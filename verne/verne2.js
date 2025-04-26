const consoleOutput = document.getElementById('console-output');
const commandInput = document.getElementById('command-input');
const gameContainer = document.getElementById('game-container');

let gameData = {};
let currentRoomId = '';
let roomIndex = {};
let inventory = new Set();
let transformedRooms = new Set(); // Rooms that should use entry_text_after
let isWaitingForAnswer = false; // Flag for riddle handling
let isWaitingForEnter = false; // Flag to wait for Enter before showing room
let currentRiddle = null;

// ADD: Globals to manage the active typewriter
let activeTypewriterTimeoutId = null;
let activeTypewriterElement = null;
let activeTypewriterFullText = '';

const TYPEWRITER_DELAY = 35; // ms per character
const SAVE_KEY = 'verne_savegame'; // Key for localStorage

// --- Utility Functions ---

function sanitizeForFilename(name) {
    // Basic sanitization: lowercase, replace spaces with underscores, remove non-alphanumeric/underscore
    return name.toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9_]/g, '');
}

function renderText(text) {
    // Replace **bold** with <b>bold</b> for HTML rendering
    return text.replace(/\*\*(.*?)\*\*/g, '<b>$1</b>');
}

function getAvailableActions(room, includeGlobal = false) {
    const exitNames = (room.exits || []).map(ex => ex.name.toLowerCase());
    const itemNames = (room.items || []).map(it => it.name.toLowerCase());
    let actions = [...new Set([...exitNames, ...itemNames])]; // Combine and remove duplicates
    if (includeGlobal) {
        actions = [...new Set([...actions, 'help', 'inventory', 'quit'])]; // Add global commands
    }
    return actions.sort();
}

// Function to immediately update background image without redrawing room
function updateBackgroundImage() {
    const room = roomIndex[currentRoomId];
    if (!room) return;
    
    const roomImageName = sanitizeForFilename(room.id);
    const imageState = transformedRooms.has(currentRoomId) ? 'after' : 'before';
    const imageUrl = `rooms/${roomImageName}/${imageState}.png`;
    gameContainer.style.backgroundImage = `url('${imageUrl}')`;
}

// --- Typewriter Effect ---

function typeWriter(text, element, callback) {
    // ADD: Clear any previous typewriter effect immediately
    if (activeTypewriterTimeoutId) {
        clearTimeout(activeTypewriterTimeoutId);
        if (activeTypewriterElement) {
            // Ensure the previous element shows its full text immediately
            activeTypewriterElement.innerHTML = activeTypewriterFullText;
        }
        // Reset globals, except for the new ones we're about to set
        activeTypewriterTimeoutId = null;
        activeTypewriterElement = null;
        activeTypewriterFullText = '';
    }

    element.innerHTML = ''; // Clear previous content of the target element

    // First, create the full content with proper formatting
    const fullText = renderText(text); // Convert markdown to HTML

    // ADD: Store info about the current typewriter
    activeTypewriterElement = element;
    activeTypewriterFullText = fullText;

    // Create array of all characters, preserving HTML tags
    const htmlChars = [];
    let inTag = false;
    let currentTag = '';
    
    // Process the HTML string character by character
    for (let i = 0; i < fullText.length; i++) {
        const char = fullText[i];
        
        if (char === '<') {
            inTag = true;
            currentTag += char;
        } else if (char === '>' && inTag) {
            inTag = false;
            currentTag += char;
            htmlChars.push(currentTag);
            currentTag = '';
        } else if (inTag) {
            currentTag += char;
        } else {
            // Regular character outside of tags
            htmlChars.push(char);
        }
    }
    
    // Type each character or HTML tag with proper timing
    let index = 0;
    let currentParent = element; // Track the current parent element for nesting
    const elementStack = [element]; // Stack to track nested elements
    
    function typeNextChar() {
        if (index >= htmlChars.length) {
            // All characters displayed, enable input and trigger callback
            // REMOVE: isTyping = false;
            // REMOVE: commandInput.disabled = false;
            // ADD: Reset typewriter state
            activeTypewriterTimeoutId = null;
            activeTypewriterElement = null;
            activeTypewriterFullText = '';

            // Only refocus if we are not waiting for a specific input state
            if (!isWaitingForAnswer && !isWaitingForEnter) {
                 commandInput.focus();
            }
            if (callback) callback();
            return;
        }
        
        const char = htmlChars[index];
        index++;
        
        // If it's an HTML tag, handle it properly
        if (char.startsWith('<')) {
            if (char.startsWith('</')) {
                // Closing tag - pop from stack and set current parent
                if (elementStack.length > 1) { // Don't pop the root element
                    elementStack.pop();
                    currentParent = elementStack[elementStack.length - 1];
                }
                typeNextChar(); // Process next char immediately
            } else if (char.startsWith('<b>')) {
                // Opening bold tag - create element and push to stack
                const boldElement = document.createElement('b');
                currentParent.appendChild(boldElement);
                elementStack.push(boldElement);
                currentParent = boldElement;
                typeNextChar(); // Process next char immediately
            } else {
                // Other tags - add directly (shouldn't happen with our simple formatting)
                const tempDiv = document.createElement('div');
                tempDiv.innerHTML = char;
                while (tempDiv.firstChild) {
                    currentParent.appendChild(tempDiv.firstChild);
                }
                typeNextChar(); // Process next char immediately
            }
        } else {
            // For regular characters, use the typewriter effect
            const span = document.createElement('span');
            span.className = 'typewriter-char';
            span.textContent = char;
            currentParent.appendChild(span);
            
            // Ensure scrolling happens as typing progresses
            consoleOutput.scrollTop = consoleOutput.scrollHeight;
            
            // Continue with next character after delay
            // STORE TIMEOUT ID
            activeTypewriterTimeoutId = setTimeout(typeNextChar, TYPEWRITER_DELAY);
        }
    }
    
    // Start typing
    typeNextChar();
}


// --- Game Logic ---

function displayOutput(text, isImmediate = false) {
    if (isImmediate) {
        const div = document.createElement('div');
        div.innerHTML = renderText(text);
        consoleOutput.appendChild(div);
    } else {
        const tempDiv = document.createElement('div'); // Create a temporary container for new text
        consoleOutput.appendChild(tempDiv);
        typeWriter(text, tempDiv, () => {
             // Scroll to bottom after typing finishes
             consoleOutput.scrollTop = consoleOutput.scrollHeight;
        });
    }
    // Ensure scroll to bottom even for immediate text
    consoleOutput.scrollTop = consoleOutput.scrollHeight;
}


function updateRoomDisplay() {
    if (!currentRoomId || !roomIndex[currentRoomId]) {
        console.error("Error: Invalid currentRoomId", currentRoomId);
        displayOutput("Error: Cannot find the current room.", true);
        return;
    }
    const room = roomIndex[currentRoomId];
    const useAfterText = transformedRooms.has(currentRoomId) && room.entry_text_after; // Determine which text to use

    // Don't clear previous output anymore
    // Display room name information
    displayOutput(`[${room.id}]`, true);

    // 2. Set background image
    const roomImageName = sanitizeForFilename(room.id);
    // Use 'after' image if the room has been transformed (is in transformedRooms set).
    // Otherwise, use 'before' image.
    const imageState = transformedRooms.has(currentRoomId) ? 'after' : 'before';
    const imageUrl = `rooms/${roomImageName}/${imageState}.png`;
    gameContainer.style.backgroundImage = `url('${imageUrl}')`;
    // Optional: Add a fallback background color or image
    gameContainer.style.backgroundColor = '#000'; // Fallback if image fails

    // 4. Display entry text with typewriter effect
    const textToDisplay = useAfterText ? room.entry_text_after : room.entry_text;

    // Create a container for room text
    const roomTextDiv = document.createElement('div');
    consoleOutput.appendChild(roomTextDiv);

    typeWriter(textToDisplay, roomTextDiv, () => {
        // Callback after room description is typed
        // Optionally add a slight pause or divider before the next prompt
    });
}

function showHelp() {
    const helpText = `Commands:
  **look**       – describe the current room again
  **inventory**  – list the things you're carrying
  **help**       – this message
  **save**       – save your progress
  **load**       – load your saved progress
  **quit**       – leave the game
Otherwise type one of the **bolded** action words you see.`;
    displayOutput(helpText, true); // Show help immediately
}

function showInventory() {
    if (inventory.size > 0) {
        displayOutput(`You are carrying: ${[...inventory].sort().join(', ')}`, true);
    } else {
        displayOutput("You have nothing.", true);
    }
}

function handleRiddleAnswer(attempt) {
     if (!currentRiddle) return;

     // Add the answer to the console output for history
     displayOutput(`> ${attempt}`, true); // Show answer in command history

     const riddle = currentRiddle;
     const room = roomIndex[currentRoomId]; // Get current room
     currentRiddle = null; // Clear riddle state
     isWaitingForAnswer = false; // No longer waiting

     if (attempt === riddle.answer.toLowerCase()) {
         // Create a temporary div for success text
         const successDiv = document.createElement('div');
         consoleOutput.appendChild(successDiv);

         // Type success text
         typeWriter(riddle.success_text, successDiv, () => {
             // After success text, handle item granting
             const token = riddle.gives_item || `${riddle.name}_solved`; // Use provided item or generate one
             if (token && !inventory.has(token)) { // Only add if not already present
                 inventory.add(token);
                 const inventoryDiv = document.createElement('div');
                 consoleOutput.appendChild(inventoryDiv);
                 // Type inventory message with callback for potential transformation
                 typeWriter(`(Added ${token} to inventory)`, inventoryDiv, () => {
                     // After inventory message, check for transformation
                     if (room && room.transform_text && !transformedRooms.has(currentRoomId)) {
                         const transformDiv = document.createElement('div');
                         consoleOutput.appendChild(transformDiv);
                         typeWriter(room.transform_text, transformDiv, () => {
                              transformedRooms.add(currentRoomId); // Mark transformed AFTER text is shown
                              updateBackgroundImage(); // Update background immediately
                              consoleOutput.scrollTop = consoleOutput.scrollHeight;
                         });
                     } else if (room && room.entry_text_after && !transformedRooms.has(currentRoomId)) {
                         // Fallback: if no transform_text but entry_text_after exists, mark transformed
                         transformedRooms.add(currentRoomId);
                         updateBackgroundImage(); // Update background immediately
                         // Consider if we need to update display here? Probably not,
                         // as the change will be seen on next entry.
                     } else {
                          consoleOutput.scrollTop = consoleOutput.scrollHeight; // Scroll if no further text
                     }
                 });
             } else {
                 // If no item OR item already present, check directly for transformation
                  if (room && room.transform_text && !transformedRooms.has(currentRoomId)) {
                       const transformDiv = document.createElement('div');
                       consoleOutput.appendChild(transformDiv);
                       typeWriter(room.transform_text, transformDiv, () => {
                            transformedRooms.add(currentRoomId); // Mark transformed AFTER text is shown
                            updateBackgroundImage(); // Update background immediately
                            consoleOutput.scrollTop = consoleOutput.scrollHeight;
                       });
                   } else if (room && room.entry_text_after && !transformedRooms.has(currentRoomId)) {
                       transformedRooms.add(currentRoomId);
                       updateBackgroundImage(); // Update background immediately
                       consoleOutput.scrollTop = consoleOutput.scrollHeight;
                   } else {
                       consoleOutput.scrollTop = consoleOutput.scrollHeight;
                   }
             }
         });
     } else {
         displayOutput("That doesn't seem right.");
         commandInput.focus(); // Refocus after wrong answer
     }
     commandInput.placeholder = ""; // Clear placeholder
}

// ADD: Save game state function
function saveGameState() {
    try {
        const state = {
            currentRoomId: currentRoomId,
            inventory: Array.from(inventory), // Convert Set to Array for JSON
            transformedRooms: Array.from(transformedRooms) // Convert Set to Array
        };
        localStorage.setItem(SAVE_KEY, JSON.stringify(state));
        displayOutput("Game saved.", true);
    } catch (error) {
        console.error("Error saving game:", error);
        displayOutput("Failed to save game.", true);
    }
     // Ensure input stays focused after saving
     if (!isWaitingForAnswer && !isWaitingForEnter) commandInput.focus();
}

// ADD: Load game state function
function loadGameState() {
    try {
        const savedState = localStorage.getItem(SAVE_KEY);
        if (savedState) {
            const state = JSON.parse(savedState);

            // Validate loaded state (basic check)
            if (!state.currentRoomId || !roomIndex[state.currentRoomId] || !Array.isArray(state.inventory) || !Array.isArray(state.transformedRooms)) {
                 throw new Error("Invalid or corrupted save data.");
            }

            currentRoomId = state.currentRoomId;
            inventory = new Set(state.inventory); // Convert Array back to Set
            transformedRooms = new Set(state.transformedRooms); // Convert Array back to Set

            // Clear console and display loaded room
            consoleOutput.innerHTML = '';
            updateRoomDisplay(); // Display the loaded room state

            // Give confirmation after room display starts
             setTimeout(() => {
                displayOutput("Game loaded.", true);
                 displayOutput("» Type a command to interact (or type **help**).", true);
                if (!isWaitingForAnswer && !isWaitingForEnter) commandInput.focus();
             }, 50); // Small delay ensure room text starts first


        } else {
            displayOutput("No saved game found.", true);
             if (!isWaitingForAnswer && !isWaitingForEnter) commandInput.focus();
        }
    } catch (error) {
        console.error("Error loading game:", error);
        displayOutput(`Failed to load game: ${error.message}`, true);
         if (!isWaitingForAnswer && !isWaitingForEnter) commandInput.focus();
    }
}

function processCommand(cmd) {
    cmd = cmd.toLowerCase().trim();
    if (!cmd) return;

     // If waiting for a riddle answer
    if (isWaitingForAnswer) {
        handleRiddleAnswer(cmd);
        return;
    }

    // Add the command to the console output for history
    displayOutput(`> ${cmd}`, true); // Show command immediately


    if (cmd === 'quit' || cmd === 'exit') {
        displayOutput("Goodbye!", true);
        commandInput.disabled = true;
        return;
    }
    if (cmd === 'help') {
        showHelp();
        return;
    }
    if (cmd === 'inventory') {
        showInventory();
        return;
    }
    // ADD: Handle save/load commands
    if (cmd === 'save') {
        saveGameState();
        return;
    }
    if (cmd === 'load') {
        loadGameState();
        return;
    }
    // ADD: Handle 'look' command
    if (cmd === 'look') {
        const room = roomIndex[currentRoomId];
        if (room) {
            const useAfterText = transformedRooms.has(currentRoomId) && room.entry_text_after;
            const textToDisplay = useAfterText ? room.entry_text_after : room.entry_text;
            displayOutput(`[${room.id}]`, true); // Show room ID immediately
            // Display room description with typewriter effect
            const roomTextDiv = document.createElement('div');
            consoleOutput.appendChild(roomTextDiv);
            typeWriter(textToDisplay, roomTextDiv, () => {
                // Optionally, re-display the prompt after looking
                // displayOutput("» Type a command to interact (or type **help**).", true);
            });
        } else {
            displayOutput("Cannot describe the current location.", true); // Fallback
        }
        return; // Command handled
    }


    const room = roomIndex[currentRoomId];
    if (!room) return; // Should not happen

    // Try matching command with items (check if this needs update)
    for (const item of room.items || []) {
        if (item.name.toLowerCase() === cmd) {
            switch (item.type) {
                case "hint":
                    displayOutput(item.text);
                    break;
                case "inventory":
                    { // Use block scope for const
                        const descDiv = document.createElement('div');
                        consoleOutput.appendChild(descDiv);
                        typeWriter(item.description, descDiv, () => {
                            if (item.gives_item) {
                                const itemDiv = document.createElement('div');
                                consoleOutput.appendChild(itemDiv);
                                if (!inventory.has(item.gives_item)) {
                                    inventory.add(item.gives_item);
                                    typeWriter(`(You take the ${item.gives_item})`, itemDiv, () => {
                                        // Check for transformation after taking item
                                        const room = roomIndex[currentRoomId];
                                        if (room && room.transform_text && !transformedRooms.has(currentRoomId)) {
                                            // If taking the item itself triggers the main transformation
                                            const transformDiv = document.createElement('div');
                                            consoleOutput.appendChild(transformDiv);
                                            typeWriter(room.transform_text, transformDiv, () => {
                                                transformedRooms.add(currentRoomId);
                                                updateBackgroundImage(); // Update background immediately
                                                consoleOutput.scrollTop = consoleOutput.scrollHeight;
                                            });
                                        } else if (room && room.entry_text_after && !transformedRooms.has(currentRoomId)) {
                                            // If taking the item implies a state change for entry_text_after later
                                            // but without an immediate transform_text
                                            transformedRooms.add(currentRoomId);
                                            updateBackgroundImage(); // Update background immediately
                                            consoleOutput.scrollTop = consoleOutput.scrollHeight;
                                        } else {
                                             consoleOutput.scrollTop = consoleOutput.scrollHeight;
                                        }
                                    });
                                } else {
                                    typeWriter(`(You already have the ${item.gives_item})`, itemDiv, () => {
                                        consoleOutput.scrollTop = consoleOutput.scrollHeight;
                                    });
                                }
                            } else {
                                 consoleOutput.scrollTop = consoleOutput.scrollHeight; // Scroll if no item given
                            }
                        });
                    }
                    break;
                case "riddle":
                    displayOutput(item.prompt);
                    isWaitingForAnswer = true;
                    currentRiddle = item;
                    commandInput.placeholder = "Enter your answer...";
                    break;
                default:
                    displayOutput("[Unknown item type]", true);
            }
            return; // Command handled
        }
    }

    // Try matching command with exits
    for (const exit of room.exits || []) {
        if (exit.name.toLowerCase() === cmd) {
             if (exit.locked) {
                 const requiredKey = exit.key;
                 if (requiredKey && inventory.has(requiredKey)) {
                     const room = roomIndex[currentRoomId]; // Get current room data
                     const roomAlreadyTransformed = transformedRooms.has(currentRoomId);
                     const unlockDiv = document.createElement('div'); // Div for unlock message
                     consoleOutput.appendChild(unlockDiv);

                     // Step 1: Show unlock message (if appropriate) and unlock logically
                     const unlockMsg = `You use the ${requiredKey} to unlock the ${exit.name}.`;
                     exit.locked = false; // Unlock permanently (within this session)

                     const showUnlockMessageAndProceed = () => {
                         // Step 2: Check if there's a transformation text to show
                         if (room.transform_text && !roomAlreadyTransformed) {
                             const transformDiv = document.createElement('div');
                             consoleOutput.appendChild(transformDiv);
                             typeWriter(room.transform_text, transformDiv, () => {
                                 transformedRooms.add(currentRoomId); // Mark transformed AFTER text shown
                                 updateBackgroundImage(); // Update background immediately
                                 // Player must enter command again to move
                                 consoleOutput.scrollTop = consoleOutput.scrollHeight;
                                 // Re-enable input if needed after transform text
                                 // Only focus if not waiting for other input
                                 if (!isWaitingForEnter && !isWaitingForAnswer) commandInput.focus();
                             });
                         } else {
                                 // Step 3: No transform text, or already transformed - prepare to move
                                 if (room.entry_text_after && !roomAlreadyTransformed) {
                                     transformedRooms.add(currentRoomId); // Mark transformed if applicable
                                     updateBackgroundImage(); // Update background immediately
                                 }
                                 const dest = exit.to;
                                 if (dest === gameData.end_room) {
                                     displayOutput("\nYou step through the portal and feel reality twist…\nCongratulations – you have escaped the mansion!", true);
                                     commandInput.disabled = true;
                                     return; // End game
                                 }
                                 if (roomIndex[dest]) {
                                     // Prepare to move, but wait for Enter
                                     currentRoomId = dest; // Set the new room ID immediately
                                     const nextRoomName = roomIndex[dest].id; // Get the name for the message
                                     displayOutput(`You approach the ${exit.name} leading to the ${nextRoomName}...<br>Press ENTER to continue.`, true);
                                     isWaitingForEnter = true;
                                     commandInput.placeholder = "Press ENTER";
                                     commandInput.focus(); // Input is now enabled, focus works
                                 } else {
                                     console.error("Error: Destination room not found:", dest);
                                     displayOutput("That path leads nowhere (Error in game data).", true);
                                      if (!isWaitingForAnswer && !isWaitingForEnter) commandInput.focus(); // Refocus on error
                                 }
                             }
                         };

                         if (!roomAlreadyTransformed) {
                            // Type the unlock message, then proceed in callback
                            // REMOVE: Disable input during unlock message typing
                            // REMOVE: commandInput.disabled = true;
                            typeWriter(unlockMsg, unlockDiv, showUnlockMessageAndProceed);
                         } else {
                            // Room was already transformed, skip unlock message, just proceed
                            // REMOVE: commandInput.disabled = true; // Disable input briefly while processing
                            showUnlockMessageAndProceed();
                         }

                 } else {
                     displayOutput("It's locked.");
                 }
            } else {
                 // Exit is not locked, prepare to move
                 const dest = exit.to;
                 if (dest === gameData.end_room) {
                     displayOutput("\nYou step through the portal and feel reality twist…\nCongratulations – you have escaped the mansion!", true);
                     commandInput.disabled = true;
                     return; // End game
                 }
                 if (roomIndex[dest]) {
                    // Prepare to move, but wait for Enter
                    currentRoomId = dest; // Set the new room ID immediately
                    const nextRoomName = roomIndex[dest].id; // Get the name for the message
                    displayOutput(`You approach the ${exit.name} leading to the ${nextRoomName}...<br>Press ENTER to continue.`, true);
                    isWaitingForEnter = true;
                    commandInput.placeholder = "Press ENTER";
                    commandInput.focus(); // Input is now enabled, focus works
                 } else {
                    console.error("Error: Destination room not found:", dest);
                    displayOutput("That path leads nowhere (Error in game data).", true);
                 }
            }
            return; // Command handled (either preparing to move, showed transform, or failed)
        }
    }

    // Command not understood
    displayOutput("I don't understand that command.", true);
}


// --- Initialization ---

async function loadGame() {
    try {
        const response = await fetch('rooms.json');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        gameData = await response.json();

        // Validate basic structure
        if (!gameData.start_room || !gameData.rooms) {
             throw new Error("Invalid game data: Missing 'start_room' or 'rooms'.");
        }

        // Index rooms by ID
        roomIndex = gameData.rooms.reduce((acc, room) => {
            acc[room.id] = room;
            return acc;
        }, {});

         if (!roomIndex[gameData.start_room]) {
              throw new Error("Invalid game data: 'start_room' ID not found in rooms list.");
         }

        currentRoomId = gameData.start_room;
        // Clear output and set cursor to enabled before initial display
        consoleOutput.innerHTML = '';
        commandInput.disabled = false;
        
        // Ensure the room is properly displayed
        updateRoomDisplay(); // Initial room display
        
        // Add a slight delay before showing the help prompt
        setTimeout(() => {
            displayOutput("» Type a command to interact (or type **help**).", true);
        }, 500);

    } catch (error) {
        console.error("Failed to load game data:", error);
        displayOutput(`Error loading game: ${error.message}\nPlease check rooms.json and ensure it's accessible.`, true);
        commandInput.disabled = true; // Disable input if game fails to load
    }
}

// --- Event Listeners ---

commandInput.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
        event.preventDefault(); // Prevent default form submission/newline

        // Handle waiting for Enter first (room transition)
        if (isWaitingForEnter) {
            // ADD: Cancel any ongoing typewriter from the "Press ENTER" message or previous action
            if (activeTypewriterTimeoutId) {
                 clearTimeout(activeTypewriterTimeoutId);
                 if (activeTypewriterElement) {
                     activeTypewriterElement.innerHTML = activeTypewriterFullText; // Finish immediately
                 }
                 activeTypewriterTimeoutId = null;
                 activeTypewriterElement = null;
                 activeTypewriterFullText = '';
            }

            consoleOutput.innerHTML = ''; // Clear the console
            isWaitingForEnter = false;
            commandInput.placeholder = "";
            updateRoomDisplay(); // Now display the new room
             // Add the prompt after a short delay to ensure display is updated
             setTimeout(() => {
                displayOutput("» Type a command to interact (or type **help**).", true);
                if (!isWaitingForAnswer) commandInput.focus(); // Focus only if not waiting for riddle
            }, 50); // Small delay might be needed
            return; // Handled the Enter press for room transition
        }

        // ADD: Cancel any active typewriter before processing the command
        if (activeTypewriterTimeoutId) {
             clearTimeout(activeTypewriterTimeoutId);
             if (activeTypewriterElement) {
                 activeTypewriterElement.innerHTML = activeTypewriterFullText; // Finish immediately
             }
             activeTypewriterTimeoutId = null;
             activeTypewriterElement = null;
             activeTypewriterFullText = '';
        }

        const command = commandInput.value;
        // Only process if not waiting for an answer (riddle)
        if (!isWaitingForAnswer) {
             processCommand(command);
        } else {
             handleRiddleAnswer(command); // Handle riddle answer if waiting
        }
        commandInput.value = ''; // Clear input field

    } else if (event.key === 'Tab') {
        event.preventDefault(); // Prevent default tab behavior (changing focus)

        if (isWaitingForAnswer) {
            return; // Don't autocomplete during typing or riddles
        }

        const currentText = commandInput.value.toLowerCase();
        if (!currentText) {
            return; // No text to complete
        }

        const room = roomIndex[currentRoomId];
        if (!room) return; // Should not happen

        const possibleCompletions = getAvailableActions(room, true); // Include global commands

        const matches = possibleCompletions.filter(cmd => cmd.startsWith(currentText));

        if (matches.length === 1) {
            // Unambiguous completion
            commandInput.value = matches[0];
        }
        // Optional: If multiple matches, could show them? For now, only complete unambiguous.
    }
});

// --- Start Game ---
loadGame(); 