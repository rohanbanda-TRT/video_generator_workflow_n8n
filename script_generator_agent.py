import os
import uuid
import logging
from typing import Annotated, TypedDict, Dict, Any, Optional, List
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from openai import OpenAI
from langchain.tools import tool

from prompts.script_generator import SCRIPT_GENERATOR_PROMPT

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Image processing tool
@tool
def process_multi_images(image_urls: List[str]) -> Dict[str, str]:
    """Process a list of images and return their details sequentially."""
    results = {}
    try:
        openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        for i, image_url in enumerate(image_urls, start=1):
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Please analyze this image and extract the details. Try to extract features, dimensions, specifications and if multiple objects are the same, count them."},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }
            ]
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                max_tokens=500,
            )
            results[f"Image Detail {i}"] = response.choices[0].message.content
        logger.info(f"Processed {len(image_urls)} images successfully")
    except Exception as e:
        logger.error(f"Error processing images: {str(e)}")
        results["error"] = str(e)
    return results


class ScriptGeneratorState(TypedDict):
    """State schema for the script generator graph."""

    messages: Annotated[list[BaseMessage], add_messages]


class ScriptGeneratorAgent:
    """Script Generator Agent implemented using LangGraph.
    
    This agent generates 30-second video shooting scripts for products
    based on user input, with scene-by-scene breakdown including image
    and video prompts.
    """

    def __init__(self, api_key: str = None):
        """
        Initialize the script generator agent with LangGraph.

        Args:
            api_key: OpenAI API key. If not provided, will try to get from environment.
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key is required. Please provide it or set OPENAI_API_KEY environment variable."
            )

        # Using gpt-4o-mini for better script generation quality
        self.llm = ChatOpenAI(
            temperature=0.7, api_key=self.api_key, model="gpt-4o-mini"
        )
        self.memory = MemorySaver()
        self.graph = self._create_graph()
        logger.info("ScriptGeneratorAgent initialized with LangGraph implementation")

    def _create_graph(self) -> StateGraph:
        """
        Create the LangGraph for script generation.

        Returns:
            Compiled StateGraph
        """
        # Create the graph builder with our state schema
        graph_builder = StateGraph(ScriptGeneratorState)

        # Define the script generator node with tool access
        def script_generator(state: ScriptGeneratorState) -> Dict[str, Any]:
            """Process messages and generate video script."""
            # Format system message with the script generator prompt
            system_message = {"role": "system", "content": SCRIPT_GENERATOR_PROMPT}

            # Prepare messages for the LLM
            messages = [system_message] + [
                {"role": m.type, "content": m.content} for m in state["messages"]
            ]

            # Call the LLM with access to the image processing tool
            # The LLM will detect image URLs in the input and use the tool as needed
            response = self.llm.invoke(messages, tools=[process_multi_images])

            # Return updated state with the new AI message
            return {"messages": [response]}

        # Add the node to the graph
        graph_builder.add_node("script_generator", script_generator)

        # Add edges
        graph_builder.add_edge(START, "script_generator")
        graph_builder.add_edge("script_generator", END)

        # Compile the graph with the memory saver
        return graph_builder.compile(checkpointer=self.memory)

    def generate_script(self, product_info: str, image_urls: List[str] = None, session_id: str = None) -> str:
        """
        Generate a 30-second video shooting script for a product.

        Args:
            product_info: Information about the product for script generation
            image_urls: Optional list of image URLs to analyze
            session_id: Optional session ID for conversation persistence
                        If not provided, a new UUID will be generated

        Returns:
            Generated script in JSON format
        """
        # Generate a session ID if not provided
        if not session_id:
            session_id = str(uuid.uuid4())
            logger.info(f"Generated new session_id: {session_id}")
        else:
            logger.info(f"Using existing session_id: {session_id}")

        # If image URLs are provided, include them in the product info
        if image_urls and len(image_urls) > 0:
            # Add image URLs to the product info
            enhanced_product_info = product_info + "\n\nProduct Images:\n"
            for i, url in enumerate(image_urls, 1):
                enhanced_product_info += f"\nImage {i}: {url}"
            logger.info(f"Added {len(image_urls)} image URLs to product info")
        else:
            enhanced_product_info = product_info

        # Create a human message with the enhanced product information
        human_message = HumanMessage(content=enhanced_product_info)

        # Set up the config for this session
        config = {"configurable": {"thread_id": session_id}}

        # Invoke the graph with the message
        result = self.graph.invoke(
            {"messages": [human_message]},
            config=config,
        )

        # Extract and return the response content
        if result and "messages" in result and len(result["messages"]) > 0:
            # Get the last message (the response)
            last_message = result["messages"][-1]
            if isinstance(last_message, AIMessage):
                return last_message.content

        logger.warning("Failed to generate script")
        return "Sorry, I couldn't generate a script for this product."


def main():
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("Please set OPENAI_API_KEY environment variable")

    agent = ScriptGeneratorAgent(api_key)

    print("Script Generator started! Type 'q' or 'quit' to exit.")
    session_id = str(uuid.uuid4())
    print(f"Session ID: {session_id}")

    while True:
        user_input = input("\nEnter product information: ").strip()

        if user_input.lower() in ["q", "quit"]:
            print("\nScript Generator ended.")
            break

        print("\nGenerating script...")
        response = agent.generate_script(user_input, session_id)
        print("\nGenerated Script:")
        print(response)


if __name__ == "__main__":
    main()
