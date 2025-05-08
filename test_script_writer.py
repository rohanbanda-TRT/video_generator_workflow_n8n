import os
import sys
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.agents.script_writer_agent import script_writer_agent

def test_script_writer():
    """
    Test the script writer agent with an interactive conversation flow.
    """
    print("\n=== Script Writer Agent - 30-Second Product Demo Script Generator ===\n")
    print("Welcome! I'll help you create a 30-second video script for your product.")
    print("You can chat with me naturally. Type 'exit' at any time to quit.\n")
    print("If you provide JSON data, I'll extract the relevant information automatically.\n")
    
    # Initialize conversation session
    session_messages = []
    
    # Start conversation loop
    while True:
        # Get user input
        print("You: ", end="")
        user_input = ""
        
        # Support multi-line input for JSON
        while True:
            line = input().strip()
            if not line and user_input:
                break  # Empty line after content ends input
            user_input += line + "\n"
        
        user_input = user_input.strip()
        
        # Check for exit command
        if user_input.lower() in ["exit", "quit", "q"]:
            print("\nThank you for using the Script Writer Agent. Goodbye!")
            break
        
        # Try to parse as JSON if it looks like JSON
        if user_input.startswith("{") and user_input.endswith("}"):
            try:
                parsed_json = json.loads(user_input)
                print("\nDetected JSON input. Extracting product information...\n")
            except json.JSONDecodeError:
                # Not valid JSON, that's okay
                pass
        
        # Add user message to session
        session_messages.append({"content": user_input, "role": "user"})
    
        # Invoke the script writer agent
        try:
            result = script_writer_agent.invoke({"messages": session_messages})
            
            # Extract the output from the result
            output = result.get("output", "")
            
            # Add AI response to session
            session_messages.append({"content": output, "role": "assistant"})
            
            # Print AI response
            print(f"\nAgent: {output}\n")
            
            # Try to parse as JSON if it looks like JSON
            if output.strip().startswith("{") and output.strip().endswith("}"):
                try:
                    script_json = json.loads(output)
                    print("\n=== Formatted Script ===\n")
                    
                    # Print formatted script
                    if "product_name" in script_json:
                        print(f"Product: {script_json['product_name']}")
                    if "video_duration" in script_json:
                        print(f"Duration: {script_json['video_duration']}")
                    
                    # Print scenes
                    if "scenes" in script_json:
                        for scene in script_json["scenes"]:
                            scene_num = scene.get("scene_number", "")
                            duration = scene.get("duration_seconds", "")
                            print(f"\nScene {scene_num} - {duration}s")
                            print(f"Description: {scene.get('scene_description', '')}")
                            print(f"Image Prompt: {scene.get('image_prompt', '')}")
                            print(f"Video Prompt: {scene.get('video_prompt', '')}")
                            print(f"Narration: {scene.get('narration', '')}")
                except json.JSONDecodeError:
                    # Not valid JSON, that's okay - it's conversational
                    pass
        except Exception as e:
            print(f"\nError: {str(e)}")

if __name__ == "__main__":
    test_script_writer()
