import json
import random
import argparse
import collections # Needed for BFS queue
import math # Needed for infinity

class Room:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z
        self.id = f"{x}-{y}-{z}"
        # Connections: N, S, E, W, U, D (Up, Down)
        self.connections = {'N': None, 'S': None, 'E': None, 'W': None, 'U': None, 'D': None}
        self.is_foyer = False
        self.is_portal = False
        self.visited = False # For maze generation
        self.difficulty = math.inf # Distance from Foyer (calculated later)

    def connect(self, other_room, direction):
        opposite_direction = {
            'N': 'S', 'S': 'N', 'E': 'W', 'W': 'E', 'U': 'D', 'D': 'U'
        }
        if direction in self.connections:
            self.connections[direction] = other_room.id
            other_room.connections[opposite_direction[direction]] = self.id
        else:
            raise ValueError(f"Invalid direction: {direction}")

    def get_symbol(self):
        if self.is_foyer:
            return 'F'
        if self.is_portal:
            return 'P'

        has_up = self.connections['U'] is not None
        has_down = self.connections['D'] is not None

        if has_up and has_down:
            return 'X'
        elif has_up:
            return '<'
        elif has_down:
            return '>'
        else:
            return 'O'

    def to_dict(self):
        return {
            "id": self.id,
            "coords": (self.x, self.y, self.z),
            "connections": self.connections,
            "is_foyer": self.is_foyer,
            "is_portal": self.is_portal,
            "difficulty": self.difficulty if self.difficulty != math.inf else -1, # Use -1 for unreachable
            "symbol": self.get_symbol()
        }

def get_room_from_id(room_id, rooms_grid, xmax, ymax, zmax):
    try:
        x_str, y_str, z_str = room_id.split('-')
        x, y, z = int(x_str), int(y_str), int(z_str)
        if 0 <= x < xmax and 0 <= y < ymax and 0 <= z < zmax:
            return rooms_grid[x][y][z]
        else:
            return None # ID coordinates out of bounds
    except (ValueError, IndexError):
        return None # Invalid ID format or coords

def calculate_distances_bfs(start_room, rooms_grid, xmax, ymax, zmax):
    """Calculates shortest path distance from start_room to all others using BFS."""
    print("Calculating distances from Foyer...")
    # Reset all difficulties
    for x in range(xmax):
        for y in range(ymax):
            for z in range(zmax):
                rooms_grid[x][y][z].difficulty = math.inf

    queue = collections.deque([(start_room, 0)]) # (room, distance)
    start_room.difficulty = 0
    visited_bfs = {start_room.id} # Keep track of visited rooms in this BFS run

    while queue:
        current_room, distance = queue.popleft()

        # Explore neighbors
        for direction, neighbor_id in current_room.connections.items():
            if neighbor_id and neighbor_id not in visited_bfs:
                neighbor_room = get_room_from_id(neighbor_id, rooms_grid, xmax, ymax, zmax)
                if neighbor_room: # Should always find a valid room if ID exists
                    visited_bfs.add(neighbor_id)
                    neighbor_room.difficulty = distance + 1
                    queue.append((neighbor_room, distance + 1))
    print("Distance calculation complete.")

def generate_maze(xmax, ymax, zmax, extra_connection_prob=0.05):
    if xmax <= 0 or ymax <= 0 or zmax <= 0:
        raise ValueError("Dimensions must be positive integers")

    rooms = [[[Room(x, y, z) for z in range(zmax)] for y in range(ymax)] for x in range(xmax)]
    stack = []
    visited_count = 0
    total_rooms = xmax * ymax * zmax
    # last_visited_room is no longer used for Portal placement

    # Start position (Foyer)
    start_x, start_y, start_z = xmax // 2, 0, 0
    start_room = rooms[start_x][start_y][start_z]
    start_room.is_foyer = True
    start_room.visited = True # Mark visited for DFS
    stack.append(start_room)
    visited_count += 1

    # --- Primary Maze Generation (DFS) ---
    print("Generating initial maze structure (DFS)...")
    while visited_count < total_rooms:
        if not stack:
             # Find an unvisited room to restart DFS - necessary for potentially disconnected graphs
             print("Warning: DFS Stack empty, searching for unvisited node to ensure all rooms are processed...")
             unvisited_found = False
             # Iterate through all rooms to find an unvisited one
             for x in range(xmax):
                 for y in range(ymax):
                     for z in range(zmax):
                         room_to_check = rooms[x][y][z]
                         if not room_to_check.visited:
                             # Found an unvisited node, start a new DFS tree from here
                             room_to_check.visited = True # Mark visited immediately
                             stack.append(room_to_check)
                             visited_count += 1
                             unvisited_found = True
                             print(f"Restarting DFS from unconnected node {room_to_check.id}")
                             break
                     if unvisited_found: break
                 if unvisited_found: break
             if not unvisited_found:
                 # This should only happen if all rooms somehow got marked visited
                 # but visited_count < total_rooms, indicating a potential logic error.
                 print(f"Error: Could not find any remaining unvisited nodes, but expected {total_rooms - visited_count} more.")
                 break

        current_room = stack[-1] # Peek
        x, y, z = current_room.x, current_room.y, current_room.z

        # Potential neighbors (dx, dy, dz, direction)
        potential = [
            (x + 1, y, z, 'E'), (x - 1, y, z, 'W'),
            (x, y + 1, z, 'S'), (x, y - 1, z, 'N'),
            (x, y, z + 1, 'U'), (x, y, z - 1, 'D')
        ]
        random.shuffle(potential) # Randomize neighbor selection

        found_neighbor = False
        for nx, ny, nz, direction in potential:
            # Check bounds
            if 0 <= nx < xmax and 0 <= ny < ymax and 0 <= nz < zmax:
                neighbor_room = rooms[nx][ny][nz]
                if not neighbor_room.visited:
                    # Carve path
                    current_room.connect(neighbor_room, direction)
                    neighbor_room.visited = True
                    stack.append(neighbor_room)
                    visited_count += 1
                    found_neighbor = True
                    break # Move to the new neighbor

        if not found_neighbor:
            stack.pop() # Backtrack
    print("Initial maze structure complete.")

    # --- Add Extra Connections within Floors ---
    print(f"Adding extra connections with probability {extra_connection_prob}...")
    added_connections = 0
    for z in range(zmax):
        for y in range(ymax):
            for x in range(xmax):
                current_room = rooms[x][y][z]

                # Check East connection
                if x + 1 < xmax:
                    neighbor_room = rooms[x+1][y][z]
                    if current_room.connections['E'] is None: # If no connection exists
                        if random.random() < extra_connection_prob:
                            current_room.connect(neighbor_room, 'E')
                            added_connections += 1

                # Check South connection
                if y + 1 < ymax:
                    neighbor_room = rooms[x][y+1][z]
                    if current_room.connections['S'] is None: # If no connection exists
                        if random.random() < extra_connection_prob:
                            current_room.connect(neighbor_room, 'S')
                            added_connections += 1
    print(f"Added {added_connections} extra horizontal connections.")

    # --- Calculate Distances from Foyer ---
    calculate_distances_bfs(start_room, rooms, xmax, ymax, zmax)

    # --- Set Portal based on Difficulty ---
    print("Assigning Portal based on maximum distance...")
    max_difficulty = -1
    farthest_rooms = []

    for x in range(xmax):
        for y in range(ymax):
            for z in range(zmax):
                room = rooms[x][y][z]
                # Exclude foyer itself unless it's the only reachable room
                if room.difficulty != math.inf and (not room.is_foyer or total_rooms == 1):
                    if room.difficulty > max_difficulty:
                        max_difficulty = room.difficulty
                        farthest_rooms = [room]
                    elif room.difficulty == max_difficulty:
                        farthest_rooms.append(room)

    if not farthest_rooms:
         # Fallback: if only the foyer is reachable (e.g., 1x1x1 grid or error)
         # or if somehow no rooms qualified (shouldn't happen with BFS)
         if total_rooms > 0 and rooms[start_x][start_y][start_z].difficulty == 0:
             print("Warning: Only Foyer seems reachable or is the only candidate. Placing Portal in Foyer.")
             rooms[start_x][start_y][start_z].is_portal = True
         else:
              print("Error: Could not find any suitable room for the Portal. No Portal assigned.")
    else:
        # Choose one random room from the farthest ones
        portal_room = random.choice(farthest_rooms)
        portal_room.is_portal = True
        print(f"Portal placed in room {portal_room.id} with difficulty {portal_room.difficulty}")

    return rooms

def output_json(rooms, filename="mansion_map.json"):
    map_data = []
    xmax = len(rooms)
    ymax = len(rooms[0])
    zmax = len(rooms[0][0])
    for x in range(xmax):
        for y in range(ymax):
            for z in range(zmax):
                map_data.append(rooms[x][y][z].to_dict())

    with open(filename, 'w') as f:
        json.dump({
            "dimensions": {"xmax": xmax, "ymax": ymax, "zmax": zmax},
            "rooms": map_data
            }, f, indent=4)
    print(f"JSON map data saved to {filename}")

def output_visual_maps(rooms):
    xmax = len(rooms)
    ymax = len(rooms[0])
    zmax = len(rooms[0][0])

    vis_width = 2 * xmax + 1
    vis_height = 2 * ymax + 1

    for z in range(zmax):
        filename = f"mansion_floor_{z}.txt"
        vis_grid = [[' ' for _ in range(vis_width)] for _ in range(vis_height)]

        # Draw borders
        for r in range(vis_height):
            vis_grid[r][0] = '#'
            vis_grid[r][vis_width - 1] = '#'
        for c in range(vis_width):
            vis_grid[0][c] = '#'
            vis_grid[vis_height - 1][c] = '#'

        # Draw rooms and connections
        for y in range(ymax):
            for x in range(xmax):
                room = rooms[x][y][z]
                grid_r, grid_c = 2 * y + 1, 2 * x + 1

                # Place room symbol (Portal 'P' now takes precedence)
                vis_grid[grid_r][grid_c] = room.get_symbol()

                # Draw passages (only check East and South to avoid duplicates)
                # Also check North and West for drawing walls correctly if no passage
                if room.connections['E']:
                    vis_grid[grid_r][grid_c + 1] = '-'
                elif x + 1 < xmax : # Only draw wall if neighbor exists
                     vis_grid[grid_r][grid_c + 1] = '#'

                if room.connections['S']:
                    vis_grid[grid_r + 1][grid_c] = '|'
                elif y + 1 < ymax: # Only draw wall if neighbor exists
                     vis_grid[grid_r + 1][grid_c] = '#'

                # Fill corners with walls
                vis_grid[grid_r+1][grid_c+1] = '#'
                # Fill other walls gaps based on neighbours (optional but looks better)
                if x > 0 and vis_grid[grid_r+1][grid_c-1] == ' ': # Wall West-South Corner
                    vis_grid[grid_r+1][grid_c-1] = '#'
                if y > 0 and vis_grid[grid_r-1][grid_c+1] == ' ': # Wall North-East Corner
                    vis_grid[grid_r-1][grid_c+1] = '#'
                if x > 0 and y > 0 and vis_grid[grid_r-1][grid_c-1] == ' ': # Wall North-West Corner
                     vis_grid[grid_r-1][grid_c-1] = '#'



        with open(filename, 'w') as f:
            for row in vis_grid:
                f.write("".join(row) + "\n")
        print(f"Visual map for floor {z} saved to {filename}")


def main():
    parser = argparse.ArgumentParser(description="Generate a 3D mansion map for an adventure game.")
    parser.add_argument("xmax", type=int, help="Width of the mansion (number of rooms)")
    parser.add_argument("ymax", type=int, help="Depth of the mansion (number of rooms)")
    parser.add_argument("zmax", type=int, help="Number of floors")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for generation")
    parser.add_argument("--extra_prob", type=float, default=0.05, help="Probability of adding extra horizontal connections (0.0 to 1.0)")


    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    if not (0.0 <= args.extra_prob <= 1.0):
        print("Error: --extra_prob must be between 0.0 and 1.0")
        return

    print(f"Generating a {args.xmax}x{args.ymax}x{args.zmax} mansion map...")
    try:
        # Pass the extra connection probability to the generator
        mansion_rooms = generate_maze(args.xmax, args.ymax, args.zmax, args.extra_prob)
        output_json(mansion_rooms)
        output_visual_maps(mansion_rooms)
        print("Map generation complete.")
    except ValueError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc() # Print stack trace for debugging


if __name__ == "__main__":
    main()
