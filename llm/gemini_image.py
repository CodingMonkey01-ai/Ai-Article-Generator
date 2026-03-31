import os
import re
import time
from google import genai
from langfuse import observe
from config.settings import GEMINI_API_KEY

client = genai.Client(api_key=GEMINI_API_KEY)
IMAGE_MODELS = [
    os.getenv("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image-preview"),
    "gemini-2.5-flash-image",
    "gemini-3-pro-image-preview",
]
IMAGE_BLOCKED_UNTIL = 0.0
IMAGE_BLOCK_REASON = ""


def sanitize_filename(text: str) -> str:
    """Make safe filename from title."""
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"\s+", "_", text)
    return text[:100]


def _parse_retry_delay_seconds(error_message: str) -> int | None:
    """Extract a retry delay in seconds from a provider error message."""

    match = re.search(r"retry in ([\d.]+)s", error_message, flags=re.IGNORECASE)
    if not match:
        return None
    return max(1, int(float(match.group(1))))


def _classify_image_error(error_message: str, model: str) -> tuple[bool, str, int | None]:
    """Classify Gemini image errors into retryable and non-retryable cases."""

    lowered = error_message.lower()
    retry_after = _parse_retry_delay_seconds(error_message)

    if "not_found" in lowered or "is not found" in lowered or "not supported" in lowered:
        return False, f"Image model '{model}' is unavailable for this Gemini API setup.", None

    if "quota exceeded" in lowered or "billing details" in lowered:
        return False, "Gemini image quota exhausted.", retry_after

    if "resource_exhausted" in lowered or "429" in lowered:
        return True, "Gemini image rate limited.", retry_after

    return False, f"Image generation failed: {error_message}", None


@observe()
def generate_image(article_title: str, save_path: str = None) -> dict:
    """
    Generate image for article using Gemini image-capable models.
    """

    prompt = f"""
    Article topic: {article_title}

    Professional editorial photography capturing the subject of this article.
    Wide-angle photorealistic composition with documentary journalism style.

    Show real-world context relevant to the topic:
    - industry
    - environment
    - people (if relevant)

    Style:
    - natural colors
    - realistic lighting
    - no filters
    - no text, no words, no logos
    - business publication quality (Bloomberg, McKinsey style)

    Clean, sharp, professional, cinematic composition.
    """

    if not save_path:
        filename = sanitize_filename(article_title) + ".png"
        save_path = os.path.join("generated_images", filename)

    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    global IMAGE_BLOCKED_UNTIL, IMAGE_BLOCK_REASON

    if IMAGE_BLOCKED_UNTIL > time.time():
        return {
            "image_path": None,
            "error": IMAGE_BLOCK_REASON or "Gemini image generation is temporarily blocked due to quota exhaustion.",
        }

    max_retries = 3
    attempted_models = []

    for model in dict.fromkeys(IMAGE_MODELS):
        attempted_models.append(model)

        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=[prompt],
                )

                image_bytes = None

                for part in getattr(response, "parts", []) or []:
                    inline_data = getattr(part, "inline_data", None)
                    if inline_data is not None:
                        image_bytes = getattr(inline_data, "data", None)
                        if image_bytes:
                            break

                if not image_bytes:
                    candidates = getattr(response, "candidates", None) or []
                    for candidate in candidates:
                        content = getattr(candidate, "content", None)
                        parts = getattr(content, "parts", None) or []
                        for part in parts:
                            inline_data = getattr(part, "inline_data", None)
                            if inline_data is not None:
                                image_bytes = getattr(inline_data, "data", None)
                                if image_bytes:
                                    break
                        if image_bytes:
                            break

                if not image_bytes:
                    return {
                        "image_path": None,
                        "error": f"Model '{model}' returned no image data.",
                    }

                with open(save_path, "wb") as f:
                    f.write(image_bytes)

                print(f"Image saved: {save_path}")
                return {"image_path": save_path, "error": None}

            except Exception as e:
                should_retry, error_message, retry_after = _classify_image_error(str(e), model)

                if should_retry and attempt < max_retries - 1:
                    wait = retry_after or (5 * (attempt + 1))
                    print(f"Rate limited (image), retrying in {wait}s...")
                    time.sleep(wait)
                    continue

                print(f"Image generation failed: {e}")

                if "unavailable" in error_message.lower():
                    break

                if "quota exhausted" in error_message.lower():
                    block_seconds = retry_after or 60
                    IMAGE_BLOCKED_UNTIL = time.time() + block_seconds
                    IMAGE_BLOCK_REASON = (
                        f"{error_message} Skipping further image generation attempts for about {block_seconds}s."
                    )

                return {"image_path": None, "error": error_message}

    return {
        "image_path": None,
        "error": (
            "No compatible Gemini image model was available. "
            f"Tried: {', '.join(attempted_models)}"
        ),
    }
