#!/usr/bin/env python3
"""
OpenAI Agent Fitness Coach with Hindsight Memory Backend.

This demonstrates how to use OpenAI Agents with Hindsight as a memory layer.
The OpenAI Agent handles conversation logic, while Hindsight provides
sophisticated memory storage and retrieval.
"""
import os
import sys
import json
import time
from openai import OpenAI
from memory_tools import MEMORY_TOOLS, FUNCTION_MAP

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Assistant ID (will be set by setup_openai_coach.py)
ASSISTANT_ID_FILE = ".openai_assistant_id"


def get_or_create_assistant():
    """Get existing assistant or create a new one."""

    # Try to load existing assistant ID
    if os.path.exists(ASSISTANT_ID_FILE):
        with open(ASSISTANT_ID_FILE, 'r') as f:
            assistant_id = f.read().strip()

        try:
            assistant = client.beta.assistants.retrieve(assistant_id)
            print(f"Using existing OpenAI Assistant: {assistant.name}")
            return assistant
        except:
            print("Saved assistant not found, creating new one...")

    # Create new assistant

    assistant = client.beta.assistants.create(
        name="Fitness Coach with Hindsight",
        instructions="""You are an experienced and supportive fitness coach.

**MOST IMPORTANT RULE - USER PREFERENCES (READ THIS FIRST):**

BEFORE giving ANY training advice, you MUST:
1. Retrieve memories to check for user preferences
2. Identify activities the user DISLIKES
3. Identify activities the user LOVES
4. NEVER recommend disliked activities - find alternatives
5. EMPHASIZE loved activities in your recommendations

EXAMPLES OF WHAT TO DO:
- User says: "I don't enjoy tempo runs"
   -> DO: Recommend intervals, fartleks, progression runs, hill sprints
   -> DON'T: Suggest tempo runs under ANY name (steady state, threshold, etc.)

- User says: "I love interval workouts"
   -> DO: Prioritize intervals (400m, 800m, 1K repeats, pyramids)
   -> DO: Mention why intervals work well for them

NEVER DO THIS:
- Ignoring stated preferences
- Recommending disliked activities "just once" or "to try"
- Renaming disliked activities to sneak them in
- Suggesting disliked activities are "necessary"

This is THE MOST IMPORTANT rule. Violating user preferences destroys trust.

**CRITICAL - Storing What Users Tell You:**
- When users tell you about workouts, meals, goals, or PREFERENCES, ALWAYS store them using store_memory()
- Extract key details: distances, times, paces, foods, quantities, how they felt, likes/dislikes
- Store as memory_type "world" for things that happened (workouts, meals)
- Store as memory_type "agent" for goals and intentions
- Be thorough - this data will be used for future coaching

**CRITICAL - YOU MUST STORE YOUR OWN OBSERVATIONS:**
- EVERY TIME you give advice, you MUST store it using store_memory() with type "opinion"
- EVERY TIME you recognize an achievement, you MUST store it using store_memory() with type "opinion"
- EVERY TIME you make an observation, you MUST store it using store_memory() with type "opinion"
- This is NOT optional - you MUST do this in EVERY response where you give advice or recognize progress
- Format: store_memory(content="I advised/observed/noted that...", memory_type="opinion", context="coaching")

**IMPORTANT - Retrieving Context:**
- ALWAYS use memory tools to get relevant context before giving advice
- When using retrieve_memories():
  * DO NOT specify fact_types - let it search ALL types
  * Use top_k of at least 20-30 to get comprehensive context
  * Look for user PREFERENCES (what they like/don't like) <- CRITICAL
- Search for recent workouts, meals, goals, preferences, and past observations
- Base your advice on the user's actual data AND preferences
- Be specific and reference their actual activities

**Personality:**
- Supportive and encouraging
- Disciplined and structured
- Knowledgeable but not preachy
- Focus on sustainable progress over quick fixes
- Celebrate achievements enthusiastically!

**RESPONSE STYLE - KEEP IT CONCISE:**
- Maximum 3-4 short paragraphs per response
- Be direct and actionable
- Use bullet points when listing items
- Avoid lengthy explanations unless specifically asked
- Get to the point quickly

**Conversation Flow (FOLLOW THIS EXACTLY):**
1. When user tells you something -> IMMEDIATELY store it with store_memory() (type: world/agent)
2. When asked for advice:
   a. First retrieve context with retrieve_memories() or search functions
   b. CHECK FOR PREFERENCES - note what they like/dislike
   c. Analyze their patterns and progress
   d. Give personalized advice that RESPECTS preferences (NO disliked activities!)
   e. IMMEDIATELY store your advice with store_memory() (type: opinion) <- MANDATORY
3. When recognizing achievement -> IMMEDIATELY store it with store_memory() (type: opinion)
4. Keep responses SHORT and actionable

REMEMBER: You must call store_memory() with type="opinion" AFTER giving advice or recognizing achievements!
""",
        model="gpt-4o-mini",
        tools=MEMORY_TOOLS
    )

    # Save assistant ID
    with open(ASSISTANT_ID_FILE, 'w') as f:
        f.write(assistant.id)


    return assistant


def create_thread():
    """Create a new conversation thread."""
    thread = client.beta.threads.create()
    return thread


def execute_function_call(function_name: str, arguments: dict):
    """Execute a function call from the assistant."""

    # Show abbreviated version for store_memory (can be verbose)
    if function_name == "store_memory":
        content_preview = arguments.get('content', '')[:60] + "..."
        print(f"   Storing: {content_preview}")
        print(f"       memory_type: {arguments.get('memory_type', 'N/A')}")
        print(f"       context: {arguments.get('context', 'N/A')}")
    else:
        print(f"   Calling: {function_name}({json.dumps(arguments, indent=2)})")

    if function_name in FUNCTION_MAP:
        result = FUNCTION_MAP[function_name](**arguments)

        # Different messages for different function types
        if function_name == "store_memory":
            if result.get('success'):
                print(f"   Stored successfully")
                print()
            else:
                print(f"   Storage failed: {result.get('error', 'Unknown error')}")
        else:
            num_results = len(result.get('results', []))

            # Count memory types in results
            memory_types = {}
            for item in result.get('results', []):
                mem_type = item.get('fact_type', 'unknown')
                memory_types[mem_type] = memory_types.get(mem_type, 0) + 1

            # Display with breakdown
            type_str = ", ".join([f"{count} {mtype}" for mtype, count in memory_types.items()])
            if memory_types:
                print(f"   Retrieved {num_results} memories")
                print()
            else:
                print(f"   Retrieved {num_results} memories")

        return result
    else:
        print(f"   ERROR: Unknown function: {function_name}")
        return {"error": f"Unknown function: {function_name}"}


def _store_coach_response(response_text: str, user_message: str, show_storage: bool = True) -> None:
    """
    Automatically store coach's response as an opinion memory.
    This ensures all coaching advice is captured even if the model forgets to do it.
    """
    from memory_tools import store_memory
    from datetime import datetime

    if not response_text or len(response_text) < 20:
        return

    # Determine if this is advice, achievement recognition, or observation
    response_lower = response_text.lower()
    user_lower = user_message.lower()

    # Skip if it's just a greeting or acknowledgment
    if len(response_text) < 50:
        return

    # Create a summary of the coach's response
    if "goal" in user_lower and ("achieve" in user_lower or "help" in user_lower):
        context = "coaching-advice"
        content = f"I provided training guidance for the user's goal. Recommended: {response_text[:200]}"
    elif "achieved" in response_lower or "congratulations" in response_lower or "great job" in response_lower:
        context = "coaching-observation"
        content = f"I recognized the user's achievement: {response_text[:200]}"
    elif any(word in response_lower for word in ["recommend", "suggest", "focus on", "try", "should"]):
        context = "coaching-advice"
        content = f"I advised: {response_text[:200]}"
    else:
        context = "coaching-observation"
        content = f"I observed: {response_text[:200]}"

    # Store and optionally show the storage
    try:
        if show_storage:
            print(f"   Storing coach opinion: {content[:80]}...")
        store_memory(
            content=content,
            memory_type="opinion",
            context=context,
            event_date=datetime.now().isoformat()
        )
        if show_storage:
            print(f"   Stored coach observation")
            print()
    except Exception as e:
        # Fail silently - don't interrupt the conversation
        if show_storage:
            print(f"   Could not store: {e}")
        pass


def chat(assistant, thread_id: str, user_message: str, stream: bool = True) -> str:
    """
    Send a message to the assistant and get a response.

    Args:
        assistant: OpenAI Assistant instance
        thread_id: Conversation thread ID
        user_message: User's question/message
        stream: Whether to stream the response (default: True)

    Returns:
        Assistant's response text
    """

    # Safety check: Ensure no active runs on this thread
    try:
        runs = client.beta.threads.runs.list(thread_id=thread_id, limit=1)
        if runs.data and runs.data[0].status in ["in_progress", "requires_action"]:
            # Silently wait for previous run to finish (common with streaming)
            active_run_id = runs.data[0].id
            for _ in range(15):
                run = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=active_run_id)
                if run.status not in ["in_progress", "requires_action"]:
                    break
                time.sleep(1)
            else:
                # Timeout - cancel the run
                client.beta.threads.runs.cancel(thread_id=thread_id, run_id=active_run_id)
                time.sleep(2)
    except Exception as e:
        # Silently handle - normal cleanup
        pass

    # Add user message to thread
    client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=user_message
    )

    if not stream:
        # Non-streaming mode (original behavior)
        run = client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=assistant.id
        )

        print("   Coach is thinking...")

        while True:
            run = client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run.id
            )

            if run.status == "completed":
                break
            elif run.status == "requires_action":
                print("   Retrieving memories...")

                tool_outputs = []
                for tool_call in run.required_action.submit_tool_outputs.tool_calls:
                    function_name = tool_call.function.name
                    arguments = json.loads(tool_call.function.arguments)
                    result = execute_function_call(function_name, arguments)
                    tool_outputs.append({
                        "tool_call_id": tool_call.id,
                        "output": json.dumps(result)
                    })

                run = client.beta.threads.runs.submit_tool_outputs(
                    thread_id=thread_id,
                    run_id=run.id,
                    tool_outputs=tool_outputs
                )
            elif run.status in ["failed", "cancelled", "expired"]:
                print(f"\nRun failed with status: {run.status}")
                return None

            time.sleep(0.5)

        messages = client.beta.threads.messages.list(
            thread_id=thread_id,
            order="desc",
            limit=1
        )

        if messages.data:
            response = messages.data[0].content[0].text.value
            # Store coach's response as opinion
            _store_coach_response(response, user_message)
            return response
        return None

    # Streaming mode
    print("   Coach is thinking...")

    response_text = ""
    run_id = None

    try:
        # Start streaming
        with client.beta.threads.runs.stream(
            thread_id=thread_id,
            assistant_id=assistant.id
        ) as stream:
            for event in stream:
                # Capture run ID
                if event.event == "thread.run.created":
                    run_id = event.data.id

                # Handle function calls - stream ends, we need to submit outputs
                elif event.event == "thread.run.requires_action":
                    print("   Retrieving memories...")

                    tool_outputs = []
                    for tool_call in event.data.required_action.submit_tool_outputs.tool_calls:
                        function_name = tool_call.function.name
                        arguments = json.loads(tool_call.function.arguments)
                        result = execute_function_call(function_name, arguments)
                        tool_outputs.append({
                            "tool_call_id": tool_call.id,
                            "output": json.dumps(result)
                        })

                    # Submit tool outputs with streaming
                    with client.beta.threads.runs.submit_tool_outputs_stream(
                        thread_id=thread_id,
                        run_id=run_id,
                        tool_outputs=tool_outputs
                    ) as tool_stream:
                        for tool_event in tool_stream:
                            if tool_event.event == "thread.message.delta":
                                for content in tool_event.data.delta.content:
                                    if content.type == "text":
                                        text_delta = content.text.value
                                        print(text_delta, end="", flush=True)
                                        response_text += text_delta

                # Stream text deltas (for non-function-call responses)
                elif event.event == "thread.message.delta":
                    for content in event.data.delta.content:
                        if content.type == "text":
                            text_delta = content.text.value
                            print(text_delta, end="", flush=True)
                            response_text += text_delta

                elif event.event == "thread.run.failed":
                    print(f"\nRun failed")
                    return None

        print()  # New line after streaming

        # Wait for run to fully complete before returning
        if run_id:
            for _ in range(10):
                try:
                    run = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_id)
                    if run.status == "completed":
                        break
                    time.sleep(0.3)
                except:
                    break

        # Store coach's response as opinion
        _store_coach_response(response_text, user_message)

        return response_text

    except Exception as e:
        # Handle streaming errors (network issues, premature connection close, etc.)
        # Silently handle - these are common with OpenAI streaming and we handle gracefully

        # CRITICAL: Ensure the run completes before we can continue
        if run_id:
            max_attempts = 60
            for attempt in range(max_attempts):
                try:
                    run = client.beta.threads.runs.retrieve(
                        thread_id=thread_id,
                        run_id=run_id
                    )

                    if run.status in ["completed", "failed", "cancelled", "expired"]:
                        break

                    # If still running or requires_action after too many attempts, cancel it
                    if attempt > 30 and run.status in ["in_progress", "requires_action"]:
                        print("   Run taking too long, attempting to cancel...")
                        client.beta.threads.runs.cancel(thread_id=thread_id, run_id=run_id)
                        time.sleep(2)
                        break

                except Exception as inner_e:
                    # Only print if it's not a normal completion
                    if "not found" not in str(inner_e).lower():
                        print(f"   Error checking run status: {inner_e}")
                    break

                time.sleep(1)

        # If we got partial response, return it (no need to announce)
        if response_text:
            print()  # Add newline if streaming was interrupted

            # Ensure run is completed before returning
            if run_id:
                for _ in range(10):
                    try:
                        run = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_id)
                        if run.status == "completed":
                            break
                        time.sleep(0.3)
                    except:
                        break

            # Store coach's response as opinion
            _store_coach_response(response_text, user_message)
            return response_text

        # Otherwise, try to get the full response
        try:
            messages = client.beta.threads.messages.list(
                thread_id=thread_id,
                order="desc",
                limit=1
            )

            if messages.data:
                response = messages.data[0].content[0].text.value
                # Print the response since streaming failed
                print(response)
                print()

                # Ensure run is completed before returning
                if run_id:
                    for _ in range(10):
                        try:
                            run = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_id)
                            if run.status == "completed":
                                break
                            time.sleep(0.3)
                        except:
                            break

                # Store coach's response as opinion
                _store_coach_response(response, user_message)
                return response
        except Exception as msg_e:
            print(f"   Could not retrieve message: {msg_e}")

        return None


def interactive_chat():
    """Interactive chat session with the fitness coach."""

    print("\n" + "=" * 70)
    print("OPENAI FITNESS COACH (with Hindsight Memory)")
    print("=" * 70)
    print("\nThis coach uses:")
    print("  - OpenAI Assistant for conversation")
    print("  - Hindsight for long-term memory storage")
    print("  - Function calling to retrieve relevant context")
    print("\n" + "=" * 70)

    # Get or create assistant
    assistant = get_or_create_assistant()

    # Create a new conversation thread
    thread = create_thread()
    print(f"\nStarted new conversation (Thread: {thread.id[:8]}...)")

    print("\nAsk me anything about your fitness journey!")
    print("Type 'quit' or 'exit' to end the conversation.")
    print("=" * 70 + "\n")

    while True:
        try:
            user_input = input("You: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ['quit', 'exit', 'bye']:
                print("\nKeep up the great work! See you next time!")
                break

            # Get response from assistant (streaming)
            print(f"\nCoach:")
            response = chat(assistant, thread.id, user_input, stream=True)

            if response:
                print("\n" + "=" * 70 + "\n")

        except KeyboardInterrupt:
            print("\n\nKeep up the great work! See you next time!")
            break
        except Exception as e:
            print(f"\nError: {e}")


def ask_single_question(question: str):
    """Ask a single question and exit."""

    # Get or create assistant
    assistant = get_or_create_assistant()

    # Create thread
    thread = create_thread()

    print(f"\nYou: {question}\n")

    # Get response
    response = chat(assistant, thread.id, question)

    if response:
        print(f"Coach:\n{response}\n")


def main():
    """Main entry point."""

    # Check for OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set")
        print("\nPlease set your OpenAI API key:")
        print("  export OPENAI_API_KEY=your_api_key_here")
        sys.exit(1)

    if len(sys.argv) > 1:
        # Single question mode
        question = " ".join(sys.argv[1:])
        ask_single_question(question)
    else:
        # Interactive mode
        interactive_chat()


if __name__ == "__main__":
    main()
