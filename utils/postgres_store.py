from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime

import psycopg

from config.settings import DATABASE_URL


def postgres_enabled() -> bool:
    """Return whether Postgres has been configured for the project."""

    return bool(DATABASE_URL)


@contextmanager
def get_connection():
    """Yield a live psycopg connection using the configured database URL."""

    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured.")

    conn = psycopg.connect(DATABASE_URL)
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    """Create the required keyword and document tables if they do not exist."""

    if not postgres_enabled():
        return

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS keywords (
                    id BIGSERIAL PRIMARY KEY,
                    keyword TEXT NOT NULL UNIQUE,
                    fetch_date DATE NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    id BIGSERIAL PRIMARY KEY,
                    keyword_id BIGINT NOT NULL REFERENCES keywords(id) ON DELETE CASCADE,
                    filename TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    article_text TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE (keyword_id, filename)
                )
                """
            )
        conn.commit()


def add_keywords(keywords: list[str]) -> list[dict]:
    """Insert or upsert keyword rows and return their stored metadata."""

    if not postgres_enabled():
        raise RuntimeError("DATABASE_URL is not configured.")

    cleaned = []
    seen = set()
    for keyword in keywords:
        value = str(keyword).strip()
        if value and value not in seen:
            cleaned.append(value)
            seen.add(value)

    if not cleaned:
        return []

    with get_connection() as conn:
        created_rows = []
        with conn.cursor() as cur:
            for keyword in cleaned:
                cur.execute(
                    """
                    INSERT INTO keywords (keyword)
                    VALUES (%s)
                    ON CONFLICT (keyword)
                    DO UPDATE SET keyword = EXCLUDED.keyword
                    RETURNING id, keyword, fetch_date, created_at
                    """,
                    (keyword,),
                )
                row = cur.fetchone()
                created_rows.append(_keyword_row_to_dict(row))
        conn.commit()

    return created_rows


def update_keyword_fetch_date(keyword: str, fetch_date: datetime | str | None = None) -> None:
    """Update the stored fetch date for a keyword."""

    if not postgres_enabled():
        return

    value = keyword.strip()
    if not value:
        return

    fetch_value = fetch_date or datetime.utcnow().date()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE keywords
                SET fetch_date = %s
                WHERE keyword = %s
                """,
                (fetch_value, value),
            )
        conn.commit()


def save_document(keyword: str, filename: str, file_path: str, article_text: str) -> dict:
    """Insert or update a generated document for a keyword."""

    if not postgres_enabled():
        raise RuntimeError("DATABASE_URL is not configured.")

    value = keyword.strip()
    if not value:
        raise ValueError("Keyword is required.")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO keywords (keyword)
                VALUES (%s)
                ON CONFLICT (keyword)
                DO UPDATE SET keyword = EXCLUDED.keyword
                RETURNING id
                """,
                (value,),
            )
            keyword_id = cur.fetchone()[0]

            cur.execute(
                """
                INSERT INTO documents (keyword_id, filename, file_path, article_text)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (keyword_id, filename)
                DO UPDATE SET
                    file_path = EXCLUDED.file_path,
                    article_text = EXCLUDED.article_text,
                    created_at = NOW()
                RETURNING id, %s, filename, file_path, article_text, created_at
                """,
                (keyword_id, filename, file_path, article_text, value),
            )
            row = cur.fetchone()
        conn.commit()

    return _document_row_to_dict(row=row)


def get_documents_by_keyword(keyword: str) -> list[dict]:
    """Fetch documents for a keyword using exact then partial matching."""

    if not postgres_enabled():
        raise RuntimeError("DATABASE_URL is not configured.")

    search_value = keyword.strip()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT d.id, k.keyword, d.filename, d.file_path, d.article_text, d.created_at
                FROM documents d
                INNER JOIN keywords k ON k.id = d.keyword_id
                WHERE k.keyword = %s
                ORDER BY d.created_at DESC
                """,
                (search_value,),
            )
            rows = cur.fetchall()

            if not rows:
                cur.execute(
                    """
                    SELECT d.id, k.keyword, d.filename, d.file_path, d.article_text, d.created_at
                    FROM documents d
                    INNER JOIN keywords k ON k.id = d.keyword_id
                    WHERE k.keyword ILIKE %s
                    ORDER BY k.keyword ASC, d.created_at DESC
                    """,
                    (f"%{search_value}%",),
                )
                rows = cur.fetchall()

    return [_document_row_to_dict(row=row) for row in rows]


def delete_keyword_and_documents(keyword: str) -> dict:
    """Delete a keyword family and cascade-delete all linked documents."""

    if not postgres_enabled():
        raise RuntimeError("DATABASE_URL is not configured.")

    search_value = keyword.strip()
    if not search_value:
        raise ValueError("Keyword is required.")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT k.id, k.keyword, COUNT(d.id) AS document_count
                FROM keywords k
                LEFT JOIN documents d ON d.keyword_id = k.id
                WHERE
                    k.keyword = %s
                    OR k.keyword IN (%s, %s, %s, %s)
                GROUP BY k.id, k.keyword
                ORDER BY k.keyword ASC
                """,
                (
                    search_value,
                    f"{search_value} fall",
                    f"{search_value} rise",
                    f"{search_value} supply",
                    f"{search_value} demand",
                ),
            )
            rows = cur.fetchall()

            if not rows:
                return {
                    "deleted": False,
                    "keyword": search_value,
                    "keywords_deleted": [],
                    "documents_deleted": 0,
                }

            cur.execute(
                """
                DELETE FROM keywords
                WHERE id = ANY(%s)
                """,
                ([row[0] for row in rows],),
            )
        conn.commit()

    return {
        "deleted": True,
        "keyword": search_value,
        "keywords_deleted": [row[1] for row in rows],
        "documents_deleted": sum(row[2] for row in rows),
    }


def _keyword_row_to_dict(row) -> dict:
    """Convert a raw keyword query row into an API-friendly dictionary."""

    return {
        "id": row[0],
        "keyword": row[1],
        "fetch_date": row[2].isoformat() if row[2] else None,
        "created_at": row[3].isoformat() if row[3] else None,
    }


def _document_row_to_dict(row) -> dict:
    """Convert a raw document query row into an API-friendly dictionary."""

    return {
        "id": row[0],
        "keyword": row[1],
        "filename": row[2],
        "file_path": row[3],
        "article_text": row[4],
        "created_at": row[5].isoformat() if row[5] else None,
    }
