#!/usr/bin/env python3

import os
import sys
import json
import base64
import argparse
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from openai import OpenAI

# Check if API key is set in environment
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    # try ~/.openai.secret
    try:
        api_key = open(os.path.expanduser("~/.openai.secret")).read().strip()
    except:
        pass
        
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable not set.")
        print("Please set your OpenAI API key with:")
        print("    export OPENAI_API_KEY='your-api-key'")
        sys.exit(1)

client = OpenAI(api_key=api_key)
MODEL = "gpt-image-1"
IMAGE_SIZE = "1536x1024"

# Thread-safe print function
print_lock = threading.Lock()
def safe_print(message):
    with print_lock:
        print(message)

def generate_image(prompt, output_path):
    """Generate an image using OpenAI API and save it to the specified path."""
    try:
        safe_print(f"Generating image: {output_path}")
        
        response = client.images.generate(
            model=MODEL,
            prompt=prompt,
            n=1,
            size=IMAGE_SIZE,
        )
        
        # Decode and save the image
        image_bytes = base64.b64decode(response.data[0].b64_json)
        with open(output_path, "wb") as f:
            f.write(image_bytes)
            
        safe_print(f"Image saved to {output_path}")
        return True
        
    except Exception as e:
        safe_print(f"Error generating image: {str(e)}")
        return False

def generate_edited_image(prompt, base_image_path, output_path):
    """Generate an edited image using an existing image as base."""
    try:
        safe_print(f"Generating edited image: {output_path} based on {base_image_path}")
        
        response = client.images.edit(
            model=MODEL,
            image=open(base_image_path, "rb"),
            prompt=prompt,
        )
        
        # Decode and save the image
        image_bytes = base64.b64decode(response.data[0].b64_json)
        with open(output_path, "wb") as f:
            f.write(image_bytes)
            
        safe_print(f"Edited image saved to {output_path}")
        return True
        
    except Exception as e:
        safe_print(f"Error generating edited image: {str(e)}")
        return False

def process_room(room_dir):
    """Process a single room directory to generate before and after images."""
    prompt_file = os.path.join(room_dir, "img-prompt.json")
    
    # Skip if prompt file doesn't exist
    if not os.path.exists(prompt_file):
        safe_print(f"Skipping {room_dir} - no img-prompt.json found")
        return
    
    # Load the prompt data
    try:
        with open(prompt_file, "r") as f:
            prompt_data = json.load(f)
    except Exception as e:
        safe_print(f"Error reading {prompt_file}: {str(e)}")
        return
    
    # Define output paths
    before_path = os.path.join(room_dir, "before.png")
    after_path = os.path.join(room_dir, "after.png")
    
    # Track whether we generated before image in this run
    before_generated = False
    
    # Generate before image if it doesn't exist
    if not os.path.exists(before_path) and "prompt" in prompt_data:
        before_generated = generate_image(prompt_data["prompt"], before_path)
    else:
        safe_print(f"Skipping {before_path} - file already exists or no prompt")
        before_generated = os.path.exists(before_path)
    
    # Generate after image if it doesn't exist and before image exists
    if not os.path.exists(after_path) and "transform" in prompt_data and before_generated:
        generate_edited_image(prompt_data["transform"], before_path, after_path)
    elif not before_generated and not os.path.exists(after_path) and "transform" in prompt_data:
        safe_print(f"Cannot generate {after_path} - before.png does not exist")
    else:
        safe_print(f"Skipping {after_path} - file already exists or no transform prompt")

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Generate images for rooms based on img-prompt.json files")
    parser.add_argument("-j", "--jobs", type=int, default=1, 
                        help="Number of parallel jobs to run (default: 1)")
    return parser.parse_args()

def main():
    args = parse_args()
    num_jobs = max(1, args.jobs)  # Ensure at least 1 job
    
    # Rooms directory should be in the same directory as this script
    base_dir = os.path.dirname(os.path.abspath(__file__))
    rooms_dir = os.path.join(base_dir, "rooms")
    
    if not os.path.exists(rooms_dir):
        print(f"Error: Rooms directory '{rooms_dir}' not found.")
        sys.exit(1)
    
    # Walk through all room directories
    room_dirs = [os.path.join(rooms_dir, d) for d in os.listdir(rooms_dir) 
                if os.path.isdir(os.path.join(rooms_dir, d))]
    
    if not room_dirs:
        print("No room directories found.")
        sys.exit(1)
    
    print(f"Found {len(room_dirs)} room directories.")
    print(f"Using {num_jobs} parallel jobs for processing.")
    
    # Process rooms in parallel
    with ThreadPoolExecutor(max_workers=num_jobs) as executor:
        # Submit all room processing tasks to the executor
        futures = [executor.submit(process_room, room_dir) for room_dir in room_dirs]
        
        # Wait for all tasks to complete (this happens automatically when exiting the context)
    
    print("Done! Generated images for all rooms.")

if __name__ == "__main__":
    main() 