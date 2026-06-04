from backend.app.agents.agent_b import EnglishLevelHintAgent
from backend.app.schemas.game_turn import DevBPolicyInput, DevBPolicyOutput


class DevBPolicyClient:
    def __init__(self, agent: EnglishLevelHintAgent | None = None) -> None:
        self.agent = agent or EnglishLevelHintAgent()

    def evaluate_turn(self, payload: DevBPolicyInput) -> DevBPolicyOutput:
        return self.agent.evaluate_turn(payload)
