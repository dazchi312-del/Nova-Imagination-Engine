from typing import Dict


class Agent:
    def __init__(self, agent_id: str, capabilities: list):
        self.id = agent_id
        self.capabilities = capabilities

    def execute(self, task: Dict) -> Dict:
        return {"status": "done", "task": task}
