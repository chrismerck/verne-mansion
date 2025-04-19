import curses
import json
import sys
import os

# Helper to find the Foyer room from loaded data
def find_foyer(rooms_data):
    for room in rooms_data:
        if room.get("is_foyer", False):
            return room
    return None

# Helper to get room by coordinates from loaded data
def get_room_at(x, y, z, rooms_dict):
    return rooms_dict.get((x, y, z))

def main(stdscr):
    # --- Initialization ---
    curses.curs_set(0) # Hide cursor
    stdscr.nodelay(False) # Wait for user input
    stdscr.keypad(True) # Enable special keys (like arrows)
    curses.start_color()
    curses.init_pair(1, curses.COLOR_YELLOW, curses.COLOR_BLACK) # Player
    curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)  # Foyer/Portal
    curses.init_pair(3, curses.COLOR_CYAN, curses.COLOR_BLACK)   # Stairs
    curses.init_pair(4, curses.COLOR_WHITE, curses.COLOR_BLACK) # Normal Room / Walls / Passages
    curses.init_pair(5, curses.COLOR_RED, curses.COLOR_BLACK)    # Error/Win message
    curses.init_pair(6, curses.COLOR_BLUE, curses.COLOR_BLACK)   # Unexplored markers

    map_filename = "mansion_map.json"
    if not os.path.exists(map_filename):
        stdscr.clear()
        stdscr.addstr(0, 0, f"Error: Map file '{map_filename}' not found.", curses.color_pair(5) | curses.A_BOLD)
        stdscr.addstr(1, 0, "Please run mkmap.py first.", curses.color_pair(5))
        stdscr.addstr(3, 0, "Press any key to exit.")
        stdscr.getch()
        return

    try:
        with open(map_filename, 'r') as f:
            map_data = json.load(f)
    except json.JSONDecodeError:
        stdscr.clear()
        stdscr.addstr(0, 0, f"Error: Could not decode JSON from '{map_filename}'.", curses.color_pair(5) | curses.A_BOLD)
        stdscr.addstr(2, 0, "Press any key to exit.")
        stdscr.getch()
        return
    except Exception as e:
        stdscr.clear()
        stdscr.addstr(0, 0, f"Error loading map: {e}", curses.color_pair(5) | curses.A_BOLD)
        stdscr.addstr(2, 0, "Press any key to exit.")
        stdscr.getch()
        return

    dimensions = map_data.get("dimensions", {})
    xmax = dimensions.get("xmax")
    ymax = dimensions.get("ymax")
    zmax = dimensions.get("zmax")
    all_rooms_list = map_data.get("rooms", [])

    if xmax is None or ymax is None or zmax is None or not all_rooms_list:
        stdscr.clear()
        stdscr.addstr(0, 0, "Error: Map file is missing dimensions or rooms.", curses.color_pair(5) | curses.A_BOLD)
        stdscr.addstr(2, 0, "Press any key to exit.")
        stdscr.getch()
        return

    # Convert room list to a dictionary keyed by coordinates for faster lookup
    rooms_dict = {(r['coords'][0], r['coords'][1], r['coords'][2]): r for r in all_rooms_list}

    foyer_room = find_foyer(all_rooms_list)
    if not foyer_room:
        stdscr.clear()
        stdscr.addstr(0, 0, "Error: Foyer room not found in map data.", curses.color_pair(5) | curses.A_BOLD)
        stdscr.addstr(2, 0, "Press any key to exit.")
        stdscr.getch()
        return

    # --- Player State ---
    player_x, player_y, player_z = foyer_room['coords']
    visited_room_ids = {foyer_room['id']} # Start with Foyer visited
    message = "Welcome! Use arrow keys to move, <> for stairs, q to quit."
    won = False

    # --- Main Game Loop ---
    while True:
        stdscr.clear()
        h, w = stdscr.getmaxyx()

        # --- Drawing ---
        vis_width = 2 * xmax + 1
        vis_height = 2 * ymax + 1
        map_start_row = 1
        map_start_col = 2

        # Basic boundary check for drawing
        if map_start_row + vis_height >= h or map_start_col + vis_width >= w:
             stdscr.addstr(0,0, "Terminal too small!", curses.color_pair(5) | curses.A_BOLD)
             stdscr.addstr(1,0, f"Need at least {vis_width+map_start_col}x{vis_height+map_start_row+2}")

        else:
            # Draw Floor Indicator
            stdscr.addstr(0, map_start_col, f"--- Floor {player_z} ---", curses.A_BOLD)

            # Draw Map Area
            for r in range(vis_height):
                for c in range(vis_width):
                    map_char = ' ' # Default empty space
                    char_attr = curses.color_pair(4) # Default color

                    # Determine if it's a room or connection based on parity
                    is_room_row = r % 2 != 0
                    is_room_col = c % 2 != 0

                    # Keep the outer border
                    if r == 0 or r == vis_height - 1 or c == 0 or c == vis_width - 1:
                        map_char = '#' # Border
                        char_attr = curses.color_pair(4) | curses.A_BOLD
                    elif is_room_row and is_room_col:
                        # --- Room Cell ---
                        room_x, room_y = c // 2, r // 2
                        current_cell_room = get_room_at(room_x, room_y, player_z, rooms_dict)

                        if current_cell_room and current_cell_room['id'] in visited_room_ids:
                            if room_x == player_x and room_y == player_y:
                                map_char = '@'
                                char_attr = curses.color_pair(1) | curses.A_BOLD # Player color
                            else:
                                room_symbol = current_cell_room['symbol']
                                map_char = room_symbol
                                if room_symbol in ('F', 'P'):
                                    char_attr = curses.color_pair(2) | curses.A_BOLD # Foyer/Portal
                                elif room_symbol in ('<', '>', 'X'):
                                    char_attr = curses.color_pair(3) | curses.A_BOLD # Stairs
                                else:
                                    char_attr = curses.color_pair(4) # Normal room
                        else:
                            # Unvisited room
                            map_char = '.' # Indicate potentially explorable but unseen
                            char_attr = curses.color_pair(6) # Unexplored color

                    elif is_room_row and not is_room_col:
                        # --- Horizontal Connection Cell ---
                        left_room_x, left_room_y = (c - 1) // 2, r // 2
                        right_room_x, right_room_y = (c + 1) // 2, r // 2

                        left_room = get_room_at(left_room_x, left_room_y, player_z, rooms_dict)
                        right_room = get_room_at(right_room_x, right_room_y, player_z, rooms_dict)

                        # Show passage if the left room is visited and connects East,
                        # OR if the right room is visited and connects West.
                        show_passage = False
                        if left_room and left_room['id'] in visited_room_ids and left_room['connections'].get('E'):
                            show_passage = True
                        elif right_room and right_room['id'] in visited_room_ids and right_room['connections'].get('W'):
                             show_passage = True

                        if show_passage:
                             map_char = '-'
                             char_attr = curses.color_pair(4)
                        else:
                             map_char = ' ' # No wall char, just empty space


                    elif not is_room_row and is_room_col:
                        # --- Vertical Connection Cell ---
                        top_room_x, top_room_y = c // 2, (r - 1) // 2
                        bottom_room_x, bottom_room_y = c // 2, (r + 1) // 2

                        top_room = get_room_at(top_room_x, top_room_y, player_z, rooms_dict)
                        bottom_room = get_room_at(bottom_room_x, bottom_room_y, player_z, rooms_dict)

                        # Show passage if the top room is visited and connects South,
                        # OR if the bottom room is visited and connects North.
                        show_passage = False
                        if top_room and top_room['id'] in visited_room_ids and top_room['connections'].get('S'):
                            show_passage = True
                        elif bottom_room and bottom_room['id'] in visited_room_ids and bottom_room['connections'].get('N'):
                             show_passage = True

                        if show_passage:
                           map_char = '|'
                           char_attr = curses.color_pair(4)
                        else:
                           map_char = ' ' # No wall char, just empty space

                    else:
                        # --- Corner space ---
                        # Always draw empty space in corners now.
                         map_char = ' '


                    stdscr.addch(map_start_row + r, map_start_col + c, map_char, char_attr)

            # Draw Message Line
            stdscr.addstr(map_start_row + vis_height + 1, 0, message, curses.color_pair(5) if won else curses.color_pair(4))
            message = "" # Clear message after displaying

        stdscr.refresh()

        # --- Input Handling ---
        if won:
            stdscr.getch() # Wait for key press after winning
            break

        try:
            key = stdscr.getkey()
        except curses.error: # Handle interrupted getkey (e.g., terminal resize)
             message = "Input error or terminal resized. Please try again."
             continue


        current_room = get_room_at(player_x, player_y, player_z, rooms_dict)
        if not current_room:
             message = "Error: Player is in an invalid location!" # Should not happen
             continue # Or break with error

        new_x, new_y, new_z = player_x, player_y, player_z
        moved = False
        target_room_id = None

        if key in ('KEY_UP', 'k'):
            target_room_id = current_room['connections']['N']
            if not target_room_id: message = "Blocked."
        elif key in ('KEY_DOWN', 'j'):
            target_room_id = current_room['connections']['S']
            if not target_room_id: message = "Blocked."
        elif key in ('KEY_LEFT', 'h'):
            target_room_id = current_room['connections']['W']
            if not target_room_id: message = "Blocked."
        elif key in ('KEY_RIGHT', 'l'):
            target_room_id = current_room['connections']['E']
            if not target_room_id: message = "Blocked."
        elif key == '<':
            target_room_id = current_room['connections']['U']
            if not target_room_id: message = "No stairs up."
        elif key == '>':
            target_room_id = current_room['connections']['D']
            if not target_room_id: message = "No stairs down."
        elif key == 'q':
            break
        else:
            message = "Invalid key. Arrows=move, <> = stairs, q=quit"

        if target_room_id:
            try:
                nx_str, ny_str, nz_str = target_room_id.split('-')
                new_x, new_y, new_z = int(nx_str), int(ny_str), int(nz_str)
                moved = True
                player_x, player_y, player_z = new_x, new_y, new_z
                visited_room_ids.add(target_room_id)

                # Check for win condition
                new_room = get_room_at(player_x, player_y, player_z, rooms_dict)
                if new_room and new_room.get('is_portal'):
                    won = True
                    message = f"Congratulations! You reached the Portal (Room {target_room_id})!"

            except (ValueError, KeyError):
                 message = f"Error: Invalid room ID format '{target_room_id}' in connections."
                 # Don't move if ID is bad
                 moved = False
                 player_x, player_y, player_z = current_room['coords'] # Revert potential bad intermediate state
                 target_room_id = None


# --- Run the game ---
if __name__ == "__main__":
    # curses.wrapper handles terminal setup and cleanup
    curses.wrapper(main)
    print("Game exited.") 