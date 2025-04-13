#!/usr/bin/env python3

from openai import OpenAI
import os
import json
import re # Add import for sanitizing filenames
import sys

# Check if API key is set in environment 
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("Error: OPENAI_API_KEY environment variable not set.")
    print("Please set your OpenAI API key with:")
    print("    export OPENAI_API_KEY='your-api-key'")
    sys.exit(1)

client = OpenAI(api_key=api_key)

#CREATIVE_MODEL = "gpt-4.5-preview"
#LOGICAL_MODEL = "o1"
CREATIVE_MODEL = "gpt-4o"
LOGICAL_MODEL = "gpt-4o"

# -------------------------------------------------------------------
#  Helper function to send messages to the OpenAI ChatCompletion API.
# -------------------------------------------------------------------
def sanitize_filename(name):
    """Removes potentially problematic characters for filenames."""
    name = re.sub(r'[^\w\s-]', '', name).strip() # Remove non-alphanumeric (allow whitespace and hyphens)
    name = re.sub(r'[-\s]+', '_', name) # Replace spaces/hyphens with underscores
    return name

def create_chat_completion(messages, model=CREATIVE_MODEL, temperature=0.7, log_file_base=None, step_name=""):
    """
    messages: a list of dicts, e.g. [{"role": "system", "content": "..."}]
    model: the model name ("gpt-4o")
    temperature: you may adjust for more/less creativity
    log_file_base: Base path for the log file (e.g., "artifacts/room_def/Study"). Extension ".chat" will be added.
    step_name: A descriptive name for the step being logged.
    Returns the message content string from the assistant.
    """
    log_file_path = None
    if log_file_base:
        log_file_path = f"{log_file_base}.chat"
        log_dir = os.path.dirname(log_file_path)
        if log_dir: # Avoid error if log_file_base has no directory part
             os.makedirs(log_dir, exist_ok=True)
        print(f"Querying {step_name} for {log_file_path}...")

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            response_format={"type": "json_object"}
        )
        response_content = response.choices[0].message.content
        usage = response.usage

        if log_file_path:
            try:
                with open(log_file_path, "w") as f:
                    f.write(f"# Step: {step_name}\n")
                    f.write(f"# Model: {model}\n")
                    f.write(f"# Temperature: {temperature}\n\n")

                    system_message = next((m['content'] for m in messages if m['role'] == 'system'), "N/A")
                    user_message = next((m['content'] for m in messages if m['role'] == 'user'), "N/A")

                    f.write("## System Message ##\n")
                    f.write(f"{system_message}\n\n")

                    f.write("## User Message ##\n")
                    f.write(f"{user_message}\n\n")

                    f.write("---------- RESPONSE ----------\n\n")
                    f.write("## Assistant Message ##\n")
                    f.write(f"{response_content}\n\n")

                    f.write("---------- USAGE ----------\n")
                    f.write(f"Prompt Tokens: {usage.prompt_tokens}\n")
                    f.write(f"Completion Tokens: {usage.completion_tokens}\n")
                    f.write(f"Total Tokens: {usage.total_tokens}\n")

                print(f"Received response for {step_name}, saved to {log_file_path}. Input: {usage.prompt_tokens}, Output: {usage.completion_tokens}")
            except IOError as e:
                print(f"Error writing log file {log_file_path}: {e}")
            except Exception as e:
                print(f"An unexpected error occurred during logging for {step_name}: {e}")

        # Verify that the response is valid JSON before returning
        try:
            json.loads(response_content)
        except json.JSONDecodeError:
            print(f"Warning: Response for {step_name} is not valid JSON. Attempting to fix...")
            # Attempt to extract JSON from the response if it's wrapped in markdown or has extra text
            potential_json = extract_json_from_response(response_content)
            if potential_json:
                return potential_json
            print(f"Error: Could not extract valid JSON from response for {step_name}")
            print(f"Raw response: {response_content[:100]}...")
            sys.exit(1)
            
        return response_content
    
    except Exception as e:
        print(f"Error calling OpenAI API for {step_name}: {str(e)}")
        print("Make sure your API key is valid and the model name is correct.")
        sys.exit(1)

def extract_json_from_response(text):
    """
    Attempts to extract JSON from a text response that might contain additional text
    or markdown formatting.
    """
    # Try to find content between JSON code blocks
    json_block_pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
    match = re.search(json_block_pattern, text)
    if match:
        potential_json = match.group(1)
        try:
            return json.dumps(json.loads(potential_json))
        except json.JSONDecodeError:
            pass
    
    # Look for text that starts with { and ends with }
    json_pattern = r"(\{[\s\S]*\})"
    match = re.search(json_pattern, text)
    if match:
        potential_json = match.group(1)
        try:
            return json.dumps(json.loads(potential_json))
        except json.JSONDecodeError:
            pass
    
    return None

# -------------------------------------------------------------------
# 1. Game Structure Planner LLM
#    Model: gpt-4o (creative layout)
# -------------------------------------------------------------------
def game_structure_planner(user_prompt):
    """
    Generates a structured overview of the mansion layout, 
    returning JSON describing rooms and connections.
    """
    system_instructions = (
        "You are an expert game-designer assistant. "
        "You will produce JSON only—no extra commentary or markdown formatting. "
        "Your job is to output a structured overview of a mansion layout suitable for a puzzle-adventure game. "
        "Your response must be valid, parseable JSON."
    )
    user_request = f"""
    Generate a structured overview of a mansion layout for a puzzle-adventure game based on:
    {user_prompt}
    
    Requirements:
    - 8 to 12 rooms
    - Each room has a name, a theme, and connections to other rooms
    - Include locked doors or secret passages where appropriate
    - Output valid JSON only
    """
    messages = [
        {"role": "system", "content": system_instructions},
        {"role": "user", "content": user_request}
    ]
    log_base = os.path.join("artifacts", "mansion_structure")
    response = create_chat_completion(
        messages,
        model=CREATIVE_MODEL,
        log_file_base=log_base,
        step_name="Game Structure Planning"
    )
    return json.loads(response)

# -------------------------------------------------------------------
# 2. Room Definition LLM (run in parallel for each room)
#    Model: gpt-4o (creative detailing)
# -------------------------------------------------------------------
def define_room(room_name, theme_description):
    """
    Expands on a single room by listing interactable objects, 
    entry/exit points, secrets, etc., returning JSON.
    """
    system_instructions = (
        "You are an expert puzzle-adventure designer. "
        "Produce valid JSON only—no additional text or markdown. "
        "Your response must be parseable as valid JSON."
    )
    user_request = f"""
    Expand the mansion room labeled "{room_name}" with theme "{theme_description}".
    Provide a JSON structure containing:
    - "interactable_objects": array of objects/furniture
    - "entry_exit_points": array of doorways/locks/passages
    - "hidden_mechanics": array of any hidden features or special interactive elements
    """
    messages = [
        {"role": "system", "content": system_instructions},
        {"role": "user", "content": user_request}
    ]
    sanitized_room_name = sanitize_filename(room_name)
    log_base = os.path.join("artifacts", "room_definition", sanitized_room_name)
    response = create_chat_completion(
        messages,
        model=CREATIVE_MODEL,
        log_file_base=log_base,
        step_name=f"Room Definition ({room_name})"
    )
    return json.loads(response)

# -------------------------------------------------------------------
# 3. Puzzle Generator LLM
#    Model: gpt-4o (creative puzzle design)
# -------------------------------------------------------------------
def generate_puzzle(object_name, room_name):
    """
    Creates a puzzle scenario around a specific object in a room.
    Returns puzzle details in JSON form.
    """
    system_instructions = (
        "You are a puzzle-design specialist. "
        "Output puzzle details in valid JSON only—no extra text, explanations, or markdown. "
        "Your entire response must be valid JSON."
    )
    user_request = f"""
    Design a puzzle involving the object "{object_name}" in room "{room_name}".
    Provide:
    - "puzzle_setup": how it appears or is discovered
    - "interactions": steps required to solve it
    - "logic": numeric/symbolic/logic pattern
    - "solution": the final unlocking or reveal
    - "reward": outcome of solving
    Output valid JSON only.
    """
    messages = [
        {"role": "system", "content": system_instructions},
        {"role": "user", "content": user_request}
    ]
    sanitized_room_name = sanitize_filename(room_name)
    sanitized_object_name = sanitize_filename(object_name)
    log_base = os.path.join("artifacts", "puzzle", f"{sanitized_room_name}_{sanitized_object_name}")
    response = create_chat_completion(
        messages,
        model=CREATIVE_MODEL,
        log_file_base=log_base,
        step_name=f"Puzzle Generation ({room_name} - {object_name})"
    )
    return json.loads(response)

# -------------------------------------------------------------------
# 4. Clue Generator LLM
#    Model: gpt-4o (creative but subtle clue writing)
# -------------------------------------------------------------------
def generate_clues(object_name, room_name, puzzle_details):
    """
    Generates subtle hints or clues for the puzzle, possibly 
    placed in different rooms. Returns JSON with 2-4 clue entries.
    """
    system_instructions = (
        "You are an expert in designing subtle puzzle clues. "
        "Output valid JSON only—no additional explanations, text, or markdown. "
        "Your complete response must be parseable as proper JSON."
    )
    user_request = f"""
    Based on the puzzle for the object "{object_name}" in room "{room_name}", 
    create 2-4 subtle clues that guide the player without solving it outright.
    For each clue, specify:
    - "location": where it is found
    - "form": note, inscription, scratchings, etc.
    - "hint_text": the subtle hint
    
    Puzzle details:
    {json.dumps(puzzle_details, indent=2)}
    
    Output valid JSON only.
    """
    messages = [
        {"role": "system", "content": system_instructions},
        {"role": "user", "content": user_request}
    ]
    sanitized_room_name = sanitize_filename(room_name)
    sanitized_object_name = sanitize_filename(object_name)
    log_base = os.path.join("artifacts", "clues", f"{sanitized_room_name}_{sanitized_object_name}")
    response = create_chat_completion(
        messages,
        model=CREATIVE_MODEL,
        log_file_base=log_base,
        step_name=f"Clue Generation ({room_name} - {object_name})"
    )
    return json.loads(response)

# -------------------------------------------------------------------
# 5. Room Description LLM
#    Model: gpt-4o (creative descriptive writing)
# -------------------------------------------------------------------
def describe_room(room_name, room_data):
    """
    Produces a short atmospheric text describing the room, 
    referencing key objects without spoiling puzzles.
    Returns JSON with a single field "description".
    """
    system_instructions = (
        "You are an immersive narrative writer. "
        "Output valid JSON only—no additional commentary or markdown. "
        "Your entire response must be pure, parseable JSON with a single description field."
    )
    user_request = f"""
    Generate a concise description (5-8 sentences) for the room "{room_name}" 
    in the mansion, incorporating references to relevant objects/puzzles 
    without revealing solutions.
    
    room_data:
    {json.dumps(room_data, indent=2)}
    
    Return JSON: {{"description": "Your descriptive text"}}
    """
    messages = [
        {"role": "system", "content": system_instructions},
        {"role": "user", "content": user_request}
    ]
    sanitized_room_name = sanitize_filename(room_name)
    log_base = os.path.join("artifacts", "description", sanitized_room_name)
    response = create_chat_completion(
        messages,
        model=CREATIVE_MODEL,
        log_file_base=log_base,
        step_name=f"Room Description ({room_name})"
    )
    return json.loads(response)

# -------------------------------------------------------------------
# 6. Final Room Verification LLM
#    Model: gpt-4o (logical coherence check)
# -------------------------------------------------------------------
def verify_room(room_name, room_details):
    """
    Ensures final consistency of the room before integration.
    This LLM verifies puzzle solutions, clue coherence, etc.
    Returns either validated JSON or corrected JSON.
    """
    system_instructions = (
        "You are a detail-oriented game logic verifier. "
        "Check for logical consistency, puzzle solvability, and clue alignment. "
        "Output valid JSON only—no explanations, text, or markdown. "
        "Your entire response must be valid JSON."
    )
    user_request = f"""
    Review the following data for room '{room_name}':
    {json.dumps(room_details, indent=2)}

    1) Check puzzle and solution consistency.
    2) Ensure clues align logically with the puzzle solutions.
    3) Confirm entry/exit points match the overall mansion structure (if provided).
    4) Provide final JSON with any corrections or if all is good, mark it as approved.

    Only output valid JSON.
    """
    messages = [
        {"role": "system", "content": system_instructions},
        {"role": "user", "content": user_request}
    ]
    sanitized_room_name = sanitize_filename(room_name)
    log_base = os.path.join("artifacts", "verification", sanitized_room_name)
    response = create_chat_completion(
        messages,
        model=LOGICAL_MODEL,
        temperature=0.0,
        log_file_base=log_base,
        step_name=f"Room Verification ({room_name})"
    )
    return json.loads(response)

# -------------------------------------------------------------------
# Example Orchestrator (High-Level Usage)
# -------------------------------------------------------------------
def main_example():
    # Ensure the top-level artifacts directory exists
    os.makedirs("artifacts", exist_ok=True)
    # 1) Get mansion structure from user prompt
    # (In a real app, user_prompt might come from external input)
    user_prompt = (
        "We want a creepy Victorian mansion with interconnected secret passages "
        "and a few locked doors, oriented around puzzle-solving."
    )
    mansion_structure = game_structure_planner(user_prompt)

    # 2) For each room, define it
    final_rooms_data = {}
    for room in mansion_structure.get("rooms", []):
        room_name = room["name"]
        theme = room["theme"]
        
        # Get basic breakdown
        room_def = define_room(room_name, theme)

        # Suppose we pick one object to design a puzzle for demonstration
        if room_def["interactable_objects"]:
            first_object = room_def["interactable_objects"][0]
            puzzle_info = generate_puzzle(first_object, room_name)
            clues_info = generate_clues(first_object, room_name, puzzle_info)

            # Attach puzzle + clues to room data
            room_def["puzzle"] = puzzle_info
            room_def["clues"] = clues_info

        # 5) Generate a short, atmospheric description
        desc_json = describe_room(room_name, room_def)
        room_def["description"] = desc_json.get("description", "")

        # 6) Verify final room data
        verification_result = verify_room(room_name, room_def)
        final_rooms_data[room_name] = verification_result

    # For demonstration, just print the final structure
    # In a real application, you might store or serve this to your engine.
    print(json.dumps(final_rooms_data, indent=2))

if __name__ == "__main__":
    main_example()