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

CREATIVE_MODEL = "gpt-4.5-preview"
LOGICAL_MODEL = "o1"
#CREATIVE_MODEL = "gpt-4o"
#LOGICAL_MODEL = "gpt-4o"

# -------------------------------------------------------------------
#  PROMPT TEMPLATES
# -------------------------------------------------------------------

# 1. Game Structure Planner Prompts
GAME_STRUCTURE_SYSTEM = (
    "You are a skilled puzzle-game designer, specializing in Victorian-era mysteries inspired by Jules Verne. "
    "Produce valid JSON output only, omitting any additional comments or formatting."
)

def get_game_structure_user_prompt(user_prompt):
    return f"""
    Based explicitly on the following background lore, devise a detailed and intriguing mansion layout for a puzzle-adventure web game:

    {user_prompt}

    Requirements:
    - Precisely 30 uniquely themed rooms influenced by Lucien Ravenshade's Victorian era eccentricities and Jules Verne-inspired inventions.
    - Each room explicitly named (evocative and theme-appropriate) and briefly described.
    - Clearly outline room exits, including stair cases, doorways, locked doors, or secret passages of any kind. (Do not specify the room names of the exits, just the directions.) 
    - Valid exit directions are N, S, E, W, U (up) and D (down).
    - Start with "Grand Vestibule" and end with "Portal Chamber".
    - Keep output strictly in valid JSON format:
    """ + r"""
    {"rooms": [ {"name": "Concise Room Name", "theme": "Room Thematic description", "exits": {"N": "locked door", "U": "staircase", "W": "hidden passage behind bookshelf"} }] }
    """

# 2. Room Definition Prompts
ROOM_DEFINITION_SYSTEM = (
    "You are an expert adventure room designer, deeply familiar with Victorian-Era aesthetics and fantastical Jules Verne-inspired machinery. "
    "Output detailed JSON only; omit any commentary or markdown formatting."
)

def get_room_definition_user_prompt(room_name, theme_description):
    return f"""
    Expand into vivid detail the room titled "{room_name}", specifically considering the theme: "{theme_description}" from Ravenshade Manor's Victorian puzzle-adventure.

    Provide exactly the following in JSON format:
    - "interactable_objects": an array of distinct room objects (e.g., mechanical contraptions, maps, furniture, artifacts, Verne-inspired technology).
    - "entry_exit_points": clearly categorized doorways, locked doors, or concealed secret passages connecting to neighboring rooms.
    - "hidden_mechanics": special hidden interactive features aligned with Lucien Ravenshade's experiments and Victorian-era ingenuity.

    Output JSON only, strictly conforming to clarity and readability.
    """

# 3. Puzzle Generator Prompts
PUZZLE_GENERATOR_SYSTEM = (
    "You are a specialist puzzle creator, accurately designing puzzles inspired by Victorian-era exploration and speculative science akin to Jules Verne's inventions. "
    "Return puzzle details exclusively in parseable, concise JSON form."
)

def get_puzzle_generator_user_prompt(object_name, room_name):
    return f"""
    Invent a puzzle involving the Victorian and Jules Verne-inspired object "{object_name}" in the Ravenshade Manor room "{room_name}":

    Specifically provide in JSON format:
    - "puzzle_setup": initial reveal and how the player finds it within the room (concealed mechanism, subtle indicator, etc.).
    - "interactions": meticulous steps or actions needed (activation sequences, logical reasoning, machine operations).
    - "logic": clearly stated logic, symbolic, numerical or spatial reasoning underpinning the puzzle.
    - "solution": final solved state or solution clearly explained.
    - "reward": meaningful outcome such as opening secret passages, gaining an artifact, revealing hidden narrative information related to Lucien's explorations or Chronal Resonators.

    Provide valid and structured JSON only.
    """

# 4. Clue Generator Prompts
CLUE_GENERATOR_SYSTEM = (
    "You are a puzzle clue design expert, adept at subtly guiding players in Jules Verne-inspired Victorian puzzle adventures. "
    "Output clearly structured, valid JSON only, free from extraneous explanation or text."
)

def get_clue_generator_user_prompt(object_name, room_name, puzzle_details):
    return f"""
    From these puzzle details involving object "{object_name}" in the Ravenshade Manor room named "{room_name}", carefully design 2 to 4 subtly placed clues that support player discovery without explicitly revealing solutions.

    Each clue must explicitly indicate:
    - "location": a different room or specific hidden object within Ravenshade Manor where the clue is located.
    - "form": precisely described form of clue (notes, scribbled margins, engravings, faded sketches, etc.) suitable to Victorian-era adventuring.
    - "hint_text": elegantly subtle textual hints gently illuminating puzzle logic without direct spoilers.

    Puzzle details provided:
    {json.dumps(puzzle_details, indent=2)}

    Output JSON strictly.
    """

# 5. Room Description Prompts
ROOM_DESCRIPTION_SYSTEM = (
    "You are a highly talented, atmospheric narrative writer skilled in crafting evocative scenes influenced by Victorian mysteries and Jules Verne's speculative technology. "
    "Your output must strictly be concise JSON containing a single elegantly descriptive text field."
)

def get_room_description_user_prompt(room_name, room_data):
    return f"""
    Write an immersive, atmospheric description (5-8 sentences) for the Ravenshade Manor room "{room_name}". 

    Your description should thoughtfully weave references to interactable objects, hints of hidden mechanisms inspired by Lucien Ravenshade's explorations, puzzles, and Victorian-era atmosphere, avoiding direct spoilers. Ensure an enticing, mysterious atmosphere hinting at deeper secrets related to Ravenshade's discoveries and eccentric ingenuity.

    Room details provided:
    {json.dumps(room_data, indent=2)}

    Return strictly JSON: {{"description": "Your generated evocative atmospheric description here."}}
    """

# 6. Room Verification Prompts
ROOM_VERIFICATION_SYSTEM = (
    "You are meticulous and detail-oriented, tasked with confirming logical integrity and puzzle consistency in Victorian-era puzzle adventures. "
    "Provide strictly structured and clear JSON results only, without additional comments or markdown formatting."
)

def get_room_verification_user_prompt(room_name, room_details):
    return f"""
    Carefully verify every element provided for Ravenshade Manor room '{room_name}', detailed as follows:
    {json.dumps(room_details, indent=2)}

    Explicitly perform the following checks and correct any issues:
    1) Validate puzzle logic, ensuring absolute clarity in interactions and solvable solutions clearly reflecting Victorian-era ingenuity, Jules Verne-inspired designs, and Ravenshade narrative consistency.
    2) Examine provided clues carefully, ensuring all clues logically align and effectively guide the puzzle's solution without direct spoilers.
    3) Verify the accuracy and logical connectivity of all listed entry/exit points, locked doors, or secret passages considering overall mansion structure context.
    4) Check description against puzzles and interactable objects to ensure absolute coherence and subtlety.

    If corrections are necessary, provide clearly labeled corrections; otherwise, explicitly indicate in JSON that the room is fully validated and approved without changes.

    Output this strictly structured information as clear, readable JSON only.
    """

# -------------------------------------------------------------------
#  Helper function to send messages to the OpenAI ChatCompletion API.
# -------------------------------------------------------------------
def sanitize_filename(name):
    """Removes potentially problematic characters for filenames."""
    name = re.sub(r'[^\w\s-]', '', name).strip() # Remove non-alphanumeric (allow whitespace and hyphens)
    name = re.sub(r'[-\s]+', '_', name) # Replace spaces/hyphens with underscores
    return name

def load_chat_from_file(log_file_path):
    """
    Load a cached chat response from a file.
    Returns the extracted JSON response if the file exists, None otherwise.
    """
    if not os.path.exists(log_file_path):
        return None
    
    try:
        with open(log_file_path, "r") as f:
            content = f.read()
        
        # Extract the response content between the assistant message and usage sections
        response_section = re.search(r"## Assistant Message ##\n([\s\S]*?)\n\n---------- USAGE ----------", content)
        if response_section:
            response_content = response_section.group(1).strip()
            # Verify it's valid JSON
            try:
                json.loads(response_content)
                print(f"Using cached response from {log_file_path}")
                return response_content
            except json.JSONDecodeError:
                print(f"Warning: Cached response in {log_file_path} is not valid JSON.")
                return None
        return None
    except Exception as e:
        print(f"Error reading cached chat file {log_file_path}: {e}")
        return None

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
        
        # Check if there's a cached response
        cached_response = load_chat_from_file(log_file_path)
        if cached_response:
            return cached_response
        
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
    messages = [
        {"role": "system", "content": GAME_STRUCTURE_SYSTEM},
        {"role": "user", "content": get_game_structure_user_prompt(user_prompt)}
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
    messages = [
        {"role": "system", "content": ROOM_DEFINITION_SYSTEM},
        {"role": "user", "content": get_room_definition_user_prompt(room_name, theme_description)}
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
    messages = [
        {"role": "system", "content": PUZZLE_GENERATOR_SYSTEM},
        {"role": "user", "content": get_puzzle_generator_user_prompt(object_name, room_name)}
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
    messages = [
        {"role": "system", "content": CLUE_GENERATOR_SYSTEM},
        {"role": "user", "content": get_clue_generator_user_prompt(object_name, room_name, puzzle_details)}
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
    messages = [
        {"role": "system", "content": ROOM_DESCRIPTION_SYSTEM},
        {"role": "user", "content": get_room_description_user_prompt(room_name, room_data)}
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
    messages = [
        {"role": "system", "content": ROOM_VERIFICATION_SYSTEM},
        {"role": "user", "content": get_room_verification_user_prompt(room_name, room_details)}
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
        """
        In the waning years of the 19th century, Lucien Ravenshade, a scholar and explorer of extraordinary ambition and eccentricity, had become an enigma whispered about in drawing rooms across Europe. Born into great wealth, Ravenshade found conventional pursuits unworthy of his restless imagination. His insatiable curiosity, matched only by his boundless resources, drove him across oceans and continents, delving into the unknown realms of both science and myth.

Inspired by the visionary journeys chronicled by his contemporaries—such as Professor Pierre Aronnax's undersea adventures aboard Captain Nemo’s Nautilus, or Phileas Fogg’s legendary voyage around the world—Lucien undertook expeditions into the most remote and forbidding regions of the earth. Each voyage brought back peculiar artifacts, volumes of rare lore, and whispered rumors of discoveries too fantastic to reveal openly.

Yet, it was in the quiet countryside of Northern England that Lucien chose to build Ravenshade Manor. Designed with intricate complexity and riddled with concealed passages, the mansion was more than a mere home: it was a manifestation of Lucien’s obsession with secrecy and discovery. Within its walls, he amassed an unparalleled collection of treasures: ancient maps inscribed in forgotten tongues, contraptions engineered from blueprints too advanced for their era, and fragments of civilizations said to exist only in legend.

In his latter years, Lucien became increasingly withdrawn, speaking cryptically of a groundbreaking revelation—an invention or perhaps a discovery—that would forever alter humanity’s understanding of time and space. He filled his journals with obscure references to "Chronal Resonators," machines capable of bending reality, and doors "between worlds." Drawing from the speculative visions of Jules Verne himself, Lucien hinted at realms buried beneath the earth, submerged in the depths of the ocean, or hidden among the clouds.

Then, without explanation, Lucien vanished.

For decades thereafter, Ravenshade Manor stood sealed and silent, guarded by a trust whose instructions forbade entry except under extraordinary circumstances. Persistent rumors suggested the mansion was more alive than abandoned—strange lights flickering in windows, spectral figures glimpsed through curtains, and music drifting hauntingly from empty halls. The townsfolk whispered that Lucien had not truly departed but instead become ensnared in his own experiments, caught between realities.

Now, a century later, you—a historian renowned for your expertise on Victorian-era mysteries—receive a cryptic invitation bearing the Ravenshade family seal. Curious and compelled by the offer of uncovering truths long buried, you journey to Ravenshade Manor. But upon crossing the threshold, it swiftly becomes apparent that Lucien’s legacy remains active, his puzzles, secrets, and devices waiting patiently for someone clever and bold enough to unravel them.

Each room within Ravenshade Manor is layered with complexity, as if the house itself were an immense puzzle designed by Lucien to protect—and perhaps reveal—his ultimate discovery. From locked chambers and hidden laboratories to secret observatories observing impossible constellations, every passageway opened and puzzle solved draws you closer to Lucien's greatest secret: a device capable of transcending the limitations of space and time.

Yet the mansion is no passive vault; its enigmatic machinery, influenced by Lucien’s dabbling with forces he scarcely understood, constantly rearranges pathways and puzzles, challenging you anew with each step forward. Ravenshade Manor demands intelligence, observation, and courage. To succeed, you must not only decipher the puzzles but understand the ambitions and fears of Lucien Ravenshade himself, unraveling a mystery that spans realms both known and unknowable.

Ultimately, your exploration will determine whether Lucien Ravenshade’s work was madness or genius, and if the secret he left behind holds the potential to illuminate humanity’s future—or doom it.
"""
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