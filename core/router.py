from typing import Any, Dict


class MemoryAwareRouter:
    def __init__(self, agents: Dict[str, Dict[str, Any]]):
        self.agents = agents

    def route(self, task: Dict[str, Any]) -> str:
        if "capability" not in task:
            raise ValueError("Task is missing required 'capability' key.")

        required_capability = task["capability"]
        context = task.get("context", {})

        if isinstance(context, dict) and context: 
            print("Using memory context for routing")

            preferred_agent = context.get("preferred_agent")
            if preferred_agent:
                if preferred_agent in self.agents:
                    if required_capability in self.agents[preferred_agent].get("capabilities", []):
                        return preferred_agent

            previous_capability = context.get("capability")
            if previous_capability == "text" and required_capability == "text":
                return "agent1"

            if previous_capability == "image" and required_capability == "image":
                return "agent2"

        for agent_id, info in self.agents.items():
            if required_capability in info.get("capabilities", []):
                return agent_id

        raise ValueError(f"No agent found for capability: {required_capability}")