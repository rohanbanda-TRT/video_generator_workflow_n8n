import os
import json
import streamlit as st
from dotenv import load_dotenv
from app.agents.script_writer_agent import script_writer_agent

# Load environment variables
load_dotenv()

# Set page configuration
st.set_page_config(
    page_title="Video Script Generator",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main {
        padding: 2rem;
    }
    .scene-card {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 20px;
    }
    .scene-header {
        font-weight: bold;
        margin-bottom: 10px;
    }
    .stButton>button {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'script' not in st.session_state:
    st.session_state.script = None

# Check if API key is available
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    st.error("OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")
    st.stop()

# Title and description
st.title("🎬 Video Script Generator")
st.markdown("""
Generate a 30-second video shooting script for your product with scene-by-scene breakdown, 
including image prompts, video directions, and narration.

You can either use the form below or chat with our AI assistant to create your script.
""")

# Sidebar
with st.sidebar:
    st.header("About")
    st.markdown("""
    This app uses an AI agent to generate professional video scripts for product marketing.
    
    Each script includes:
    - 3-5 scenes (total 30 seconds)
    - Scene descriptions
    - Image prompts for visuals
    - Video directions (camera angles, movements)
    - Narration text
    """)
    
    st.header("How to use")
    st.markdown("""
    1. Enter product information in the text area
    2. Click "Generate Script"
    3. View and copy the generated script
    """)

# Main content
st.header("Product Information")
st.markdown("Provide details about your product. Include features, benefits, target audience, and any specific aspects you want to highlight.")

# Initialize image_urls in session state if not present
if 'image_urls' not in st.session_state:
    st.session_state.image_urls = [""]

# Function to add more image URL fields
def add_image_url():
    st.session_state.image_urls.append("")
    
# Function to remove an image URL field
def remove_image_url(index):
    if len(st.session_state.image_urls) > 1:  # Keep at least one field
        st.session_state.image_urls.pop(index)

# Image URL management (outside the form)
st.markdown("### Product Images")
st.markdown("Add image URLs to enhance script generation with visual analysis")

# Display image URL inputs with add/remove buttons
col1, col2 = st.columns([5, 1])
with col1:
    for i, url in enumerate(st.session_state.image_urls):
        st.text_input(
            f"Image URL {i+1}",
            value=url,
            key=f"image_url_{i}",
            placeholder="https://example.com/product-image.jpg"
        )

with col2:
    for i in range(len(st.session_state.image_urls)):
        if i > 0:  # Only show remove button if there's more than one field
            if st.button("❌", key=f"remove_{i}"):
                remove_image_url(i)
                st.rerun()
        else:
            st.write("")

if st.button("Add Another Image URL"):
    add_image_url()
    st.rerun()

# Input form
with st.form("script_form"):
    product_info = st.text_area(
        "Product Information",
        height=200,
        placeholder="Example: The XYZ Wireless Earbuds feature 24-hour battery life, active noise cancellation, and water resistance. They're perfect for athletes and commuters who want premium sound quality without wires. Key selling points include the compact charging case and comfortable fit for extended wear."
    )
    
    # Amazon URL option
    use_amazon_url = st.checkbox("Use Amazon product URL instead")
    
    if use_amazon_url:
        amazon_url = st.text_input(
            "Amazon Product URL",
            placeholder="https://www.amazon.com/dp/PRODUCT_ID"
        )
    
    submitted = st.form_submit_button("Generate Script")
    
    if submitted:
        with st.spinner("Generating your script... This may take a minute."):
            if use_amazon_url and amazon_url:
                # Here you would integrate with your Amazon scraping functionality
                # For now, we'll just pass the URL as the product info
                product_info = f"Amazon product URL: {amazon_url}"
            
            # Collect image URLs from session state
            image_urls = []
            for i in range(len(st.session_state.image_urls)):
                url = st.session_state[f"image_url_{i}"]
                if url and url.strip():
                    image_urls.append(url)
            
            # Create a prompt for the script writer agent
            prompt = f"""
            
            {product_info}
        
            """
            
            # Store the image URLs used for this generation
            st.session_state.last_used_image_urls = image_urls.copy() if image_urls else []
            
            # Invoke the script writer agent
            result = script_writer_agent.invoke({"messages": [{"content": prompt, "role": "user"}]})
            
            # Get the output from the result
            script_text = result.get("output", "")
            
            try:
                # Try to parse as JSON
                script_json = json.loads(script_text)
                st.session_state.script = script_json
            except json.JSONDecodeError:
                # If not valid JSON, store as text
                st.session_state.script = {"raw_text": script_text}

# Display generated script
if st.session_state.script:
    st.header("Generated Script")
    
    # Display images used for this generation if any
    if hasattr(st.session_state, 'last_used_image_urls') and st.session_state.last_used_image_urls:
        with st.expander("Images Used for Analysis", expanded=False):
            st.markdown("The following images were analyzed to enhance the script:")
            cols = st.columns(min(3, len(st.session_state.last_used_image_urls)))
            for i, url in enumerate(st.session_state.last_used_image_urls):
                if url.strip():
                    with cols[i % len(cols)]:
                        st.image(url, width=200)
                        st.markdown(f"[Image {i+1}]({url})")
    
    # Check if it's properly formatted JSON
    if "raw_text" in st.session_state.script:
        # Display as raw text if not valid JSON
        st.text_area("Script Output", st.session_state.script["raw_text"], height=400)
    else:
        # Display formatted script
        script = st.session_state.script
        
        # Script metadata
        col1, col2 = st.columns(2)
        with col1:
            st.subheader(f"Product: {script.get('product_name', 'Product')}")
        with col2:
            st.subheader(f"Duration: {script.get('video_duration', '30 seconds')}")
        
        # Scenes
        if "scenes" in script:
            for i, scene in enumerate(script["scenes"]):
                with st.expander(f"Scene {scene.get('scene_number', i+1)} - {scene.get('duration_seconds', '')}s", expanded=True):
                    st.markdown(f"**Description:** {scene.get('scene_description', '')}")
                    st.markdown(f"**Image Prompt:** {scene.get('image_prompt', '')}")
                    st.markdown(f"**Video Prompt:** {scene.get('video_prompt', '')}")
                    st.markdown(f"**Narration:** {scene.get('narration', '')}")
        
        # Download as JSON option
        script_json = json.dumps(script, indent=2)
        st.download_button(
            label="Download Script as JSON",
            data=script_json,
            file_name="video_script.json",
            mime="application/json"
        )

# Chat interface
st.header("Chat with Script Writer Assistant")

# Initialize chat history
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []

# Display chat messages
for message in st.session_state.chat_messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])
        
        # If it's an assistant message with JSON, try to display it nicely
        if message["role"] == "assistant" and message["content"].strip().startswith("{") and message["content"].strip().endswith("}"):
            try:
                script_json = json.loads(message["content"])
                if "scenes" in script_json:
                    st.subheader("Script Preview")
                    for scene in script_json["scenes"]:
                        with st.expander(f"Scene {scene.get('scene_number', '')}"):
                            st.write(f"**Description:** {scene.get('scene_description', '')}")
                            st.write(f"**Image Prompt:** {scene.get('image_prompt', '')}")
                            st.write(f"**Video Prompt:** {scene.get('video_prompt', '')}")
                            st.write(f"**Narration:** {scene.get('narration', '')}")
            except:
                pass

# Chat input
if prompt := st.chat_input("Ask me about creating a script for your product..."):
    # Add user message to chat history
    st.session_state.chat_messages.append({"role": "user", "content": prompt})
    
    # Display user message
    with st.chat_message("user"):
        st.write(prompt)
    
    # Display assistant response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            # Prepare messages for the agent
            messages = [{"role": msg["role"], "content": msg["content"]} for msg in st.session_state.chat_messages]
            
            # Call the agent
            result = script_writer_agent.invoke({"messages": messages})
            response = result.get("output", "I'm having trouble generating a response.")
            
            # Display the response
            st.write(response)
            
            # Add assistant response to chat history
            st.session_state.chat_messages.append({"role": "assistant", "content": response})
            
            # Try to parse as JSON for better display
            if response.strip().startswith("{") and response.strip().endswith("}"):
                try:
                    script_json = json.loads(response)
                    if "scenes" in script_json:
                        st.subheader("Script Preview")
                        for scene in script_json["scenes"]:
                            with st.expander(f"Scene {scene.get('scene_number', '')}"):
                                st.write(f"**Description:** {scene.get('scene_description', '')}")
                                st.write(f"**Image Prompt:** {scene.get('image_prompt', '')}")
                                st.write(f"**Video Prompt:** {scene.get('video_prompt', '')}")
                                st.write(f"**Narration:** {scene.get('narration', '')}")
                except:
                    pass

# Footer
st.markdown("---")
st.markdown("Powered by AI Script Generator")
