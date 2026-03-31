import pandas as pd
from datetime import datetime
import os


def safe_read_excel(excel_path):
    """Read the keyword workbook safely and normalize expected columns."""

    import os
    import pandas as pd

    if not os.path.exists(excel_path) or os.path.getsize(excel_path) == 0:
        return pd.DataFrame(columns=["keyword", "fetch_date"])

    try:
        df = pd.read_excel(excel_path, engine="openpyxl")
    except Exception:
        return pd.DataFrame(columns=["keyword", "fetch_date"])

    # ✅ FIXED HERE
    df.columns = df.columns.map(lambda x: str(x).strip().lower())

    # Ensure required columns exist
    if "keyword" not in df.columns:
        df["keyword"] = None

    if "fetch_date" not in df.columns:
        df["fetch_date"] = None

    return df

def load_keywords_with_dates(excel_path):
    """Load keyword records with fetch dates from the Excel store."""

    df = safe_read_excel(excel_path)

    keywords_data = []
    for _, row in df.iterrows():
        keyword = row.get("keyword")
        if pd.notna(keyword):
            fetch_date = row.get("fetch_date")

            if pd.notna(fetch_date):
                if isinstance(fetch_date, datetime):
                    fetch_date = fetch_date.strftime("%Y-%m-%d")
                else:
                    fetch_date = str(fetch_date)
            else:
                fetch_date = None

            keywords_data.append({
                "keyword": str(keyword).strip(),
                "fetch_date": fetch_date
            })

    return keywords_data


def update_fetch_dates(excel_path, keywords_to_update: list):
    """Update fetch dates for the supplied keywords in the Excel store."""

    df = safe_read_excel(excel_path)

    today = datetime.now().strftime("%Y-%m-%d")

    for keyword in keywords_to_update:
        mask = df["keyword"].astype(str).str.strip() == keyword
        df.loc[mask, "fetch_date"] = today

    df.to_excel(excel_path, index=False)

    return len(keywords_to_update)


def add_keywords_to_excel(excel_path, new_keywords: list):
    """Append unique keywords to the Excel store."""

    df = safe_read_excel(excel_path)

    existing_keywords = set(clean_keyword_series(df["keyword"]).tolist())
    added_count = 0

    for kw in new_keywords:
        kw = str(kw).strip()
        if kw and kw not in existing_keywords:
            new_row = pd.DataFrame([{"keyword": kw, "fetch_date": None}])
            df = pd.concat([df, new_row], ignore_index=True)
            existing_keywords.add(kw)
            added_count += 1

    df.to_excel(excel_path, index=False)
    return added_count


def remove_keyword_from_excel(excel_path, keyword: str):
    """Remove a single keyword from the Excel store."""

    df = safe_read_excel(excel_path)

    initial_len = len(df)

    df = df[df["keyword"].astype(str).str.strip() != keyword.strip()]

    if len(df) < initial_len:
        df.to_excel(excel_path, index=False)
        return True

    return False


def expand_keywords_with_modifiers(keywords: list) -> list:
    """Expand each keyword with the default modifier set."""

    modifiers = ["fall", "demand", "supply", "rise"]
    expanded = []
    for kw in keywords:
        kw = str(kw).strip()
        if not kw:
            continue
        for mod in modifiers:
            expanded.append(f"{kw} {mod}")
    return expanded

def clean_keyword_series(series):
    """Normalize a pandas keyword series into stripped string values."""

    return series.astype(str).str.strip().replace("nan", "")

def load_keywords(excel_path):
    """Load unique keyword strings from the Excel store."""

    df = safe_read_excel(excel_path)
    return df["keyword"].astype(str).str.strip().replace("nan", "").dropna().unique().tolist()
