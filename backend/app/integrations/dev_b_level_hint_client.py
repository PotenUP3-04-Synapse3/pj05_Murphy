from pathlib import Path

from backend.app.agents.agent_b import EnglishLevelHintAgent
from backend.app.schemas.game_turn import DevBPolicyInput, DevBPolicyOutput


class DevBPolicyClient:
    def __init__(
        self,
        agent: EnglishLevelHintAgent | None = None,
        *,
        agent_run_root: Path | None = None,
    ) -> None:
        self.agent = agent or EnglishLevelHintAgent(agent_run_root=agent_run_root)

    def evaluate_turn(self, payload: DevBPolicyInput) -> DevBPolicyOutput:
        return self.agent.evaluate_turn(payload)
