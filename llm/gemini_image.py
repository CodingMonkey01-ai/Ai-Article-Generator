import os
from google import genai
from langfuse import observe
from google.genai.types import GenerateImagesConfig
from config.settings import GEMINI_API_KEY

client = genai.Client(api_key=GEMINI_API_KEY)

@observe()
def generate_image(article_title: str, save_path: str):
    prompt = f"""
    article_title : {article_title}
    Professional editorial photography capturing the core subject matter of this article through wide-angle 
    photorealistic composition. Analyze the article topic and create a relevant scene showing the 
    primary industry, location, or subject at scale with documentary journalism style. 
    Use natural authentic colors appropriate to the subject matter without filters or overlays, 
    authentic environmental lighting matching the context. Wide cinematic framing showing landscape, 
    industrial setting, agricultural scene, urban environment, or workplace as relevant to article content. 
    Clean high-end photojournalism for business news publication, no text, no letters, no words, 
    no signage visible anywhere in frame. Corporate editorial photography aesthetic with realistic
    color tones, sharp professional focus, environmental storytelling through contextual photography.
    Documentary visual standard similar to Fortune, Bloomberg, McKinsey editorial imagery,
    premium business publication quality with journalistic authenticity and professional 
    sophistication appropriate to the article's subject matter and industry.
    """

    os.makedirs(os.path.dirname(save_path), exist_ok=True)

    response = client.models.generate_images(
    model="models/imagen-4.0-generate-001",
    prompt=prompt,
    config={
        "imageSize": "1K",        
        "numberOfImages": 1
    }
    )

    image_bytes = response.generated_images[0].image.image_bytes

    with open(save_path, "wb") as f:
        f.write(image_bytes)


    return save_path


