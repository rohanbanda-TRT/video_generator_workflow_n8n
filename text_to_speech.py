#!/usr/bin/env python3
"""
Text to speech utility script using OpenAI's API.

This script generates audio from text using OpenAI's text-to-speech API.
"""

import os
import logging
import uuid
from typing import Dict, Any, Optional
import requests
from openai import OpenAI

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def generate_audio_from_text(
    text: str, 
    voice: str = "alloy", 
    model: str = "tts-1",
    output_path: Optional[str] = None,
    output_format: str = "mp3",
    speed: float = 0.83,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate audio from text using OpenAI's text-to-speech API.
    
    Args:
        text: The text to convert to speech
        voice: The voice to use (alloy, echo, fable, onyx, nova, shimmer)
        model: The TTS model to use (tts-1, tts-1-hd)
        output_path: Path where the output audio should be saved (optional)
        output_format: Format of the output audio file (mp3, opus, aac, flac)
        speed: Speed of the audio (0.25 to 4.0)
        api_key: OpenAI API key (optional, will use environment variable if not provided)
        
    Returns:
        dict: Dictionary containing success status, output path, and any error message
    """
    try:
        # Validate inputs
        if not text:
            logger.error("No text provided for speech generation")
            return {"success": False, "error": "No text provided for speech generation"}
            
        # Validate voice
        valid_voices = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
        if voice not in valid_voices:
            logger.warning(f"Invalid voice '{voice}', using default 'alloy'")
            voice = "alloy"
            
        # Validate model
        valid_models = ["tts-1", "tts-1-hd"]
        if model not in valid_models:
            logger.warning(f"Invalid model '{model}', using default 'tts-1'")
            model = "tts-1"
            
        # Validate speed
        if speed < 0.25 or speed > 4.0:
            logger.warning(f"Invalid speed '{speed}', using default 1.0")
            speed = 0.83
            
        # Generate output path if not provided
        if output_path is None:
            os.makedirs("temp/audio", exist_ok=True)
            output_path = f"temp/audio/speech_{uuid.uuid4()}.{output_format}"
        else:
            # Ensure output directory exists
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        
        # Initialize OpenAI client
        client = OpenAI(api_key=api_key)  # Will use OPENAI_API_KEY env var if api_key is None
        
        # Generate speech
        logger.info(f"Generating speech for text: {text[:50]}{'...' if len(text) > 50 else ''}")
        
        response = client.audio.speech.create(
            model=model,
            voice=voice,
            input=text,
            speed=speed,
            response_format=output_format
        )
        
        # Save to file
        response.stream_to_file(output_path)
        
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
        
        logger.info(f"Successfully generated audio: {output_path}")
        return {
            "success": True,
            "output_path": output_path,
            "voice": voice,
            "model": model,
            "format": output_format
        }
        
    except Exception as e:
        logger.error(f"Error generating audio from text: {str(e)}")
        return {
            "success": False,
            "error": f"Error generating audio from text: {str(e)}"
        }

def main():
    """Command line interface for text-to-speech generation."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate audio from text using OpenAI's API")
    parser.add_argument("text", help="Text to convert to speech")
    parser.add_argument("-v", "--voice", default="alloy", choices=["alloy", "echo", "fable", "onyx", "nova", "shimmer"], 
                        help="Voice to use")
    parser.add_argument("-m", "--model", default="tts-1", choices=["tts-1", "tts-1-hd"], 
                        help="TTS model to use")
    parser.add_argument("-o", "--output", help="Path where the output audio should be saved")
    parser.add_argument("-f", "--format", default="mp3", choices=["mp3", "opus", "aac", "flac"], 
                        help="Format of the output audio file")
    parser.add_argument("-s", "--speed", type=float, default=1.0, 
                        help="Speed of the audio (0.25 to 4.0)")
    
    args = parser.parse_args()
    
    result = generate_audio_from_text(
        text=args.text,
        voice=args.voice,
        model=args.model,
        output_path=args.output,
        output_format=args.format,
        speed=args.speed
    )
    
    if result["success"]:
        print(f"Successfully generated audio: {result['output_path']}")
    else:
        print(f"Failed to generate audio: {result['error']}")
        exit(1)

if __name__ == "__main__":
    main()
