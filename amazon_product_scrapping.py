import requests
from bs4 import BeautifulSoup
import re
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import nest_asyncio
from pyngrok import ngrok
import os

# Initialize FastAPI app
app = FastAPI(title="Amazon Product Scraper API", description="API for scraping Amazon product details")

class ProductRequest(BaseModel):
    url: str


def get_amazon_product_details(url):
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


@app.get("/")
def read_root():
    return {"message": "Welcome to Amazon Product Scraper API", 
            "endpoints": {
                "/scrape": "POST - Scrape product details from an Amazon URL"
            }}


@app.post("/scrape")
def scrape_product(request: ProductRequest):
    try:
        product_data = get_amazon_product_details(request.url)
        if "error" in product_data:
            raise HTTPException(status_code=400, detail=product_data["error"])
        return product_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def start_server():
    # Set up ngrok
    port = 8000
    public_url = ngrok.connect(port).public_url
    print(f"\nNgrok tunnel established at: {public_url}")
    print(f"Public API URL: {public_url}/scrape")
    
    # Apply nest_asyncio to allow running asyncio in Jupyter notebooks if needed
    nest_asyncio.apply()
    
    # Start the FastAPI server
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    start_server()
