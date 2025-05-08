from fastapi import APIRouter, HTTPException, Depends, File, UploadFile, Form
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import uuid
import re
import json
import os
import requests
import base64
from bs4 import BeautifulSoup
from langchain_core.messages import HumanMessage

from app.agents.script_writer_agent import script_writer_agent
from app.utils.image_editor import edit_image
from app.utils.image_processor import process_scene_image, download_image_from_url
from app.core.settings import settings

# Create router
router = APIRouter(prefix="/api", tags=["script-generator"])

# The script writer agent is already initialized in the imported module

# Session storage for conversation persistence
sessions = {}

# Request models
class ScriptRequest(BaseModel):
    message: str = Field(..., description="User message containing product details and/or image URLs")
    session_id: Optional[str] = Field(default=None, description="Session ID for conversation persistence")

class ProductRequest(BaseModel):
    url: str = Field(..., description="Amazon product URL to scrape")

class ImageEditRequest(BaseModel):
    prompt: str = Field(..., description="Text prompt describing the desired edits")
    size: str = Field(default="1024x1024", description="Image size (1024x1024, 1024x1792, 1792x1024)")
    quality: str = Field(default="high", description="Image quality (standard, high)")
    style: str = Field(default="natural", description="Image style (natural, vivid)")
    return_format: str = Field(default="url", description="Return format (url, base64)")

class Base64ImageEditRequest(BaseModel):
    image_data: str = Field(..., description="Base64 encoded image data")
    prompt: str = Field(..., description="Text prompt describing the desired edits")
    size: str = Field(default="1024x1024", description="Image size (1024x1024, 1024x1792, 1792x1024)")
    quality: str = Field(default="high", description="Image quality (standard, high)")
    return_format: str = Field(default="url", description="Return format (url, base64)")

# Response models
class Scene(BaseModel):
    scene_number: int
    duration_seconds: int
    scene_description: str
    image_prompt: str
    video_prompt: str
    narration: str
    image_url: Optional[str] = None

class ScriptResponse(BaseModel):
    response: str
    session_id: str
    product_name: Optional[str] = None
    video_duration: Optional[str] = None
    scenes: Optional[List[Scene]] = None
    raw_text: Optional[str] = None

class ProductResponse(BaseModel):
    title: Optional[str] = None
    price: Optional[str] = None
    rating: Optional[str] = None
    number_of_reviews: Optional[str] = None
    availability: Optional[str] = None
    brand: Optional[str] = None
    product_description: Optional[str] = None
    product_details: Optional[Dict[str, str]] = None
    images: Optional[List[str]] = None

class ImageEditResponse(BaseModel):
    url: Optional[str] = None
    b64_json: Optional[str] = None
    saved_path: Optional[str] = None
    error: Optional[str] = None

class SceneImageRequest(BaseModel):
    scene_number: int = Field(..., description="Scene number for organization")
    image_url: str = Field(..., description="URL of the image to process")
    prompt: str = Field(..., description="Text prompt for image editing")
    size: str = Field(default="1024x1024", description="Image size (1024x1024, 1024x1792, 1792x1024)")
    quality: str = Field(default="high", description="Image quality (standard, high)")

class SceneImageResponse(BaseModel):
    success: bool
    scene_number: Optional[int] = None
    prompt: Optional[str] = None
    image_data: Optional[str] = None  # Base64 encoded image data
    error: Optional[str] = None

@router.post("/script", response_model=ScriptResponse)
async def generate_script(request: ScriptRequest):
    """
    Generate a 30-second video script for a product.
    
    This endpoint creates a professional video script with scene-by-scene breakdown,
    including image prompts, video directions, and narration.
    
    The message field should contain product details and any image URLs for analysis.
    """
    try:
        # Get or create session ID
        session_id = request.session_id or str(uuid.uuid4())
        
        # Create a human message
        human_message = HumanMessage(content=request.message)
        
        # Invoke the script writer agent
        result = script_writer_agent.invoke(
            {"messages": [human_message]},
            session_id=session_id
        )
        
        # Get the output from the result
        script_text = result.get("output", "")
        
        # Try to extract JSON from the text
        json_match = re.search(r'```(?:json)?\s*({.*?})\s*```|(\{\s*"product_name".*})', script_text, re.DOTALL)
        
        response_data = {
            "response": script_text,
            "session_id": session_id,
            "raw_text": script_text
        }
        
        if json_match:
            # Get the JSON string from whichever group matched
            json_str = json_match.group(1) if json_match.group(1) else json_match.group(2)
            script_json = json.loads(json_str)
            
            # Add script JSON data to response
            response_data["product_name"] = script_json.get("product_name")
            response_data["video_duration"] = script_json.get("video_duration")
            response_data["scenes"] = script_json.get("scenes")
        
        return response_data
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating script: {str(e)}")


@router.post("/scrape-amazon", response_model=ProductResponse)
async def scrape_amazon_product(request: ProductRequest):
    """
    Scrape product details from an Amazon product URL.
    
    This endpoint extracts product information including title, price, rating,
    description, and image URLs from an Amazon product page.
    """
    try:
        product_data = get_amazon_product_details(request.url)
        if "error" in product_data:
            raise HTTPException(status_code=400, detail=product_data["error"])
        return product_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error scraping product: {str(e)}")


@router.post("/edit-image", response_model=ImageEditResponse)
async def edit_image_endpoint(
    image: UploadFile = File(...),
    prompt: str = Form(...),
    size: str = Form("1024x1024"),
    quality: str = Form("high"),
    return_format: str = Form("url")
):
    """
    Edit an image using OpenAI's image editing API.
    
    This endpoint allows you to edit an image based on a text prompt.
    You can optionally provide a mask to specify which parts of the image to edit.
    """
    try:
        # Create temporary directory if it doesn't exist
        os.makedirs("temp", exist_ok=True)
        
        # Save uploaded image to temporary file
        temp_image_path = f"temp/{uuid.uuid4()}.png"
        with open(temp_image_path, "wb") as f:
            f.write(await image.read())
        
        # Generate output path
        output_path = f"temp/output_{uuid.uuid4()}.png"
        
        # Call the image editor
        result = edit_image(
            image_file=temp_image_path,
            prompt=prompt,
            size=size,
            quality=quality,
            save_path=output_path 
        )
        
        # Clean up temporary files
        # if os.path.exists(temp_image_path):
        #     os.remove(temp_image_path)
        
        # Return appropriate response
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        
        # If file was saved and user wants the file, return it
        if return_format == "file" and "saved_path" in result and os.path.exists(result["saved_path"]):
            return FileResponse(
                path=result["saved_path"],
                media_type="image/png",
                filename="edited_image.png"
            )
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error editing image: {str(e)}")

@router.post("/edit-image-base64", response_model=ImageEditResponse)
async def edit_image_base64_endpoint(request: Base64ImageEditRequest):
    """
    Edit an image using OpenAI's image editing API with base64 encoded image data.
    
    This endpoint allows you to edit an image based on a text prompt using base64 encoded image data.
    Designed for integration with n8n workflows where you have base64 image data.
    """
    try:
        # Create temporary directory if it doesn't exist
        os.makedirs("temp", exist_ok=True)
        
        # Decode base64 data and save to temporary file
        try:
            image_data = base64.b64decode(request.image_data)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid base64 image data: {str(e)}")
        
        # Save decoded image to temporary file
        temp_image_path = f"temp/{uuid.uuid4()}.png"
        with open(temp_image_path, "wb") as f:
            f.write(image_data)
        
        # Generate output path
        output_path = f"temp/output_{uuid.uuid4()}.png"
        
        # Call the image editor
        result = edit_image(
            image_file=temp_image_path,
            prompt=request.prompt,
            size=request.size,
            quality=request.quality,
            save_path=output_path 
        )
        
        # Clean up temporary files
        # if os.path.exists(temp_image_path):
        #     os.remove(temp_image_path)
        
        # Return appropriate response
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        
        # If file was saved and user wants the file, return it
        if request.return_format == "file" and "saved_path" in result and os.path.exists(result["saved_path"]):
            return FileResponse(
                path=result["saved_path"],
                media_type="image/png",
                filename="edited_image.png"
            )
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error editing image: {str(e)}")


@router.post("/scene-image", response_model=SceneImageResponse)
async def scene_image_endpoint(request: SceneImageRequest):
    """
    Download an image from a URL and return its base64 data along with scene information.
    
    This endpoint downloads an image from a URL and returns the image data in base64 format,
    along with the scene number and prompt, so it can be directly passed to the edit image endpoint.
    
    Designed for integration with n8n workflows.
    """
    try:
        # Create scene-specific directory
        scene_dir = f"temp/scene_{request.scene_number}"
        os.makedirs(scene_dir, exist_ok=True)
        
        # Download the image
        download_result = download_image_from_url(
            image_url=request.image_url,
            save_directory=scene_dir
        )
        
        if not download_result["success"]:
            return {
                "success": False,
                "error": download_result.get("error", "Unknown error downloading image")
            }
        
        # Read the file and convert to base64
        try:
            with open(download_result["file_path"], "rb") as image_file:
                image_data = base64.b64encode(image_file.read()).decode("utf-8")
        except Exception as e:
            return {
                "success": False,
                "error": f"Error converting image to base64: {str(e)}"
            }
        
        # Prepare the response
        return {
            "success": True,
            "scene_number": request.scene_number,
            "prompt": request.prompt,
            "image_data": image_data
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error processing scene image: {str(e)}"
        }


def get_amazon_product_details(url):
    """
    Scrape product details from an Amazon product URL.
    
    Args:
        url: Amazon product URL
        
    Returns:
        Dictionary containing product details
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/90.0.4430.93 Safari/537.36"
        )
    }

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return {"error": f"Failed to fetch page. Status code: {response.status_code}"}

    soup = BeautifulSoup(response.content, "html.parser")

    def extract_text(selector):
        element = soup.select_one(selector)
        return element.get_text(strip=True) if element else None

    title = extract_text("#productTitle")
    price = extract_text(".a-price .a-offscreen")
    rating = extract_text("span.a-icon-alt")
    reviews = extract_text("#acrCustomerReviewText")
    availability = extract_text("#availability .a-declarative, #availability span")
    brand = extract_text("#bylineInfo")
    
    # Product details table
    details = {}
    for row in soup.select("#productDetails_techSpec_section_1 tr, #productDetails_detailBullets_sections1 tr"):
        heading = row.select_one("th, td")
        value = row.select("td")
        if heading and value:
            details[heading.get_text(strip=True)] = value[-1].get_text(strip=True)

    # Description
    description = extract_text("#productDescription p") or extract_text("#productDescription")

    # Images (using regex to get from imageBlockData)
    image_urls = []
    image_data_script = soup.find("script", text=re.compile("ImageBlockATF"))
    if image_data_script:
        image_matches = re.findall(r'"hiRes":"(https[^"]+)"', image_data_script.string)
        image_urls = list(set(image_matches))  # remove duplicates

    return {
        "title": title,
        "price": price,
        "rating": rating,
        "number_of_reviews": reviews,
        "availability": availability,
        "brand": brand,
        "product_description": description,
        "product_details": details,
        "images": image_urls,
    }
