#!/usr/bin/env python3
"""
Amazon Product Scraper for n8n AI Agents

This script provides a simple function to scrape product details from an Amazon URL.
It can be used directly in n8n AI agents to extract product information.
"""

import re
import json
import requests
from bs4 import BeautifulSoup

def scrape_amazon_product(url):
    """
    Scrape product details from an Amazon product URL.
    
    Args:
        url (str): Amazon product URL
        
    Returns:
        dict: Dictionary containing product details
    """
    # Set up headers to mimic a browser
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/91.0.4472.124 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
    
    try:
        # Send request to Amazon
        response = requests.get(url, headers=headers, timeout=10)
        
        # Check if request was successful
        if response.status_code != 200:
            return {
                "success": False,
                "error": f"Failed to fetch page. Status code: {response.status_code}"
            }
        
        # Parse HTML content
        soup = BeautifulSoup(response.content, "html.parser")
        
        # Helper function to extract text from selectors
        def extract_text(selector):
            element = soup.select_one(selector)
            return element.get_text(strip=True) if element else None
        
        # Extract product details
        product = {
            "success": True,
            "title": extract_text("#productTitle"),
            "price": extract_text(".a-price .a-offscreen") or extract_text(".a-color-price"),
            "rating": extract_text("span.a-icon-alt"),
            "reviews_count": extract_text("#acrCustomerReviewText"),
            "availability": extract_text("#availability .a-declarative, #availability span"),
            "brand": extract_text("#bylineInfo"),
            "features": []
        }
        
        # Extract bullet points/features
        for feature in soup.select("#feature-bullets li span.a-list-item"):
            text = feature.get_text(strip=True)
            if text and text != "":
                product["features"].append(text)
        
        # Extract product description
        product["description"] = extract_text("#productDescription p") or extract_text("#productDescription")
        
        # Extract product details table
        product["details"] = {}
        for row in soup.select("#productDetails_techSpec_section_1 tr, #productDetails_detailBullets_sections1 tr, #detailBullets_feature_div li"):
            if row.name == "li":
                # Handle detail bullets format
                text = row.get_text(strip=True)
                if ":" in text:
                    key, value = text.split(":", 1)
                    product["details"][key.strip()] = value.strip()
            else:
                # Handle table format
                heading = row.select_one("th, td")
                value = row.select("td")
                if heading and value:
                    product["details"][heading.get_text(strip=True)] = value[-1].get_text(strip=True)
        
        # Extract images
        product["images"] = []
        
        # Try to get images from image gallery
        image_data_script = soup.find("script", text=re.compile("ImageBlockATF"))
        if image_data_script:
            image_matches = re.findall(r'"hiRes":"(https[^"]+)"', image_data_script.string)
            product["images"] = list(set(image_matches))  # remove duplicates
        
        # If no images found, try alternate method
        if not product["images"]:
            for img in soup.select("#imgTagWrapperId img, #imageBlock img.a-dynamic-image"):
                src = img.get("src") or img.get("data-old-hires") or img.get("data-a-dynamic-image")
                if src and "data-a-dynamic-image" in img.attrs:
                    # Extract image URLs from data-a-dynamic-image attribute
                    try:
                        image_data = json.loads(src)
                        product["images"].extend(list(image_data.keys()))
                    except:
                        pass
                elif src:
                    product["images"].append(src)
        
        # Clean up image URLs
        product["images"] = [url for url in product["images"] if url.startswith("http")]
        
        return product
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error scraping product: {str(e)}"
        }

# Example usage for n8n AI agent
def main(params):
    """
    Main function for n8n AI agent.
    
    Args:
        params (dict): Parameters from n8n
        
    Returns:
        dict: Scraped product details
    """
    # Get URL from parameters
    url = params.get("url")
    
    # Validate URL
    if not url:
        return {
            "success": False,
            "error": "No URL provided"
        }
    
    if not url.startswith("https://www.amazon."):
        return {
            "success": False,
            "error": "Not a valid Amazon URL"
        }
    
    # Scrape product details
    return scrape_amazon_product(url)

# Example of how to use this in n8n AI agent:
"""
// Input in n8n AI agent
const url = "https://www.amazon.com/product-url";
const result = await runPython(`
import json
from amazon_scraper import main

# Pass parameters to the main function
result = main({"url": "${url}"})

# Return the result as JSON
print(json.dumps(result))
`);

// Parse the result
const productDetails = JSON.parse(result);
return productDetails;
"""

if __name__ == "__main__":
    # This allows testing the script directly
    import sys
    
    if len(sys.argv) > 1:
        url = sys.argv[1]
        result = scrape_amazon_product(url)
        print(json.dumps(result, indent=2))
    else:
        print("Please provide an Amazon URL as an argument")
        print("Example: python amazon_scraper.py https://www.amazon.com/product-url")
