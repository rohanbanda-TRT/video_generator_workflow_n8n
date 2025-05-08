# Video Script Generator

This project provides a script writing agent that generates 30-second video scripts for products. The agent analyzes product data, including images, and creates scene-by-scene scripts with image prompts, video prompts, and narration text. The implementation uses LangChain and OpenAI's GPT-4o model for advanced image analysis and script generation.

## Features

- Product image analysis using OpenAI's GPT-4o vision capabilities
- Script generation using LangChain
- Scene-by-scene script output in JSON format
- Streamlit web interface for easy interaction

## Components

1. **Script Writer Agent**: Generates creative scripts based on product data
2. **Image Analysis Tool**: Analyzes product images using OpenAI's GPT-4o vision capabilities
3. **Streamlit Interface**: Web-based UI for entering product details and viewing generated scripts

## Setup

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Set up environment variables in the `.env` file:
   ```
   OPENAI_API_KEY=your-openai-api-key-here
   ```
   

## Usage

### Running the Streamlit Web Interface

```bash
streamlit run streamlit_app.py
```

This will start the Streamlit web interface where you can enter product details, add image URLs, and generate scripts.

### Testing the Script Writer Agent Directly

```bash
python test_script_writer.py
```

This will run a command-line interface for testing the script writer agent directly.

## Output Format

The script writer generates output in the following JSON format:

```json
{
  "product_name": "Product Name",
  "video_duration": "30 seconds",
  "scenes": [
    {
      "scene_number": 1,
      "duration_seconds": 3,
      "scene_description": "Brief description of the scene",
      "image_prompt": "Detailed prompt for image generation",
      "video_prompt": "Instructions for video shooting/editing",
      "narration": "Script text for this scene"
    }
  ]
}
```

## Customization

You can customize the script generation by modifying the prompt templates in `app/agents/script_writer_agent.py`.
