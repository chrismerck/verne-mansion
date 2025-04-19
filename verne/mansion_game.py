# ────────────────────────────────────────────────────────────────────────────
# mansion_game.py – simple CLI engine
# Usage:   python mansion_game.py sample_mansion.json
#          python mansion_game.py  (defaults to sample_mansion.json in script dir)
# The engine works for any mansion JSON built with the same structure (e.g. the
# upcoming 30‑room version). Only the JSON file needs to change – no code edits.

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Set


def load_game(path: Path) -> Dict[str, Any]:
    """Load and validate the mansion JSON definition."""
    try:
        with path.open("r", encoding="utf‑8") as fh:
            data = json.load(fh)
    except FileNotFoundError as exc:
        sys.exit(f"❌ JSON file not found: {exc}")
    except json.JSONDecodeError as exc:
        sys.exit(f"❌ JSON syntax error: {exc}")

    for required in ("start_room", "rooms"):
        if required not in data:
            sys.exit(f"❌ Missing '{required}' field in JSON definition.")

    # Index rooms by id for O(1) lookup
    data["room_index"] = {room["id"]: room for room in data["rooms"]}
    if data["start_room"] not in data["room_index"]:
        sys.exit("❌ start_room id not found in rooms list.")
    return data


def render(text: str) -> str:
    """Return entry text with **bold** markers removed for console output."""
    return text.replace("**", "")


def list_actions(room: Dict[str, Any]) -> List[str]:
    """Return a list of single‑word actions available in the room."""
    exits = [ex["name"] for ex in room.get("exits", [])]
    items = [it["name"] for it in room.get("items", [])]
    return sorted(set(exits + items))


class MansionGame:
    """Core game engine."""

    def __init__(self, data: Dict[str, Any]):
        self.rooms = data["room_index"]              # id → room dict
        self.current = data["start_room"]            # id of current room
        self.inventory: Set[str] = set()              # collected items / flags
        self.transformed: Set[str] = set()            # rooms which displayed _after_ text
        self.end_room = data.get("end_room", "END")  # sentinel for winning

    # ───────────────────────────────── CLI loop ────────────────────────────
    def play(self) -> None:
        print("» Type a single word to interact (help, inventory, quit).\n")
        while True:
            room = self.rooms[self.current]
            entered_before = self.current in self.transformed

            # Print room name
            print(f"\n[ {self.current} ]")
            
            text = room.get("entry_text_after") if entered_before else room["entry_text"]
            print("\n" + render(text))

            # Show quick cheat‑sheet of actions
            actions = list_actions(room)
            if actions:
                print("Available actions:", ", ".join(actions))

            cmd = input("\n› ").strip().lower()
            if not cmd:
                continue
            if cmd in {"quit", "exit"}:
                print("Goodbye!")
                break
            if cmd == "help":
                self.help()
                continue
            if cmd == "inventory":
                self.show_inventory()
                continue

            if self.try_item(room, cmd):
                continue
            if self.try_exit(room, cmd):
                # moved room; loop back to describe new room
                continue
            print("I don't see how to do that.")

    # ───────────────────────────── helper routines ─────────────────────────
    def help(self) -> None:
        print("\nCommands:\n  inventory  – list the things you're carrying\n  help       – this message\n  quit       – bail out\nOtherwise type exactly one of the bolded words shown in the room.")

    def show_inventory(self) -> None:
        if self.inventory:
            print("You are carrying:", ", ".join(sorted(self.inventory)))
        else:
            print("You have nothing.")

    # ---------------------------------------------------------------------
    def try_item(self, room: Dict[str, Any], cmd: str) -> bool:
        """Return True if cmd matched an item and was handled."""
        for item in room.get("items", []):
            if item["name"].lower() != cmd:
                continue
            itype = item["type"]
            if itype == "hint":
                print(render(item["text"]))
            elif itype == "inventory":
                print(render(item["description"]))
                given = item.get("gives_item")
                if given:
                    self.inventory.add(given)
            elif itype == "riddle":
                self.handle_riddle(item, room)
            else:
                print("[⚠ Unknown item type]")
            return True
        return False

    def handle_riddle(self, item: Dict[str, Any], room: Dict[str, Any]):
        print(item["prompt"])
        attempt = input("Answer: ").strip().lower()
        if attempt == item["answer"].lower():
            print(item["success_text"])
            # grant reward token (key or flag)
            token = item.get("gives_item") or f"{item['name']}_solved"
            self.inventory.add(token)
            # mark room as transformed to use entry_text_after from now on
            if "entry_text_after" in room:
                self.transformed.add(room["id"])
        else:
            print("That doesn't seem right.")

    # ---------------------------------------------------------------------
    def try_exit(self, room: Dict[str, Any], cmd: str) -> bool:
        """Return True if cmd matched an exit (and movement happened or failed)."""
        for ex in room.get("exits", []):
            if ex["name"].lower() != cmd:
                continue
            if ex.get("locked", False):
                required = ex.get("key")
                if required and required in self.inventory:
                    print(f"You use the {required} to open the {ex['name']}.")
                    ex["locked"] = False
                    # if the room has an alternate description, flip it on unlock
                    if "entry_text_after" in room:
                        self.transformed.add(room["id"])
                else:
                    print("It won't budge; seems locked.")
                    return True
            # still locked?
            if ex.get("locked", False):
                return True

            dest = ex["to"]
            if dest == self.end_room:
                print("\nYou step through the portal and feel reality twist…\nCongratulations – you have escaped the mansion!")
                sys.exit(0)
            if dest not in self.rooms:
                print("The exit leads nowhere (malformed JSON).")
                return True
            self.current = dest
            return True
        return False


# ──────────────────────────────────────── main ─────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Play a text‑based mansion maze game.")
    parser.add_argument("json", nargs="?", default="sample_mansion.json", help="Path to the mansion definition JSON file")
    args = parser.parse_args()

    data = load_game(Path(args.json))
    MansionGame(data).play()


if __name__ == "__main__":
    main()
