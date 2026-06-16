import pytest
from pathlib import Path
from backend.app.agents.agent_a.npc_llm_client import _render_developer_instructions


def test_prompt_rendering_success():
    context = {
        "persona_instruction": "a polite desk clerk.",
        "npc_role": "baggage_agent",
        "english_level": "intermediate",
        "incivility_tier": 0,
        "profanity_mode": "off",
        "surface_goal": "ask_baggage_weight",
        "allowed_emotions": ["joy", "normal"],
        "non_verbal_palette": ["Oh!", "Mm-hmm."],
        "allowed_mild": ["heck"],
        "allowed_strong": ["heck"],
    }
    
    # 1. Primary prompt rendering
    prompt = _render_developer_instructions(context, use_short=False)
    assert "baggage_agent" in prompt
    assert "polite desk clerk" in prompt
    assert "FEW-SHOT EXAMPLES" in prompt
    assert "player_text" in prompt

    # 2. Fallback short prompt rendering
    short_prompt = _render_developer_instructions(context, use_short=True)
    assert "baggage_agent" in short_prompt
    assert "polite desk clerk" in short_prompt
    assert "FEW-SHOT EXAMPLES" in short_prompt
