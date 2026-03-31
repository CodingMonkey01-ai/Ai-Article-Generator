from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from utils.article_service import generate_documents_for_keywords
from utils.postgres_store import (
    delete_keyword_and_documents,
    get_documents_by_keyword,
    init_db,
    postgres_enabled,
)


app = FastAPI(title="Article Generator API")


class KeywordsRequest(BaseModel):
    """Request payload for keyword-based article generation."""

    keywords: list[str] = Field(default_factory=list, min_length=1)
    expand_modifiers: bool = False


@app.on_event("startup")
def startup() -> None:
    """Initialize database tables when the API process starts."""

    init_db()


@app.get("/")
def root() -> dict:
    """Return a simple root response for discovery and uptime checks."""

    return {
        "message": "Article Generator API is running.",
        "docs_url": "/docs",
    }


@app.get("/health")
def healthcheck() -> dict:
    """Report basic API and database configuration status."""

    return {
        "status": "ok",
        "postgres_enabled": postgres_enabled(),
    }


@app.post("/keywords")
def create_keywords(payload: KeywordsRequest) -> dict:
    """Generate and persist articles for the submitted keywords."""

    try:
        result = generate_documents_for_keywords(
            keywords=payload.keywords,
            expand_modifiers=payload.expand_modifiers,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "count": len(result["documents"]),
        "keywords": result["keywords"],
        "documents": result["documents"],
        "failures": result["failures"],
    }


@app.get("/documents")
def get_documents(keyword: str = Query(..., min_length=1)) -> dict:
    """Fetch stored documents by exact or partial keyword match."""

    try:
        docs = get_documents_by_keyword(keyword)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "keyword": keyword,
        "count": len(docs),
        "documents": docs,
    }


@app.get("/keywords/{keyword}/documents")
def get_keyword_documents(keyword: str) -> dict:
    """Alias route for fetching documents by keyword path parameter."""

    return get_documents(keyword)


@app.delete("/keywords/{keyword}")
def delete_keyword(keyword: str) -> dict:
    """Delete a keyword family and all linked documents."""

    try:
        result = delete_keyword_and_documents(keyword)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not result["deleted"]:
        raise HTTPException(status_code=404, detail=f"Keyword '{keyword}' not found.")

    return result
