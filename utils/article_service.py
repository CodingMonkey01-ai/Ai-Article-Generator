from utils.keyword_utils import expand_keywords_with_modifiers, normalize_keywords
from llm.gemini_text import generate_article_from_news
from search.gemini_search import get_news_for_keyword
from utils.postgres_store import add_keywords, save_document, update_keyword_fetch_date


def build_keywords(keywords: list[str], expand_modifiers: bool) -> list[str]:
    """Normalize keywords and optionally expand them with standard modifiers."""

    cleaned = normalize_keywords(keywords)
    seen = set(cleaned)

    if expand_modifiers:
        for keyword in list(cleaned):
            for expanded in expand_keywords_with_modifiers([keyword]):
                if expanded not in seen:
                    cleaned.append(expanded)
                    seen.add(expanded)

    return cleaned


def _filename_for_keyword(keyword: str) -> str:
    """Convert a keyword into a stable filename stem."""

    return keyword.replace(" ", "_")


def generate_documents_for_keywords(keywords: list[str], expand_modifiers: bool) -> dict:
    """Generate articles for keywords and persist them to Postgres."""

    generated_keywords = build_keywords(keywords, expand_modifiers)
    add_keywords(generated_keywords)

    documents = []
    failures = []

    for keyword in generated_keywords:
        news_list = get_news_for_keyword(keyword)

        if not news_list:
            failures.append({
                "keyword": keyword,
                "error": "No news found for keyword.",
            })
            continue

        update_keyword_fetch_date(keyword)

        article_result = generate_article_from_news(keyword, news_list)
        article = article_result["article"]

        if article_result["error"]:
            failures.append({
                "keyword": keyword,
                "error": article_result["error"],
            })
            continue

        filename = f"{_filename_for_keyword(keyword)}.docx"
        saved = save_document(
            keyword=keyword,
            filename=filename,
            file_path="",
            article_text=article,
        )
        documents.append(saved)

    return {
        "keywords": generated_keywords,
        "documents": documents,
        "failures": failures,
    }
