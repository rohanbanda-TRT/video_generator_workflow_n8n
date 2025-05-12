#!/usr/bin/env python3
"""
Add audio to video utility script.

This script adds an audio file to a video file using FFmpeg.
"""

import os
import subprocess
import argparse
import logging
import uuid

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def add_audio_to_video(video_path: str, audio_path: str, output_path: str = None) -> dict:
    """
    Add audio to a video file using FFmpeg.
    
    Args:
        video_path: Path to the input video file
        audio_path: Path to the audio file to add
        output_path: Path where the output video should be saved (optional)
        
    Returns:
        dict: Dictionary containing success status, output path, and any error message
    """
    try:
        # Verify input files exist
        if not os.path.exists(video_path):
            logger.error(f"Input video does not exist: {video_path}")
            return {"success": False, "error": f"Input video does not exist: {video_path}"}
            
        if not os.path.exists(audio_path):
            logger.error(f"Input audio does not exist: {audio_path}")
            return {"success": False, "error": f"Input audio does not exist: {audio_path}"}
            
        # Generate output path if not provided
        if output_path is None or output_path.strip() == "":
            video_dir = os.path.dirname(video_path)
            video_name = os.path.basename(video_path)
            video_name_without_ext, video_ext = os.path.splitext(video_name)
            output_path = os.path.join(video_dir, f"{video_name_without_ext}_with_audio{video_ext}")
            
        # Ensure output_path is not empty and has a valid extension
        if not output_path or output_path.strip() == "":
            logger.error("Output path is empty")
            return {"success": False, "error": "Output path is empty"}
            
        # Ensure output path has a valid extension
        if not os.path.splitext(output_path)[1]:
            # If no extension, use the same as input video
            _, video_ext = os.path.splitext(video_path)
            output_path = f"{output_path}{video_ext}"
        
        # Ensure output directory exists
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        
        # Use FFmpeg to add audio to the video
        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output file if it exists
            "-i", video_path,  # Input video
            "-i", audio_path,  # Input audio
            "-map", "0:v",  # Use video from first input
            "-map", "1:a",  # Use audio from second input
            "-c:v", "copy",  # Copy video codec without re-encoding
            "-shortest",  # End when the shortest input stream ends
            output_path
        ]
        
        # Log the full command for debugging
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
            return {
                "success": False, 
                "error": f"FFmpeg error: {process.stderr}"
            }
        
        # Verify the output file was created and has content
        if not os.path.exists(output_path):
            logger.error(f"Output file was not created: {output_path}")
            return {
                "success": False, 
                "error": f"Output file was not created: {output_path}"
            }
            
        if os.path.getsize(output_path) == 0:
            logger.error(f"Output file is empty: {output_path}")
            return {
                "success": False, 
                "error": f"Output file is empty: {output_path}"
            }
        
        logger.info(f"Successfully added audio to video: {output_path}")
        return {
            "success": True,
            "output_path": output_path
        }
        
    except Exception as e:
        logger.error(f"Error adding audio to video: {str(e)}")
        return {
            "success": False,
            "error": f"Error adding audio to video: {str(e)}"
        }

def main():
    """Parse command line arguments and run the script."""
    parser = argparse.ArgumentParser(description="Add audio to a video file")
    parser.add_argument("video_path", help="Path to the input video file")
    parser.add_argument("audio_path", help="Path to the audio file to add")
    parser.add_argument("-o", "--output", help="Path where the output video should be saved")
    
    args = parser.parse_args()
    
    result = add_audio_to_video(args.video_path, args.audio_path, args.output)
    
    if result["success"]:
        print(f"Successfully added audio to video: {result['output_path']}")
    else:
        print(f"Failed to add audio to video: {result['error']}")
        exit(1)

if __name__ == "__main__":
    main()
