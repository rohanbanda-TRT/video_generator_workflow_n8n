from fastapi import APIRouter, HTTPException, Depends, File, UploadFile, Form
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import uuid
import json
import base64
import httpx
import os
import requests
from fastapi.responses import FileResponse
from bs4 import BeautifulSoup
from app.utils.video_combiner import combine_videos_from_urls
from langchain_core.messages import HumanMessage

from app.agents.script_writer_agent import script_writer_agent
from app.utils.image_editor import edit_image
from app.utils.image_processor import process_scene_image, download_image_from_url
from app.core.settings import settings
import httpx
import re

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
    video_prompt: Optional[str] = Field(default=None, description="Video prompt for image editing")

class RunwayMLRequest(BaseModel):
    image_data: str = Field(..., description="Base64 encoded image data")
    prompt: str = Field(..., description="Text prompt for image generation", alias="promptText")
    model_id: str = Field(default="gen4_turbo", description="RunwayML model ID", alias="model")
    params: Optional[Dict[str, Any]] = Field(default=None, description="Additional model parameters")

class RunwayTaskRequest(BaseModel):
    task_id: str = Field(..., description="RunwayML task ID to check status")

class RunwayVideoDownloadRequest(BaseModel):
    task_id: str = Field(..., description="RunwayML task ID to download video from")

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
    video_prompt: Optional[str] = None
    error: Optional[str] = None

class SceneImageRequest(BaseModel):
    scene_number: int = Field(..., description="Scene number for organization")
    image_url: str = Field(..., description="URL of the image to process")
    prompt: str = Field(..., description="Text prompt for image editing")
    video_prompt: str = Field(..., description="Text prompt for video editing")
    size: str = Field(default="1024x1024", description="Image size (1024x1024, 1024x1792, 1792x1024)")
    quality: str = Field(default="high", description="Image quality (standard, high)")

class SceneImageResponse(BaseModel):
    success: bool
    scene_number: Optional[int] = None
    prompt: Optional[str] = None
    video_prompt: Optional[str] = None
    image_data: Optional[str] = None  # Base64 encoded image data
    error: Optional[str] = None

class RunwayMLResponse(BaseModel):
    success: bool
    task_id: Optional[str] = None
    result_url: Optional[str] = None
    result_data: Optional[str] = None  # Base64 encoded result data
    error: Optional[str] = None

class RunwayTaskResponse(BaseModel):
    success: bool
    task_id: Optional[str] = None
    status: Optional[str] = None
    progress: Optional[float] = None
    output: Optional[Any] = None  # Changed from Dict to Any to handle both dict and list
    error: Optional[str] = None

class RunwayVideoDownloadResponse(BaseModel):
    success: bool
    video_url: Optional[str] = None
    download_url: Optional[str] = None  # Local URL to download the video
    error: Optional[str] = None

class VideoCombineRequest(BaseModel):
    video_urls: List[str] = Field(..., description="List of video URLs to combine")
    
class VideoCombineResponse(BaseModel):
    success: bool
    combined_video_path: Optional[str] = None
    download_url: Optional[str] = None
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
        
        # Add video_prompt to the result
        result["video_prompt"] = request.video_prompt
        
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
            "image_data": image_data,
            "video_prompt": request.video_prompt
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error processing scene image: {str(e)}"
        }


@router.post("/runway-generate", response_model=RunwayMLResponse)
async def runway_generate_endpoint(request: RunwayMLRequest):
    """
    Generate content using RunwayML API.
    
    This endpoint sends a request to the RunwayML API with an image and text prompt
    to generate new content based on the specified model.
    
    Designed for integration with n8n workflows.
    """
    try:
        # Get API key from settings
        api_key = settings.RUNWAY_API_KEY
        if not api_key:
            raise HTTPException(status_code=500, detail="RunwayML API key not configured")
        
        # Prepare the request payload
        payload = {
            "promptImage": f"data:image/png;base64,{request.image_data}" if not request.image_data.startswith("data:") else request.image_data,
            "prompt": request.prompt
        }
        
        # Add additional parameters if provided
        if request.params:
            payload.update(request.params)
        
        # Set up headers
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-Runway-Version": settings.RUNWAY_API_VERSION,
            "User-Agent": "RunwayML API/1.0"
        }
        
        # Make the API request
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{settings.RUNWAY_API_BASE_URL}/v1/image_to_video",
                json={
                    "promptImage": f"data:image/png;base64,{request.image_data}" if not request.image_data.startswith("data:") else request.image_data,
                    "promptText": request.prompt,
                    "model": request.model_id,
                    "duration": 5,
                    "ratio": "1280:720"
                },
                headers=headers
            )
            
            # Check for errors
            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"RunwayML API error: {response.status_code} - {response.text}"
                }
            
            # Process the response
            response_data = response.json()
            
            # Print the response data for debugging
            print("RunwayML API Response:", response_data)
            print(response_data)
            
            # Return the result
            result = {
                "success": True
            }
            
            # Add task_id if present
            if "taskId" in response_data:
                result["task_id"] = response_data["taskId"]
            elif "id" in response_data:
                result["task_id"] = response_data["id"]
                
            # Log the task ID for debugging
            print(f"Task ID: {result['task_id']}")
            
            # Add URL or data based on what's in the response
            if "url" in response_data:
                result["result_url"] = response_data["url"]
            if "data" in response_data:
                result["result_data"] = response_data["data"]
                
            # Include the full response for debugging
            result["raw_response"] = response_data
            
            return result
            
    except Exception as e:
        return {
            "success": False,
            "error": f"Error generating content with RunwayML: {str(e)}"
        }

@router.post("/runway-task-status", response_model=RunwayTaskResponse)
async def runway_task_status_endpoint(request: RunwayTaskRequest):
    """
    Check the status of a RunwayML task.
    
    This endpoint checks the status of a task created by the RunwayML API.
    It returns the current status, progress, and output if the task is complete.
    
    Designed for integration with n8n workflows.
    """
    try:
        # Get API key from settings
        api_key = settings.RUNWAY_API_KEY
        if not api_key:
            raise HTTPException(status_code=500, detail="RunwayML API key not configured")
        
        # Set up headers
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-Runway-Version": settings.RUNWAY_API_VERSION,
            "User-Agent": "RunwayML API/1.0"
        }
        
        # Make the API request
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{settings.RUNWAY_API_BASE_URL}/v1/tasks/{request.task_id}",
                headers=headers
            )
            
            # Check for errors
            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"RunwayML API error: {response.status_code} - {response.text}"
                }
            
            # Process the response
            task_data = response.json()
            
            # Return the result
            result = {
                "success": True,
                "task_id": request.task_id,
                "status": task_data.get("status"),
                "progress": task_data.get("progress")
            }
            
            # Add output if available
            if "output" in task_data:
                result["output"] = task_data["output"]
            
            return result
            
    except Exception as e:
        return {
            "success": False,
            "error": f"Error checking task status with RunwayML: {str(e)}"
        }

@router.post("/runway-download-video", response_model=RunwayVideoDownloadResponse)
async def runway_download_video_endpoint(request: RunwayVideoDownloadRequest):
    """
    Download a video generated by RunwayML.
    
    This endpoint first checks the task status, and if complete, downloads the
    generated video and returns it as a URL or base64 encoded data.
    
    Designed for integration with n8n workflows.
    """
    try:
        # Get API key from settings
        api_key = settings.RUNWAY_API_KEY
        if not api_key:
            raise HTTPException(status_code=500, detail="RunwayML API key not configured")
        
        # Set up headers
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-Runway-Version": settings.RUNWAY_API_VERSION,
            "User-Agent": "RunwayML API/1.0"
        }
        
        # First check the task status
        async with httpx.AsyncClient(timeout=30.0) as client:
            status_response = await client.get(
                f"{settings.RUNWAY_API_BASE_URL}/v1/tasks/{request.task_id}",
                headers=headers
            )
            
            # Check for errors
            if status_response.status_code != 200:
                return {
                    "success": False,
                    "error": f"RunwayML API error: {status_response.status_code} - {status_response.text}"
                }
            
            # Process the response
            task_data = status_response.json()
            
            # Check if the task is complete
            # RunwayML API uses "SUCCEEDED" status instead of "COMPLETED"
            if task_data.get("status") not in ["COMPLETED", "SUCCEEDED"]:
                return {
                    "success": False,
                    "error": f"Task is not completed yet. Current status: {task_data.get('status')}"
                }
            
            # Print the task data for debugging
            print("Task data:", task_data)
            
            # Get the video URL from the output
            if "output" not in task_data:
                return {
                    "success": False,
                    "error": "No output found in the task data"
                }
                
            # Handle different output formats (array or dictionary)
            output = task_data["output"]
            video_url = None
            
            if isinstance(output, list) and len(output) > 0:
                # If output is an array, use the first item as the video URL
                video_url = output[0]
                print(f"Using array output: {video_url}")
            elif isinstance(output, dict) and "video" in output:
                # If output is a dictionary with a video field, use that
                video_url = output["video"]
                print(f"Using dictionary output: {video_url}")
            else:
                return {
                    "success": False,
                    "error": f"Unexpected output format: {output}"
                }
                
            if not video_url:
                return {
                    "success": False,
                    "error": "No video URL found in the output"
                }
            
            # Create temp directory if it doesn't exist
            os.makedirs("temp", exist_ok=True)
            
            # Download the video
            video_response = await client.get(video_url)
            if video_response.status_code != 200:
                return {
                    "success": False,
                    "error": f"Error downloading video: {video_response.status_code} - {video_response.text}"
                }
            
            # Save the video to a temporary file with a more predictable name
            video_filename = f"runway_video_{request.task_id}.mp4"
            temp_video_path = f"temp/{video_filename}"
            with open(temp_video_path, "wb") as f:
                f.write(video_response.content)
            
            # Create a download URL for the video file
            download_url = f"/download/{video_filename}"
            
            # Return the result
            return {
                "success": True,
                "video_url": video_url,  # Original RunwayML URL
                "download_url": download_url  # Local download URL
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": f"Error downloading video from RunwayML: {str(e)}"
        }

@router.get("/download/{filename}")
async def download_video(filename: str):
    """
    Download a video file by filename.
    
    This endpoint serves video files from the temp directory.
    """
    try:
        video_path = f"temp/{filename}"
        
        # Check if the file exists
        if not os.path.exists(video_path):
            raise HTTPException(status_code=404, detail="Video file not found")
        
        # Return the file as a response
        return FileResponse(
            path=video_path,
            filename=filename,
            media_type="video/mp4"
        )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Error downloading video: {str(e)}")

@router.post("/combine-videos", response_model=VideoCombineResponse)
async def combine_videos_endpoint(request: VideoCombineRequest):
    """
    Combine multiple videos in sequence.
    
    This endpoint takes a list of video URLs, downloads them, and combines them
    into a single video in the specified sequence. The combined video is stored
    in the 'combined_generated_videos' folder and can be accessed via the returned URL.
    
    Designed for integration with n8n workflows.
    """
    try:
        # Call the video combiner utility function
        result = await combine_videos_from_urls(request.video_urls)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": f"Error combining videos: {str(e)}"
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
