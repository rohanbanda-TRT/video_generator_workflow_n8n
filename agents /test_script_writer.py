import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.agents.script_writer_agent import script_writer_agent

def test_script_writer():
    """
    Test the script writer agent with user input for image URLs and product details.
    """
    print("\n=== Script Writer Agent - 30-Second Product Demo Script Generator ===\n")
    
    # Get image URLs from user
    print("Enter image URLs (one per line, press Enter twice when done):")
    image_urls = []
    while True:
        url = input().strip()
        if not url:
            break
        image_urls.append(url)
    
    # If no URLs provided, use sample URLs
    if not image_urls:
        print("\nNo image URLs provided. Using sample images of a car...")
        image_urls = [
            "https://images.unsplash.com/photo-1533473359331-0135ef1b58bf?q=80&w=1470&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1494976388531-d1058494cdd8?q=80&w=1470&auto=format&fit=crop"
        ]
    
    # Get product details from user
    print("\nEnter product description (e.g., 'luxury sports car'):")
    product_description = input().strip() or "luxury product"
    
    print("\nEnter target audience (e.g., 'affluent car enthusiasts aged 30-55'):")
    target_audience = input().strip() or "potential customers"
    
    print("\nEnter key selling points (comma separated, e.g., 'powerful engine, sleek design, safety features'):")
    key_selling_points = input().strip() or "quality, performance, value"
    
    # Create a prompt for the script writer agent
    prompt = f"""
    I need a 30-second product demo script for the product shown in these images:
    {image_urls}
    
    The product is a {product_description}.
    Target audience: {target_audience}.
    Key selling points: {key_selling_points}.
    """
    
    # Invoke the script writer agent
    result = script_writer_agent.invoke({"messages": [{"content": prompt, "role": "user"}]})
    
    # Print the generated script
    print("\n=== Generated 30-Second Product Demo Script ===\n")
    print(result["output"])
    print("\n=================================================\n")

if __name__ == "__main__":
    test_script_writer()
