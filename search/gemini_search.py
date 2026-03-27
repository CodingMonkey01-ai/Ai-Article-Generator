import json
import time
from datetime import datetime, timedelta
from google import genai
from google.genai import types
from config.settings import GEMINI_API_KEY
from llm.gemini_text import get_relevant_news_list

MAX_RETRIES = 3

client = genai.Client(api_key=GEMINI_API_KEY)

SEARCH_MODEL = "gemini-2.0-flash"

google_search_tool = types.Tool(google_search=types.GoogleSearch())


def _extract_grounding_urls(response):
    """Extract titles and URLs from grounding metadata."""
    news_list = []
    if not response.candidates:
        return news_list
    for candidate in response.candidates:
        metadata = candidate.grounding_metadata
        if not metadata:
            continue
        chunks = metadata.grounding_chunks
        if not chunks:
            continue
        for chunk in chunks:
            if chunk.web:
                news_list.append({
                    "title": chunk.web.title or "",
                    "url": chunk.web.uri or ""
                })
    return news_list


def get_news_for_keyword(keyword, num_results=10, min_confidence=0.4, last_fetch_date=None,
                         include_domains=None, exclude_domains=None):
    """
    Fetch news for a keyword using Gemini with Google Search grounding.
    Returns all articles above min_confidence.
    """
    today = datetime.now()
    today_str = today.strftime("%Y-%m-%d")
    week_ago = (today - timedelta(days=7)).strftime("%Y-%m-%d")

    if last_fetch_date:
        start_date = last_fetch_date
    else:
        start_date = week_ago

    end_date = today_str

    domain_filter = ""
    if include_domains:
        domain_filter += f"\nOnly include results from these domains: {', '.join(include_domains)}"
    if exclude_domains:
        domain_filter += f"\nExclude results from these domains: {', '.join(exclude_domains)}"

    prompt = f"""Find the latest news articles about "{keyword}" published between {start_date} and {end_date}.
{domain_filter}
List each article with its title and source URL. Focus on recent news and current events about this topic."""

    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=SEARCH_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[google_search_tool],
                    temperature=0,
                ),
            )

            # Primary: extract from grounding metadata (most reliable for real URLs)
            news_list = _extract_grounding_urls(response)

            # Fallback: try to parse JSON from response text
            if not news_list:
                try:
                    result_text = response.text.strip()
                    if result_text.startswith("```"):
                        result_text = result_text.split("```")[1]
                        if result_text.startswith("json"):
                            result_text = result_text[4:]
                    result_text = result_text.strip()
                    parsed = json.loads(result_text)
                    if isinstance(parsed, list):
                        news_list = parsed
                except (json.JSONDecodeError, ValueError):
                    pass

            # Filter out entries without title or url
            news_list = [n for n in news_list if n.get("title") and n.get("url")]

            if not news_list:
                print(f"No search results found for '{keyword}'")
                return []

            print(f"Google Search returned {len(news_list)} results for '{keyword}'")

            # Brief pause before relevance check to avoid rate limiting
            time.sleep(2)

            return get_relevant_news_list(
                keyword=keyword,
                news_list=news_list,
                min_confidence=min_confidence
            )

        except Exception as e:
            if "429" in str(e) and attempt < MAX_RETRIES - 1:
                wait = 2 ** (attempt + 1)
                print(f"Rate limited for '{keyword}', retrying in {wait}s...")
                time.sleep(wait)
                continue
            print(f"Gemini search failed for '{keyword}': {e}")
            return []


def get_web_content_for_article(keyword: str, news_title: str, num_results: int = 10) -> str:
    """
    Search the web for content related to keyword and news title using Gemini with Google Search.
    Returns text content from grounded web search results.
    """
    prompt = f"""Search the web for detailed information about: "{keyword} {news_title}"

Provide comprehensive, factual content about this topic including:
- Key facts and details
- Recent developments
- Statistics and data if available
- Expert opinions or quotes if available
- Background context

Write a detailed research summary that covers all the important aspects of this topic."""

    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=SEARCH_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[google_search_tool],
                    temperature=0.1,
                    max_output_tokens=4096,
                ),
            )

            content = response.text

            # Extract grounding sources if available
            sources = _extract_grounding_urls(response)
            if sources:
                source_lines = [f"Source: {s['title']}" for s in sources[:5]]
                content = "\n".join(source_lines) + "\n\n" + content

            return content

        except Exception as e:
            if "429" in str(e) and attempt < MAX_RETRIES - 1:
                wait = 2 ** (attempt + 1)
                print(f"Rate limited for web content, retrying in {wait}s...")
                time.sleep(wait)
                continue
            print(f"Gemini web content search failed: {e}")
            return ""
