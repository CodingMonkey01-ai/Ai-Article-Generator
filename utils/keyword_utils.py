DEFAULT_KEYWORD_MODIFIERS = ("fall", "demand", "supply", "rise")


def normalize_keyword(keyword: str) -> str:
    """Return a stripped keyword string."""

    return str(keyword).strip()


def normalize_keywords(keywords: list[str]) -> list[str]:
    """Return stripped, non-empty keywords without duplicates, preserving order."""

    cleaned = []
    seen = set()

    for keyword in keywords:
        value = normalize_keyword(keyword)
        if not value or value in seen:
            continue
        cleaned.append(value)
        seen.add(value)

    return cleaned


def expand_keywords_with_modifiers(keywords: list[str]) -> list[str]:
    """Expand each keyword with the standard modifier set."""

    expanded = []
    for keyword in normalize_keywords(keywords):
        for modifier in DEFAULT_KEYWORD_MODIFIERS:
            expanded.append(f"{keyword} {modifier}")
    return expanded
