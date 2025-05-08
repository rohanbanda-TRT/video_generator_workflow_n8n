import requests
import os
import uuid
from typing import Optional, Dict, Any
from pathlib import Path
import logging
from app.core.settings import settings
from app.core.logging_config import setup_logging

# Set up logging
logger = setup_logging(__name__)

def download_image_from_url(
    image_url: str,
    save_directory: str = "temp",
    filename: Optional[str] = None
) -> Dict[str, Any]:
    """
    Download an image from a URL and save it to a local file.
    
    Args:
        image_url: URL of the image to download
        save_directory: Directory to save the image in
        filename: Optional filename to use (if None, a UUID will be generated)
        
    Returns:
        Dictionary with local file path and status information
    """
    try:
        # Create directory if it doesn't exist
        os.makedirs(save_directory, exist_ok=True)
        
        # Generate filename if not provided
        if not filename:
            ext = os.path.splitext(image_url.split("?")[0])[1] or ".jpg"
            filename = f"{uuid.uuid4()}{ext}"
        
        # Full path to save the image
        file_path = os.path.join(save_directory, filename)
        
        # Download the image
        logger.info(f"Downloading image from {image_url}")
        response = requests.get(image_url, stream=True, timeout=10)
        response.raise_for_status()
        
        # Save the image to disk
        with open(file_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        logger.info(f"Image saved to {file_path}")
        
        return {
            "success": True,
            "file_path": file_path,
            "message": "Image downloaded successfully"
        }
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error downloading image: {str(e)}")
        return {
            "success": False,
            "error": f"Error downloading image: {str(e)}"
        }
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }

def process_scene_image(
    scene_number: int,
    image_url: str,
    prompt: str,
    size: str = "1024x1024",
    quality: str = "high"
) -> Dict[str, Any]:
    """
    Process an image for a specific scene by downloading it and preparing it for editing.
    
    Args:
        scene_number: Scene number for organization
        image_url: URL of the image to process
        prompt: Text prompt for image editing
        size: Image size (1024x1024, 1024x1792, 1792x1024)
        quality: Image quality (standard, high)
        
    Returns:
        Dictionary with downloaded image path and metadata
    """
    # Create scene-specific directory
    scene_dir = f"temp/scene_{scene_number}"
    os.makedirs(scene_dir, exist_ok=True)
    
    # Download the image
    download_result = download_image_from_url(
        image_url=image_url,
        save_directory=scene_dir
    )
    
    if not download_result["success"]:
        return download_result
    
    # Add scene metadata
    result = {
        "success": True,
        "scene_number": scene_number,
        "original_image_path": download_result["file_path"],
        "prompt": prompt,
        "size": size,
        "quality": quality,
        "output_path": os.path.join(scene_dir, f"edited_{os.path.basename(download_result['file_path'])}")
    }
    
    return result
