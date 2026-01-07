"""
Game renderer for the delivery agent demo.
Creates an HTML5/CSS animated view using sprite sheets with frame-by-frame walking animation.
"""

import base64
import os
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=16)
def load_sprite_base64(filename: str) -> str:
    """Load a sprite image as base64 for embedding in HTML.

    Cached to avoid repeated disk reads and base64 encoding.
    """
    sprite_path = Path(__file__).parent / "sprites" / filename
    if sprite_path.exists():
        with open(sprite_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    return ""


def generate_game_html(
    floor: int,
    side: str,  # "front" or "back"
    current_action: str = None,
    businesses: dict = None,
    prev_floor: int = None,
    prev_side: str = None,
    difficulty: str = "easy",  # "easy", "medium", "hard"
) -> str:
    """
    Generate the HTML/JS for the animated game view using sprite sheets.
    Implements frame-by-frame walking animation with step-by-step movement.
    """

    # Load sprites based on difficulty
    building_sprites = {
        "easy": "building_easy.png",
        "medium": "building_medium.png",
        "hard": "building_hard.png",
    }
    building_b64 = load_sprite_base64(building_sprites.get(difficulty, "building_easy.png"))
    agent_b64 = load_sprite_base64("agent_transparent.png")

    # Default businesses if not provided
    if businesses is None:
        businesses = {
            (1, "front"): "Lobby & Reception",
            (1, "back"): "Mail Room",
            (2, "front"): "Acme Accounting",
            (2, "back"): "Byte Size Games",
            (3, "front"): "TechStart Labs",
            (3, "back"): "Wellness Center",
            (4, "front"): "Legal Eagles Law",
            (4, "back"): "Pixel Perfect Design",
            (5, "front"): "Executive Suite",
            (5, "back"): "Cloud Nine Cafe",
        }

    # Convert businesses to JS object
    businesses_js = "{\n"
    for (f, s), name in businesses.items():
        businesses_js += f'    "{f}_{s}": "{name}",\n'
    businesses_js += "}"

    html = f'''
<!DOCTYPE html>
<html>
<head>
<style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
        background: #d4d4c4;
        display: flex;
        justify-content: center;
        align-items: center;
        overflow: hidden;
        font-family: 'Courier New', monospace;
    }}
    #gameContainer {{
        position: relative;
        width: 800px;
        height: 550px;
        border: 4px solid #5a5a4a;
        border-radius: 4px;
        overflow: hidden;
        background: #d4d4c4;
    }}
    #buildingImg {{
        position: absolute;
        width: 100%;
        height: 100%;
        top: 0;
        left: 0;
        object-fit: cover;
        image-rendering: pixelated;
    }}

    /* Agent sprite */
    #agentContainer {{
        position: absolute;
        width: 60px;
        height: 80px;
        z-index: 100;
    }}
    #agentImg {{
        width: 100%;
        height: 100%;
        object-fit: contain;
        image-rendering: pixelated;
    }}

    /* Idle bounce animation */
    #agentContainer.idle {{
        animation: bounce 0.8s ease-in-out infinite;
    }}

    /* Walking animation - bob up and down with slight rotation */
    #agentContainer.walking {{
        animation: walk 0.15s linear infinite;
    }}

    @keyframes bounce {{
        0%, 100% {{ transform: translateY(0); }}
        50% {{ transform: translateY(-3px); }}
    }}

    @keyframes walk {{
        0% {{ transform: translateY(0) rotate(0deg); }}
        25% {{ transform: translateY(-5px) rotate(-3deg); }}
        50% {{ transform: translateY(0) rotate(0deg); }}
        75% {{ transform: translateY(-5px) rotate(3deg); }}
        100% {{ transform: translateY(0) rotate(0deg); }}
    }}

    /* Flip agent when facing left */
    #agentContainer.facing-left #agentImg {{
        transform: scaleX(-1);
    }}

    /* Indicators */
    #floorIndicator {{
        position: absolute;
        top: 10px;
        left: 10px;
        background: rgba(20,20,30,0.9);
        color: #64b5f6;
        padding: 10px 16px;
        border-radius: 4px;
        font-size: 14px;
        font-weight: bold;
        z-index: 200;
        border: 2px solid #64b5f6;
    }}
    #locationIndicator {{
        position: absolute;
        top: 10px;
        right: 10px;
        background: rgba(20,20,30,0.9);
        color: #81c784;
        padding: 10px 16px;
        border-radius: 4px;
        font-size: 12px;
        z-index: 200;
        border: 2px solid #81c784;
        max-width: 220px;
        text-align: right;
    }}
    #actionIndicator {{
        position: absolute;
        bottom: 12px;
        left: 50%;
        transform: translateX(-50%);
        background: rgba(20,20,30,0.95);
        color: #ffd54f;
        padding: 10px 24px;
        border-radius: 20px;
        font-size: 12px;
        z-index: 200;
        border: 2px solid #ffd54f;
        opacity: 0;
        transition: opacity 0.2s;
        white-space: nowrap;
    }}
    #actionIndicator.active {{
        opacity: 1;
    }}
    #sideIndicator {{
        position: absolute;
        bottom: 12px;
        left: 10px;
        background: rgba(20,20,30,0.9);
        color: #ce93d8;
        padding: 10px 16px;
        border-radius: 4px;
        font-size: 11px;
        z-index: 200;
        border: 2px solid #ce93d8;
    }}

    /* Nameplate popup for look_at_business */
    #nameplatePopup {{
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        background: linear-gradient(145deg, #c9a227, #a67c00);
        color: #1a1a1a;
        padding: 20px 40px;
        border-radius: 8px;
        font-size: 18px;
        font-weight: bold;
        z-index: 300;
        border: 4px solid #8b6914;
        box-shadow: 0 8px 32px rgba(0,0,0,0.4), inset 0 2px 4px rgba(255,255,255,0.3);
        text-align: center;
        opacity: 0;
        transition: opacity 0.3s;
        pointer-events: none;
    }}
    #nameplatePopup.visible {{
        opacity: 1;
    }}
    #nameplatePopup .label {{
        font-size: 10px;
        color: #4a3a00;
        margin-bottom: 8px;
        text-transform: uppercase;
        letter-spacing: 2px;
    }}
</style>
</head>
<body>

<div id="gameContainer">
    <img id="buildingImg" src="data:image/png;base64,{building_b64}" alt="Building">

    <div id="floorIndicator">Floor {floor}</div>
    <div id="locationIndicator"></div>
    <div id="actionIndicator"></div>
    <div id="sideIndicator"></div>

    <div id="nameplatePopup">
        <div class="label">Business Name</div>
        <div id="nameplateName"></div>
    </div>

    <div id="agentContainer" class="idle">
        <img id="agentImg" src="data:image/png;base64,{agent_b64}" alt="Agent">
    </div>
</div>

<script>
const businesses = {businesses_js};

// State - current target position
const targetFloor = {floor};
const targetSide = "{side}";
const currentAction = "{current_action or ''}";

// Previous position (for animation)
const prevFloor = {prev_floor if prev_floor else floor};
const prevSide = "{prev_side if prev_side else side}";

// Animation state
let agentX = 0;
let agentY = 0;
let targetX = 0;
let targetY = 0;
let isWalking = false;
let walkAnimTimer = null;

// Elements
const agentContainer = document.getElementById('agentContainer');
const agentImg = document.getElementById('agentImg');
const floorIndicator = document.getElementById('floorIndicator');
const locationIndicator = document.getElementById('locationIndicator');
const actionIndicator = document.getElementById('actionIndicator');
const sideIndicator = document.getElementById('sideIndicator');
const nameplatePopup = document.getElementById('nameplatePopup');
const nameplateName = document.getElementById('nameplateName');

// Position constants - vary by difficulty
const difficulty = "{difficulty}";
let FLOOR_HEIGHT, FLOOR_BASE, LEFT_DOOR_X, RIGHT_DOOR_X, ELEVATOR_X, WALK_SPEED;

if (difficulty === "easy") {{
    // Simple hallway building
    FLOOR_HEIGHT = 105;
    FLOOR_BASE = 45;
    LEFT_DOOR_X = 120;
    RIGHT_DOOR_X = 620;
    ELEVATOR_X = 370;
    WALK_SPEED = 5;
}} else if (difficulty === "medium") {{
    // Industrial building with ladders
    FLOOR_HEIGHT = 85;
    FLOOR_BASE = 35;
    LEFT_DOOR_X = 100;
    RIGHT_DOOR_X = 550;
    ELEVATOR_X = 325;
    WALK_SPEED = 5;
}} else {{
    // Space station
    FLOOR_HEIGHT = 75;
    FLOOR_BASE = 50;
    LEFT_DOOR_X = 80;
    RIGHT_DOOR_X = 650;
    ELEVATOR_X = 380;
    WALK_SPEED = 6;
}}

function getFloorBottom(floor) {{
    return FLOOR_BASE + (floor - 1) * FLOOR_HEIGHT;
}}

function getTargetX(side) {{
    if (side === "front") return LEFT_DOOR_X;
    if (side === "back") return RIGHT_DOOR_X;
    return ELEVATOR_X;  // "middle" - elevator area
}}

function startWalkAnimation() {{
    if (isWalking) return;
    isWalking = true;
    agentContainer.classList.remove('idle');
    agentContainer.classList.add('walking');
}}

function stopWalkAnimation() {{
    isWalking = false;
    agentContainer.classList.remove('walking');
    agentContainer.classList.add('idle');
}}

function showNameplate(businessName) {{
    nameplateName.textContent = businessName;
    nameplatePopup.classList.add('visible');
    setTimeout(() => {{
        nameplatePopup.classList.remove('visible');
    }}, 2000);
}}

function updateIndicators() {{
    floorIndicator.textContent = 'Floor ' + targetFloor;
    if (targetSide === 'front') {{
        sideIndicator.textContent = '◀ Left Side';
    }} else if (targetSide === 'back') {{
        sideIndicator.textContent = 'Right Side ▶';
    }} else {{
        sideIndicator.textContent = '🛗 Elevator';
    }}

    const bizName = targetSide === 'middle' ? 'Middle Hallway' : (businesses[targetFloor + '_' + targetSide] || 'Unknown');
    locationIndicator.innerHTML = '<strong>' + bizName + '</strong>';

    if (currentAction) {{
        let actionText = currentAction.replace(/_/g, ' ');
        actionText = actionText.charAt(0).toUpperCase() + actionText.slice(1);
        actionIndicator.textContent = '⚡ ' + actionText;
        actionIndicator.classList.add('active');

        // Show nameplate popup for look_at_business action
        if (currentAction === 'look_at_business') {{
            showNameplate(bizName);
        }}
    }} else {{
        actionIndicator.classList.remove('active');
    }}
}}

function animateAgent() {{
    // Start at previous position
    agentX = getTargetX(prevSide);
    agentY = getFloorBottom(prevFloor);
    agentContainer.style.left = agentX + 'px';
    agentContainer.style.bottom = agentY + 'px';

    // Calculate target position
    targetX = getTargetX(targetSide);
    targetY = getFloorBottom(targetFloor);

    // Set initial facing direction
    if (prevSide === "back") {{
        agentContainer.classList.add('facing-left');
    }}

    // If position changed, animate
    if (agentX !== targetX || agentY !== targetY) {{
        // For floor changes (elevator), just move vertically
        if (prevFloor !== targetFloor) {{
            // Move to elevator first, then change floor, then move to door
            setTimeout(() => {{
                // Walk to elevator
                walkTo(ELEVATOR_X, () => {{
                    // Change floor (instant vertical move with animation effect)
                    agentContainer.style.transition = 'bottom 0.5s ease-in-out';
                    agentContainer.style.bottom = targetY + 'px';
                    agentY = targetY;

                    setTimeout(() => {{
                        agentContainer.style.transition = '';
                        // Walk to target door
                        walkTo(targetX, null);
                    }}, 600);
                }});
            }}, 100);
        }} else {{
            // Same floor - just walk horizontally
            setTimeout(() => {{
                walkTo(targetX, null);
            }}, 100);
        }}
    }}
}}

function walkTo(destX, callback) {{
    targetX = destX;

    if (Math.abs(agentX - targetX) < 2) {{
        agentX = targetX;
        agentContainer.style.left = agentX + 'px';
        stopWalkAnimation();
        if (callback) callback();
        return;
    }}

    // Set facing direction
    if (targetX > agentX) {{
        agentContainer.classList.remove('facing-left');
    }} else {{
        agentContainer.classList.add('facing-left');
    }}

    startWalkAnimation();

    function step() {{
        if (Math.abs(agentX - targetX) < WALK_SPEED) {{
            agentX = targetX;
            agentContainer.style.left = agentX + 'px';
            stopWalkAnimation();
            if (callback) callback();
            return;
        }}

        if (agentX < targetX) {{
            agentX += WALK_SPEED;
        }} else {{
            agentX -= WALK_SPEED;
        }}
        agentContainer.style.left = agentX + 'px';
        requestAnimationFrame(step);
    }}

    requestAnimationFrame(step);
}}

function init() {{
    updateIndicators();
    animateAgent();
}}

// Initialize
init();
</script>

</body>
</html>
'''
    return html
