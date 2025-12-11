#!/bin/bash
# Reset the conversational demo completely

echo "Resetting Conversational Demo"
echo "=================================="
echo ""

# Step 1: Delete old assistant
if [ -f .openai_assistant_id ]; then
    echo "Deleting old OpenAI assistant ID"
    rm .openai_assistant_id
else
    echo "No assistant ID file found"
fi

# Step 2: Clear demo agent memories
echo "Clearing demo agent memories..."
curl -s -X DELETE http://localhost:8888/api/v1/agents/fitness-coach-demo/memories > /dev/null

echo ""
echo "Demo reset complete!"
echo ""
echo "Now run: python demo_conversational.py"
echo ""
