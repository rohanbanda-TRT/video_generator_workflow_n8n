"""
Video combiner utility functions.

This module provides functions for combining multiple videos into a single video.
"""

import os
import uuid
import httpx
import subprocess
from typing import List, Dict, Any, Optional
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def download_video(url: str, output_path: str) -> bool:
    """
    Download a video from a URL to a local file.
    
    Args:
        url: The URL of the video to download
        output_path: The path where the video should be saved
        
    Returns:
        bool: True if download was successful, False otherwise
    """
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(url)
            
            if response.status_code != 200:
                logger.error(f"Error downloading video: {response.status_code} - {response.text}")
                return False
            
            # Save the video to the specified path
            with open(output_path, "wb") as f:
                f.write(response.content)
                
            return True
    except Exception as e:
        logger.error(f"Error downloading video: {str(e)}")
        return False

async def combine_videos(video_paths: List[str], output_path: str) -> bool:
    """
    Combine multiple videos into a single video using FFmpeg.
    
    Args:
        video_paths: List of paths to the videos to combine
        output_path: Path where the combined video should be saved
        
    Returns:
        bool: True if combination was successful, False otherwise
    """
    list_file_path = None
    try:
        # Verify all input videos exist and have content
        for i, path in enumerate(video_paths):
            if not os.path.exists(path):
                logger.error(f"Input video {i+1} does not exist: {path}")
                return False
            if os.path.getsize(path) == 0:
                logger.error(f"Input video {i+1} is empty: {path}")
                return False
        
        # Create a temporary file listing all videos to combine
        temp_dir = os.path.abspath("temp")
        os.makedirs(temp_dir, exist_ok=True)
        list_file_path = os.path.join(temp_dir, f"video_list_{uuid.uuid4()}.txt")
        
        logger.info(f"Creating concat file at {list_file_path}")
        with open(list_file_path, "w") as f:
            for video_path in video_paths:
                # Use absolute paths to avoid any path issues
                abs_path = os.path.abspath(video_path)
                f.write(f"file '{abs_path}'\n")
                logger.info(f"Added {abs_path} to concat list")
        
        # Verify the list file was created and has content
        if not os.path.exists(list_file_path) or os.path.getsize(list_file_path) == 0:
            logger.error(f"Failed to create concat list file or file is empty")
            return False
            
        # Use FFmpeg to combine the videos
        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output file if it exists
            "-f", "concat",
            "-safe", "0",
            "-i", list_file_path,
            "-c", "copy",  # Copy streams without re-encoding
            output_path
        ]
        
        logger.info(f"Running FFmpeg command: {' '.join(cmd)}")
        
        # Run the FFmpeg command
        process = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Check if the command was successful
        if process.returncode != 0:
            logger.error(f"FFmpeg error: {process.stderr}")
            return False
        
        # Verify the output file was created and has content
        if not os.path.exists(output_path):
            logger.error(f"Output file was not created: {output_path}")
            return False
        if os.path.getsize(output_path) == 0:
            logger.error(f"Output file is empty: {output_path}")
            return False
            
        logger.info(f"Successfully combined videos into {output_path}")
        return True
    except Exception as e:
        logger.error(f"Error combining videos: {str(e)}")
        return False
    finally:
        # Clean up the temporary file
        if list_file_path and os.path.exists(list_file_path):
            try:
                os.remove(list_file_path)
                logger.info(f"Removed temporary file: {list_file_path}")
            except Exception as e:
                logger.warning(f"Failed to remove temporary file {list_file_path}: {str(e)}")

async def combine_videos_from_urls(video_urls: List[str], output_dir: str = "combined_generated_videos") -> Dict[str, Any]:
    """
    Download videos from URLs and combine them into a single video.
    
    Args:
        video_urls: List of URLs of the videos to combine
        output_dir: Directory where the combined video should be saved
        
    Returns:
        Dict containing success status, path to the combined video, and any error message
    """
    video_paths = []
    list_file_path = None
    
    try:
        # Generate a unique identifier for this batch of videos
        batch_id = str(uuid.uuid4())[:8]
        
        # Create a dedicated folder for this batch of videos
        videos_dir = os.path.abspath(f"downloaded_videos/batch_{batch_id}")
        os.makedirs(videos_dir, exist_ok=True)
        logger.info(f"Created directory for downloaded videos: {videos_dir}")
        
        # Create output directory if it doesn't exist
        output_dir_abs = os.path.abspath(output_dir)
        os.makedirs(output_dir_abs, exist_ok=True)
        
        # Create temp directory if it doesn't exist
        temp_dir = os.path.abspath("temp")
        os.makedirs(temp_dir, exist_ok=True)
        
        # Generate a unique filename for the combined video
        combined_video_filename = f"combined_{batch_id}.mp4"
        combined_video_path = os.path.join(output_dir_abs, combined_video_filename)
        
        logger.info(f"Starting download of {len(video_urls)} videos for batch {batch_id}")
        
        # Download all videos with sequential naming
        video_paths = []
        for i, url in enumerate(video_urls):
            # Create a sequentially named video file in the dedicated folder
            video_filename = f"video_{i+1:03d}.mp4"
            video_path = os.path.join(videos_dir, video_filename)
            logger.info(f"Downloading video {i+1}/{len(video_urls)} to {video_path}")
            
            success = await download_video(url, video_path)
            
            if not success:
                logger.error(f"Failed to download video {i+1} from URL: {url}")
                return {
                    "success": False,
                    "error": f"Failed to download video {i+1} from URL: {url}"
                }
            
            # Verify the file exists and has content
            if not os.path.exists(video_path) or os.path.getsize(video_path) == 0:
                logger.error(f"Downloaded video file {video_path} is missing or empty")
                return {
                    "success": False,
                    "error": f"Downloaded video file {i+1} is missing or empty"
                }
                
            video_paths.append(video_path)
            logger.info(f"Successfully downloaded video {i+1}/{len(video_urls)}")
        
        logger.info(f"All videos downloaded. Creating file list for FFmpeg")
        
        # Create a temporary file listing all videos to combine
        list_file_path = os.path.join(temp_dir, f"video_list_{batch_id}.txt")
        with open(list_file_path, "w") as f:
            for video_path in video_paths:
                # Use absolute paths to avoid any path issues
                abs_path = os.path.abspath(video_path)
                f.write(f"file '{abs_path}'\n")
                logger.info(f"Added {abs_path} to concat list")
        
        logger.info(f"Starting FFmpeg to combine videos into {combined_video_path}")
        
        # Combine the videos
        success = await combine_videos(video_paths, combined_video_path)
        
        if not success:
            logger.error("Failed to combine videos with FFmpeg")
            return {
                "success": False,
                "error": "Failed to combine videos"
            }
        
        # Return the result
        logger.info(f"Successfully combined videos into {combined_video_path}")
        return {
            "success": True,
            "combined_video_path": combined_video_path,
            "download_url": f"/download/{os.path.basename(combined_video_path)}",
            "videos_directory": videos_dir,
            "video_count": len(video_paths)
        }
    except Exception as e:
        logger.error(f"Error combining videos from URLs: {str(e)}")
        return {
            "success": False,
            "error": f"Error combining videos: {str(e)}"
        }
    finally:
        # Clean up only the temporary list file
        logger.info("Cleaning up temporary files")
        if list_file_path and os.path.exists(list_file_path):
            os.remove(list_file_path)
            logger.info(f"Removed temporary file list: {list_file_path}")
            
        # We're keeping all downloaded videos in the dedicated folder
        # No need to remove them
