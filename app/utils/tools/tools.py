from typing import Dict, List
from langchain.tools import tool
from openai import OpenAI
from app.core.settings import settings
from app.core.logging_config import setup_logging

# Set up logging
logger = setup_logging(__name__)

@tool
def process_multi_images(image_urls: List[str]) -> Dict[str, str]:
    """
    Process a list of images and return their details sequentially.
    
    Args:
        image_urls: List of URLs pointing to images to analyze
        
    Returns:
        Dictionary mapping image URLs to their analysis
    """
    results = {}
    try:
        openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
        for i, image_url in enumerate(image_urls, start=1):
            logger.info(f"Processing image {i}: {image_url}")
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Please analyze this image and extract the details."},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }
            ]
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                max_tokens=500,
            )
            results[image_url] = response.choices[0].message.content
        logger.info(f"Processed {len(image_urls)} images successfully")
    except Exception as e:
        logger.error(f"Error processing images: {str(e)}")
        results["error"] = str(e)
    return results
