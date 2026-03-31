import re
import time
from langfuse import observe
from google import genai
from google.genai.types import (
    HarmCategory,
    HarmBlockThreshold,
    GenerateContentConfig
)
from config.settings import GEMINI_API_KEY

# -------------------------------
# CONFIG
# -------------------------------
client = genai.Client(api_key=GEMINI_API_KEY)

MODEL = "gemini-2.5-flash"
MAX_RETRIES = 5


# -------------------------------
# SAFETY SETTINGS (FIXED)
# -------------------------------
safety_settings = [
    {"category": HarmCategory.HARM_CATEGORY_HARASSMENT, "threshold": HarmBlockThreshold.BLOCK_ONLY_HIGH},
    {"category": HarmCategory.HARM_CATEGORY_HATE_SPEECH, "threshold": HarmBlockThreshold.BLOCK_ONLY_HIGH},
    {"category": HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, "threshold": HarmBlockThreshold.BLOCK_ONLY_HIGH},
    {"category": HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, "threshold": HarmBlockThreshold.BLOCK_ONLY_HIGH},
]

civic_attr = getattr(HarmCategory, "HARM_CATEGORY_CIVIC_INTEGRITY", None)
if civic_attr is not None:
    safety_settings.append({"category": civic_attr, "threshold": HarmBlockThreshold.BLOCK_ONLY_HIGH})


# -------------------------------
# SIMPLE FILTER (NO GEMINI)
# -------------------------------
def filter_relevant_news(keyword: str, news_list: list, top_n: int = 5):
    """Select the news items whose titles best match the keyword."""

    keyword = keyword.lower()

    filtered = [
        n for n in news_list
        if keyword in n["title"].lower()
    ]

    if not filtered:
        filtered = news_list[:top_n]

    return filtered[:top_n]


# -------------------------------
# ARTICLE PROMPT
# -------------------------------
ARTICLE_PROMPT = """You are a B2B content strategist. Generate an SEO-optimized blog article.

KEYWORD: "{keyword}"

HEADLINES:
{headlines}

INSTRUCTIONS:
1. Analyze ALL headlines carefully
2. Infer trends and insights from them
3. Combine information into a comprehensive article
4. Add realistic data, stats, and industry insights

OUTPUT FORMAT:

SEO Title:
Meta Description:
Title:

Introduction

Key Insights:
- Point 1
- Point 2
- Point 3
- Point 4

## Main Section
Content

## Another Section
Content

### FAQs
Q1:
A:

Q2:
A:

Q3:
A:

RULES:
- 800-1200 words
- Professional tone
- No links
"""


def _parse_retry_delay_seconds(error_message: str) -> int | None:
    """Extract a retry delay in seconds from a provider error message."""

    match = re.search(r"retry in ([\d.]+)s", error_message, flags=re.IGNORECASE)
    if not match:
        return None
    return max(1, int(float(match.group(1))))


def _classify_generation_error(error_message: str) -> tuple[bool, str, int | None]:
    """Classify Gemini text errors into retryable and non-retryable cases."""

    lowered = error_message.lower()
    retry_after = _parse_retry_delay_seconds(error_message)

    if "quota exceeded" in lowered or "billing details" in lowered:
        return False, (
            f"Gemini text quota exhausted for model '{MODEL}'. "
            "Wait for quota reset, switch to a paid plan, or change to another model."
        ), retry_after

    if "resource_exhausted" in lowered or "429" in lowered:
        return True, "Gemini text rate limited.", retry_after

    if "503" in lowered or "unavailable" in lowered or "high demand" in lowered:
        return True, "Gemini text model is temporarily unavailable due to high demand.", retry_after

    return False, f"Gemini text generation failed: {error_message}", None


# -------------------------------
# MAIN ARTICLE GENERATION (1 CALL)
# -------------------------------
@observe()
def generate_article_from_news(keyword: str, news_list: list) -> dict:
    """Generate an article from RSS headlines for a single keyword."""

    if not news_list:
        return {"article": "", "error": "No news available for article generation."}

    filtered_news = filter_relevant_news(keyword, news_list)

    headlines = "\n".join([f"- {n['title']}" for n in filtered_news])

    prompt = ARTICLE_PROMPT.format(
        keyword=keyword,
        headlines=headlines
    )

    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=prompt,
                config=GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=4096,
                    safety_settings=safety_settings  # ✅ FIXED HERE
                ),
            )

            return {"article": response.text or "", "error": None}

        except Exception as e:
            should_retry, error_message, retry_after = _classify_generation_error(str(e))

            if should_retry and attempt < MAX_RETRIES - 1:
                wait = retry_after or min(60, 5 * (2 ** attempt))
                print(f"Text generation temporary failure, retrying in {wait}s...")
                time.sleep(wait)
                continue

            print(f"Article generation failed: {e}")
            return {"article": "", "error": error_message}

    return {"article": "", "error": "Gemini text generation failed after repeated retries."}
