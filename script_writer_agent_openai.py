import os
import uuid
import json
import logging
from typing import Annotated, TypedDict, Dict, List, Any, Optional
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from openai import OpenAI

# Import the Amazon product scraping function
from amazon_product_scrapping import get_amazon_product_details

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
# Define settings class to store API keys
class Settings:
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

settings = Settings()

# Define the scene structure for output
class Scene(TypedDict):
    scene: int
    image_prompt: str
    video_prompt: str
    image_url: str

# Define the state for our LangGraph workflow
class ScriptWriterState(TypedDict):
    """State schema for the script writer graph."""
    messages: Annotated[list[BaseMessage], add_messages]
    product_data: Dict[str, Any]
    image_analyses: Dict[str, str]
    scenes: List[Scene]

# Image analysis function using OpenAI API
def process_multi_images(image_urls: List[str]) -> Dict[str, str]:
    """Process a list of images and return their details sequentially."""
    results = {}
    try:
        openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
        for i, image_url in enumerate(image_urls, start=1):
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Please analyze this image and extract the details. Try to extract features, dimensions, specification and if multiple object is same count it "},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }
            ]
            response = openai_client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                max_tokens=500,
            )
            results[image_url] = response.choices[0].message.content
        logger.info(f"Processed {len(image_urls)} images successfully")
    except Exception as e:
        logger.error(f"Error processing images: {str(e)}")
        results["error"] = str(e)
    return results

# Script writer prompts
SCRIPT_WRITER_SYSTEM_PROMPT = """
You are a professional script writer for product advertisements. 
Your task is to create an engaging script for a product based on the provided details.
Analyze the product information and create a scene-by-scene script that highlights the key features and benefits.
Use the image analyses to incorporate visual elements into your script.

For each scene, provide:
1. A detailed image prompt that can be used to generate a new image for the scene
2. A video prompt describing what should happen in the scene
3. The original image URL that inspired this scene (if applicable)

Your response MUST be a valid JSON object with a 'scenes' key containing an array of scene objects.
Each scene object must have these exact keys: 'scene', 'image_prompt', 'video_prompt', 'image_url'.

Example format:
{{
  "scenes": [
    {{
      "scene": 1,
      "image_prompt": "detailed image generation prompt",
      "video_prompt": "description of what happens in this scene",
      "image_url": "url of original product image"
    }}
  ]
}}
"""

class ScriptWriterAgent:
    """Script Writer Agent implemented using LangGraph."""

    def __init__(self, api_key: str = None):
        """
        Initialize the script writer agent with LangGraph.

        Args:
            api_key: OpenAI API key. If not provided, will try to get from environment.
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key is required. Please provide it or set OPENAI_API_KEY environment variable."
            )

        # Initialize OpenAI client for image analysis
        self.openai_client = OpenAI(api_key=self.api_key)
        
        # Initialize LangChain LLM
        self.llm = ChatOpenAI(
            temperature=0.7, api_key=self.api_key, model="gpt-4o"
        )
        
        # Initialize memory saver
        self.memory = MemorySaver()
        
        # Create the graph
        self.graph = self._create_graph()
        
        logger.info("ScriptWriterAgent initialized with LangGraph implementation")

    def _create_graph(self) -> StateGraph:
        """
        Create the LangGraph for script writing.

        Returns:
            Compiled StateGraph
        """
        # Create the graph builder with our state schema
        graph_builder = StateGraph(ScriptWriterState)

        # Define the image analysis node
        def analyze_images(state: ScriptWriterState) -> Dict[str, Any]:
            """Analyze product images and add analyses to the state."""
            product_data = state["product_data"]
            
            # Get the image URLs from the product data
            image_urls = product_data.get("images", [])
            
            # Limit to first 3 images to avoid excessive API usage
            image_urls = image_urls[:3] if image_urls else []
            
            logger.info(f"Analyzing {len(image_urls)} product images...")
            
            # Analyze images using the OpenAI API
            image_analyses = process_multi_images(image_urls)
            
            # Check for errors
            if "error" in image_analyses:
                logger.error(f"Error in image analysis: {image_analyses['error']}")
            
            # Return updated state with image analyses
            return {"image_analyses": image_analyses}

        # Define the script generation node
        def generate_script(state: ScriptWriterState) -> Dict[str, Any]:
            """Generate a script based on product data and image analyses."""
            product_data = state["product_data"]
            image_analyses = state["image_analyses"]
            
            logger.info("Generating script...")
            
            # Create a prompt for the script writer
            prompt = ChatPromptTemplate.from_messages([
                ("system", SCRIPT_WRITER_SYSTEM_PROMPT),
                ("human", """
                Please create a script for the following product:
                
                Product Title: {title}
                Price: {price}
                Brand: {brand}
                Rating: {rating}
                Description: {description}
                
                Product Details:
                {details}
                
                Image Analyses:
                {image_analyses}
                
                Create a scene-by-scene script with 3-5 scenes that showcases this product effectively.
                """)
            ])
            
            # Format the product details for the prompt
            formatted_details = json.dumps(product_data.get("product_details", {}), indent=2)
            formatted_analyses = "\n\n".join([f"Image: {url}\n{analysis}" 
                                    for url, analysis in image_analyses.items() 
                                    if url != "error"])
            
            # Generate the script
            chain = prompt | self.llm
            response = chain.invoke({
                "title": product_data.get("title", "Unknown Product"),
                "price": product_data.get("price", "N/A"),
                "brand": product_data.get("brand", "N/A"),
                "rating": product_data.get("rating", "N/A"),
                "description": product_data.get("product_description", "No description available"),
                "details": formatted_details,
                "image_analyses": formatted_analyses
            })
            
            # Parse the response to extract the scenes
            scenes = []
            try:
                # Try to extract JSON from the response
                content = response.content
                if isinstance(content, str):
                    # First try to find JSON content by looking for the most complete JSON object
                    import re
                    # Look for JSON objects with the scenes key
                    json_pattern = r'\{[\s\S]*?"scenes"[\s\S]*?\}'
                    json_matches = re.findall(json_pattern, content)
                    
                    # If we found potential JSON matches
                    if json_matches:
                        # Sort by length to try the largest/most complete JSON first
                        json_matches.sort(key=len, reverse=True)
                        
                        for json_str in json_matches:
                            try:
                                # Try to clean up the JSON string
                                # Remove any markdown code block markers
                                clean_json = re.sub(r'```json|```', '', json_str).strip()
                                scenes_data = json.loads(clean_json)
                                if "scenes" in scenes_data and isinstance(scenes_data["scenes"], list):
                                    scenes = scenes_data["scenes"]
                                    logger.info(f"Successfully extracted {len(scenes)} scenes from JSON response")
                                    break
                            except json.JSONDecodeError as e:
                                logger.warning(f"Failed to parse JSON: {e}. Trying next match.")
                                continue
                    
                    # If we still don't have scenes, try a more aggressive approach
                    if not scenes:
                        logger.info("Trying alternative JSON extraction method")
                        # Try to extract just the scenes array
                        scenes_pattern = r'"scenes"\s*:\s*\[(.*?)\]'
                        scenes_match = re.search(scenes_pattern, content, re.DOTALL)
                        
                        if scenes_match:
                            try:
                                # Reconstruct a valid JSON
                                scenes_json = '{"scenes":[' + scenes_match.group(1) + ']}'
                                scenes_data = json.loads(scenes_json)
                                if "scenes" in scenes_data and isinstance(scenes_data["scenes"], list):
                                    scenes = scenes_data["scenes"]
                                    logger.info(f"Extracted {len(scenes)} scenes using alternative method")
                            except json.JSONDecodeError as e:
                                logger.warning(f"Alternative method failed: {e}")
            except Exception as e:
                logger.error(f"Error parsing script response: {e}")
            
            # Create a human-readable message about the script
            message_content = f"I've created a script with {len(scenes)} scenes for {product_data.get('title', 'the product')}."
            
            # Return updated state with the scenes and a message
            return {
                "scenes": scenes,
                "messages": [AIMessage(content=message_content)]
            }

        # Add nodes to the graph
        graph_builder.add_node("analyze_images", analyze_images)
        graph_builder.add_node("generate_script", generate_script)

        # Add edges to the graph
        graph_builder.add_edge(START, "analyze_images")
        graph_builder.add_edge("analyze_images", "generate_script")
        graph_builder.add_edge("generate_script", END)

        # Compile the graph with the memory saver
        return graph_builder.compile(checkpointer=self.memory)

    def generate_script(self, product_data: Dict[str, Any], session_id: str = None) -> Dict[str, Any]:
        """
        Generate a script for a product.

        Args:
            product_data: The product data to generate a script for
            session_id: Optional session ID for conversation persistence
                        If not provided, a new UUID will be generated

        Returns:
            Dictionary containing the generated scenes and any messages
        """
        # Generate a session ID if not provided
        if not session_id:
            session_id = str(uuid.uuid4())
            logger.info(f"Generated new session_id: {session_id}")
        else:
            logger.info(f"Using existing session_id: {session_id}")

        # Set up the config for this session
        config = {"configurable": {"thread_id": session_id}}

        # Initial state with product data and empty messages
        initial_state = {
            "messages": [HumanMessage(content=f"Generate a script for {product_data.get('title', 'this product')}")],
            "product_data": product_data,
            "image_analyses": {},
            "scenes": []
        }

        # Invoke the graph with the initial state
        result = self.graph.invoke(
            initial_state,
            config=config,
        )

        return {
            "scenes": result.get("scenes", []),
            "messages": result.get("messages", [])
        }

    def process_message(self, user_input: str, product_data: Dict[str, Any] = None, session_id: str = None) -> Dict[str, Any]:
        """
        Process a message in the context of script writing.

        Args:
            user_input: The user message to process
            product_data: Optional product data to use for script generation
            session_id: Optional session ID for conversation persistence

        Returns:
            Dictionary containing the response and any generated scenes
        """
        # Generate a session ID if not provided
        if not session_id:
            session_id = str(uuid.uuid4())
            logger.info(f"Generated new session_id: {session_id}")
        else:
            logger.info(f"Using existing session_id: {session_id}")

        # Set up the config for this session
        config = {"configurable": {"thread_id": session_id}}

        # Create a human message
        human_message = HumanMessage(content=user_input)

        # Initial state
        initial_state = {
            "messages": [human_message],
            "product_data": product_data or {},
            "image_analyses": {},
            "scenes": []
        }

        # Invoke the graph with the message
        result = self.graph.invoke(
            initial_state,
            config=config,
        )

        return {
            "scenes": result.get("scenes", []),
            "messages": result.get("messages", [])
        }


def main():
    # Load environment variables
    load_dotenv()
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Please set OPENAI_API_KEY environment variable or enter it now:")
        api_key = input("OpenAI API Key: ").strip()
        if not api_key:
            print("No API key provided. Exiting.")
            return
        os.environ["OPENAI_API_KEY"] = api_key

    # Create the script writer agent
    agent = ScriptWriterAgent(api_key)

    print("\n===== Amazon Product Script Writer =====\n")
    print("This tool generates video scripts for Amazon products.")
    print("It analyzes product data and images to create scene-by-scene scripts.\n")

    # You can either use a URL or provide sample data manually
    use_url = input("Do you want to use an Amazon URL? (yes/no): ").lower() == "yes"

    product_data = None
    if use_url:
        amazon_url = input("Enter Amazon product URL: ")
        print(f"\nFetching product data from {amazon_url}...")
        # Get the product data from the URL
        product_data = get_amazon_product_details(amazon_url)
        if isinstance(product_data, dict) and "error" in product_data:
            print(f"Error: {product_data['error']}")
            return
    else:
        # Sample product data for testing
        print("\nUsing sample product data for testing...")
        product_data = {
            "title": "Example Wireless Headphones",
            "price": "$99.99",
            "brand": "SoundMax",
            "rating": "4.5 out of 5 stars",
            "product_description": "Premium wireless headphones with noise cancellation, 30-hour battery life, and crystal-clear sound quality. Perfect for music lovers, gamers, and professionals.",
            "product_details": {
                "Material": "High-quality aluminum and memory foam",
                "Dimensions": "7.5 x 6.3 x 3.2 inches",
                "Weight": "0.55 pounds",
                "Battery Life": "30 hours",
                "Connectivity": "Bluetooth 5.0",
                "Features": "Active Noise Cancellation, Voice Assistant, Touch Controls"
            },
            "images": [
                "https://m.media-amazon.com/images/I/71rXSVqET9L._AC_SL1500_.jpg",
                "https://m.media-amazon.com/images/I/71nDX36Y9UL._AC_SL1500_.jpg"
            ]
        }

    # Generate the script
    print("\nGenerating script... This may take a few minutes.")
    session_id = str(uuid.uuid4())
    result = agent.generate_script(product_data, session_id)
    scenes = result.get("scenes", [])

    # Print the scenes
    if scenes:
        print("\n===== Generated Script =====\n")
        for scene in scenes:
            print(f"Scene {scene['scene']}:")
            print(f"Image Prompt: {scene['image_prompt']}")
            print(f"Video Prompt: {scene['video_prompt']}")
            print(f"Based on Image: {scene['image_url']}\n")
        
        # Also print as JSON
        print("\n===== JSON Output =====\n")
        print(json.dumps({"scenes": scenes}, indent=2))
    else:
        print("\nNo scenes were generated. Please try again with different product data.")

    # Interactive chat mode
    print("\n===== Interactive Mode =====\n")
    print("You can now chat with the script writer agent to refine the script.")
    print("Type 'q' or 'quit' to exit.")

    while True:
        user_input = input("\nEnter your message (or 'q' to quit): ").strip()

        if user_input.lower() in ["q", "quit"]:
            print("\nExiting script writer.")
            break

        # Process the message
        result = agent.process_message(user_input, product_data, session_id)
        messages = result.get("messages", [])
        scenes = result.get("scenes", [])

        # Print the response
        if messages and len(messages) > 0:
            print(f"\nResponse: {messages[-1].content}")

        # Print any new scenes
        if scenes:
            print("\n===== Updated Script =====\n")
            for scene in scenes:
                print(f"Scene {scene['scene']}:")
                print(f"Image Prompt: {scene['image_prompt']}")
                print(f"Video Prompt: {scene['video_prompt']}")
                print(f"Based on Image: {scene['image_url']}\n")


if __name__ == "__main__":
    main()
