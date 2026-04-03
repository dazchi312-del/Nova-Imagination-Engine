import sys
import os
import uuid

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.router import MemoryAwareRouter
from core.memory import Memory
from core.agents import Agent

agents = {"agent1": {"capabilities": ["text"]}, "agent2": {"capabilities": ["image"]}}

router = MemoryAwareRouter(agents)
memory = Memory()

task = {"id": str(uuid.uuid4()), "capability": "image"}

# Load last session (memory injection)
last_session = memory.get_last_session()

if last_session:
    print("\n--- CONTEXT LOADED ---")
    print(
        {
            "session_id": last_session.get("session_id"),
            "capability": last_session.get("capability"),
            "id": last_session.get("id"),
        }
    )

# Attach context to task (clean all nesting)
while isinstance(last_session, dict) and "context" in last_session:
    last_session = last_session["context"]

task["context"] = last_session

task["context"] = last_session

task["context"] = last_session

agent_id = router.route(task)
memory.save(task["id"], task)

restored = memory.load(task["id"])

print(f"Assigned to {agent_id}")
print("Restored task:", restored)

print("\n--- HISTORY ---")
sessions = memory.list_sessions()
print(f"Total sessions: {len(sessions)}")

print("\nLast session:")
print(memory.get_last_session())
