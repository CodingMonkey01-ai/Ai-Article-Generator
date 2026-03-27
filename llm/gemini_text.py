import json
from langfuse import observe
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from config.settings import GEMINI_API_KEY

genai.configure(api_key=GEMINI_API_KEY)

# Use flash model for quick tasks (relevance checking) - faster & cheaper
flash_model = genai.GenerativeModel("gemini-2.0-flash")

# Use pro model for article generation - better quality
pro_model = genai.GenerativeModel("gemini-2.5-pro")

safety_settings = [
    {"category": HarmCategory.HARM_CATEGORY_HARASSMENT, "threshold": HarmBlockThreshold.BLOCK_ONLY_HIGH},
    {"category": HarmCategory.HARM_CATEGORY_HATE_SPEECH, "threshold": HarmBlockThreshold.BLOCK_ONLY_HIGH},
    {"category": HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, "threshold": HarmBlockThreshold.BLOCK_ONLY_HIGH},
    {"category": HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, "threshold": HarmBlockThreshold.BLOCK_ONLY_HIGH},
]

civic_attr = getattr(HarmCategory, "HARM_CATEGORY_CIVIC_INTEGRITY", None)
if civic_attr is not None:
    safety_settings.append({"category": civic_attr, "threshold": HarmBlockThreshold.BLOCK_ONLY_HIGH})

ARTICLE_PROMPT = """You are a B2B content strategist. Generate an SEO-optimized blog article.

KEYWORD: "{keyword}"
TOPIC: "{news_title}"

SOURCE DATA (from multiple news sources - extract the BEST and most relevant content from each):
{web_content}

INSTRUCTIONS:
1. Analyze ALL provided sources carefully
2. Extract the most valuable, accurate, and relevant information from EACH source
3. Combine insights to create a comprehensive, well-rounded article
4. Prioritize facts, statistics, quotes, and unique perspectives from different sources
5. Synthesize information - don't just copy, create original flowing content

OUTPUT FORMAT (exactly):

SEO Title: (50-60 chars, include keyword)

Meta Description: (120-150 chars)

Title: (50-60 chars)

[Introduction: 1-2 paragraphs, 80-120 words answering What/Who/Where/When/Why/How]

Key Insights:
- [4-5 bullet points, 1-2 lines each - combine best insights from all sources]

## [H2 Heading with keyword]

[Paragraph 70-90 words]

### [H3 Subheading]

[Paragraph 70-90 words]

## [H2 Heading]

[Paragraph 70-90 words]

### [H3 Subheading]

[Paragraph 70-90 words]

[Continue with 8-10 total paragraphs]

### FAQs

Q1: [Question]
A: [2-3 sentences]

Q2: [Question]
A: [2-3 sentences]

Q3: [Question]
A: [2-3 sentences]

---
**Author:** [Professional bio, 2-3 lines]

RULES:
- 800-1200 words total
- Use keyword 5-7 times naturally
- No links, citations, or source mentions
- Professional, data-driven tone
- Short paragraphs (3-4 sentences max)
- Combine the BEST content from ALL provided sources into one cohesive article

Generate the article now:"""

BATCH_RELEVANCE_PROMPT = """Score how relevant each news title is to the keyword. Return ONLY a JSON array.

KEYWORD: "{keyword}"

TITLES:
{titles_list}

Return JSON array with scores for each title:
[{{"index": 0, "confidence": 0.0-1.0}}, {{"index": 1, "confidence": 0.0-1.0}}, ...]

Rules:
- confidence: 0.0 = not relevant, 1.0 = highly relevant
- Be strict: only high scores for titles directly about the keyword
- Return ONLY the JSON array, no other text"""

@observe()
def get_relevant_news_list(keyword: str, news_list: list, min_confidence: float = 0.4) -> list:
    """
    Find all news articles above min_confidence using batch relevance check.
    Uses a single API call to check all titles at once.
    Returns list of articles with confidence > min_confidence (40% default).
    """
    if not news_list:
        return []

    # Build titles list for batch processing
    titles_list = "\n".join([f"{i}. {news['title']}" for i, news in enumerate(news_list)])

    prompt = BATCH_RELEVANCE_PROMPT.format(
        keyword=keyword,
        titles_list=titles_list
    )

    try:
        response = flash_model.generate_content(
            prompt,
            generation_config={"temperature": 0, "max_output_tokens": 500},
            safety_settings=safety_settings,
        )

        result_text = response.text.strip()
        # Clean markdown if present
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
        result_text = result_text.strip()

        scores = json.loads(result_text)

        # Collect all matches above min_confidence
        relevant_news = []

        for score in scores:
            idx = score.get("index", -1)
            confidence = float(score.get("confidence", 0))

            if 0 <= idx < len(news_list) and confidence >= min_confidence:
                news_item = news_list[idx].copy()
                news_item["confidence"] = confidence
                news_item["keyword"] = keyword
                relevant_news.append(news_item)

        # Sort by confidence descending
        relevant_news.sort(key=lambda x: x["confidence"], reverse=True)

        print(f"Found {len(relevant_news)} relevant articles for '{keyword}' (confidence >= {min_confidence})")

        return relevant_news

    except Exception as e:
        print(f"Batch relevance check failed: {e}")
        return []


@observe()
def generate_article_from_web_search(keyword: str, news_title: str, web_content: str = "") -> str:
    """
    Generate an article based on keyword, news title, and web search content.
    """
    prompt = ARTICLE_PROMPT.format(
        keyword=keyword,
        news_title=news_title,
        web_content=web_content[:15000] if web_content else "Use your knowledge to create accurate content."
    )

    response = pro_model.generate_content(
        prompt,
        generation_config={"temperature": 0.3, "max_output_tokens": 4096},
        safety_settings=safety_settings,
    )
    return response.text
