import pandas as pd
from datetime import datetime


def load_keywords_with_dates(excel_path):
    """
    Load keywords with their fetch dates from Excel.
    Returns list of dicts: [{"keyword": str, "fetch_date": str or None}, ...]
    """
    df = pd.read_excel(excel_path)

    # Ensure fetch_date column exists
    if "fetch_date" not in df.columns:
        df["fetch_date"] = None

    keywords_data = []
    for _, row in df.iterrows():
        keyword = row.get("keyword")
        if pd.notna(keyword):
            fetch_date = row.get("fetch_date")
            # Convert to string format if it's a datetime
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
    """
    Update fetch dates for keywords that got news.
    keywords_to_update: list of keyword strings to update with today's date
    """
    df = pd.read_excel(excel_path)

    # Ensure fetch_date column exists
    if "fetch_date" not in df.columns:
        df["fetch_date"] = None

    today = datetime.now().strftime("%Y-%m-%d")

    # Update fetch_date for specified keywords
    for keyword in keywords_to_update:
        mask = df["keyword"].astype(str).str.strip() == keyword
        df.loc[mask, "fetch_date"] = today

    # Save back to Excel
    df.to_excel(excel_path, index=False)

    return len(keywords_to_update)


def add_keywords_to_excel(excel_path, new_keywords: list):
    """
    Add new keywords to Excel file.
    new_keywords: list of keyword strings to add
    Returns number of keywords added.
    """
    import os

    if os.path.exists(excel_path):
        df = pd.read_excel(excel_path)
        if "fetch_date" not in df.columns:
            df["fetch_date"] = None
    else:
        df = pd.DataFrame(columns=["keyword", "fetch_date"])

    existing_keywords = set(df["keyword"].astype(str).str.strip().tolist())
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
    """
    Remove a keyword from Excel file.
    Returns True if keyword was removed, False if not found.
    """
    import os

    if not os.path.exists(excel_path):
        return False

    df = pd.read_excel(excel_path)
    initial_len = len(df)

    df = df[df["keyword"].astype(str).str.strip() != keyword.strip()]

    if len(df) < initial_len:
        df.to_excel(excel_path, index=False)
        return True

    return False


def expand_keywords_with_modifiers(keywords: list) -> list:
    """
    Break down keywords by appending market modifiers.
    For each keyword, creates variations with: fall, demand, supply, rise.

    Example: "gold" -> ["gold fall", "gold demand", "gold supply", "gold rise"]
    """
    modifiers = ["fall", "demand", "supply", "rise"]
    expanded = []
    for kw in keywords:
        kw = str(kw).strip()
        if not kw:
            continue
        for mod in modifiers:
            expanded.append(f"{kw} {mod}")
    return expanded


def load_keywords(excel_path):
    """
    Legacy function - returns just keyword list for backward compatibility.
    """
    df = pd.read_excel(excel_path)
    return df["keyword"].dropna().unique().tolist()
