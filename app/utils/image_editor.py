from openai import OpenAI
import base64
import os
from typing import Optional, Union, BinaryIO
from pathlib import Path
from app.core.settings import settings
from app.core.logging_config import setup_logging

# Set up logging
logger = setup_logging(__name__)

def edit_image(
    image_file: Union[str, Path, BinaryIO],
    prompt: str,
    size: str = "1024x1024",
    quality: str = "high",
    save_path: Optional[str] = None
) -> dict:
    """
    Edit an image using OpenAI's image editing API.
    
    Args:
        image_file: Path to image file or file-like object
        prompt: Text prompt describing the desired edits
        mask_file: Optional path to mask file or file-like object
        size: Image size (1024x1024, 1024x1792, 1792x1024)
        quality: Image quality (standard, high)
        style: Image style (natural, vivid)
        save_path: Optional path to save the generated image
        
    Returns:
        Dictionary with image URL or base64 data and save path if applicable
    """
    try:
        # Initialize OpenAI client
        client = OpenAI(api_key=settings.OPENAI_API_KEY_TPN)
        
        # Prepare API call parameters
        params = {
            "model": "gpt-image-1",  # Use DALL-E 3 for image editing
            "image": image_file if isinstance(image_file, BinaryIO) else open(image_file, "rb"),
            "prompt": prompt,
            "n": 1,
            "size": size,
            "quality": quality
        }
        
        # Call the API
        logger.info(f"Editing image with prompt: {prompt}")
        response = client.images.edit(**params)
        
        result = {}
        
        # Process the response
        if hasattr(response.data[0], 'b64_json') and response.data[0].b64_json:
            # Handle base64 data
            image_data = response.data[0].b64_json
            result["b64_json"] = image_data
            
            # Save the image if requested
            if save_path:
                image_bytes = base64.b64decode(image_data)
                with open(save_path, "wb") as f:
                    f.write(image_bytes)
                result["saved_path"] = save_path
                logger.info(f"Image saved to {save_path}")
                
        elif hasattr(response.data[0], 'url') and response.data[0].url:
            # Handle URL response
            result["url"] = response.data[0].url
            logger.info(f"Image URL generated: {response.data[0].url}")
        else:
            logger.error("No image data found in the response")
            result["error"] = "No image data found in the response"
        
        return result
    
    except Exception as e:
        logger.error(f"Error editing image: {str(e)}")
        return {"error": str(e)}
