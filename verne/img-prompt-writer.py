#!/usr/bin/env python3

from openai import OpenAI
import json
import os
import sys
import re

# Check if API key is set in environment
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    # try ~/.openai.secret
    api_key = open(os.path.expanduser("~/.openai.secret")).read().strip()
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable not set.")
        print("Please set your OpenAI API key with:")
        print("    export OPENAI_API_KEY='your-api-key'")
        sys.exit(1)

client = OpenAI(api_key=api_key)
MODEL = "gpt-4.5-preview"

def sanitize_filename(name):
    """Removes potentially problematic characters for filenames."""
    name = re.sub(r'[^\w\s-]', '', name).strip()  # Remove non-alphanumeric (allow whitespace and hyphens)
    name = re.sub(r'[-\s]+', '_', name)  # Replace spaces/hyphens with underscores
    return name

def create_directory(path):
    """Create directory if it doesn't exist."""
    if not os.path.exists(path):
        os.makedirs(path)
        print(f"Created directory: {path}")

def get_image_prompt(room_name, rooms_data):
    """Generate image prompts using OpenAI's API."""
    system_message = (
        "You are a meticulous image prompt creator for a Jules Verne-themed Victorian mansion adventure game. "
        "Your task is to create detailed, descriptive prompts for generating photorealistic images. "
        "Output strictly valid JSON only."
    )
    
    user_message = f"""
    Here's the full data for the rooms in our Victorian Jules Verne-themed mansion:
    
    {json.dumps(rooms_data, indent=2)}
    
    Now, for the room "{room_name}", please give a detailed image generation prompt and a followup prompt to transform the image of the room as required. Be sure to include every element from the entry_text (and then for the transformation, the entry_text_after). Carefully describe the lighting and ambiance for the artist. Start with "Please generate a landscape photorealistic image of a room in a Jules Verne-themed Victorian mansion. Make the lighting dramatic and bright enough for the scene to be clearly visible.". Answer in JSON object {{"prompt": "...", "transform":"..."\}}
    """
    
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ],
            temperature=0.7,
            response_format={"type": "json_object"}
        )
        
        response_content = response.choices[0].message.content
        
        # Verify it's valid JSON
        try:
            return json.loads(response_content)
        except json.JSONDecodeError:
            print(f"Error: Response for room '{room_name}' is not valid JSON.")
            print(f"Raw response: {response_content[:100]}...")
            return {"prompt": "", "transform": ""}
            
    except Exception as e:
        print(f"Error calling OpenAI API for room '{room_name}': {str(e)}")
        return {"prompt": "", "transform": ""}

def main():
    # Check if rooms.json exists
    if not os.path.exists("rooms.json"):
        print("Error: rooms.json file not found.")
        sys.exit(1)
    
    # Read rooms data
    try:
        with open("rooms.json", "r") as f:
            rooms_data = json.load(f)
    except json.JSONDecodeError:
        print("Error: verne/rooms.json is not valid JSON.")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading rooms.json: {str(e)}")
        sys.exit(1)
    
    # Create base directory if it doesn't exist
    create_directory("rooms")
    
    # Process each room in the "rooms" array
    for room in rooms_data["rooms"]:
        room_name = room["id"]
        print(f"Processing room: {room_name}")
        
        # Create directory for the room
        sanitized_name = sanitize_filename(room_name)
        room_dir = f"rooms/{sanitized_name}"
        create_directory(room_dir)
        
        # Generate image prompts
        img_prompt_data = get_image_prompt(room_name, rooms_data)
        
        # Save to file
        output_path = f"{room_dir}/img-prompt.json"
        with open(output_path, "w") as f:
            json.dump(img_prompt_data, f, indent=2)
        
        print(f"Saved image prompts to {output_path}")
    
    print("Done! Image prompts generated for all rooms.")

if __name__ == "__main__":
    main()
