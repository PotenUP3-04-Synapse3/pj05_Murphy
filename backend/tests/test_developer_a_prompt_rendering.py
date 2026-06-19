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


def test_prompt_rendering_with_session_memory_and_policy():
    """세션 메모리 및 대화 정책 변수들이 마크다운 프롬프트(Long/Short) 내에 올바르게 직렬화되어 렌더링되는지 검증합니다."""
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
        
        # 세션 메모리 변수
        "confirmed_facts": ["The purpose of visit is tourism.", "The duration is 5 days."],
        "forbidden_repeat_questions": ["What is the purpose of your visit?"],
        "open_hooks": ["tourism", "hotel"],
        "last_npc_intent": "ask_travel_purpose",
        "recent_turns_compact": ["T-1 player='tourism' npc='What is the purpose?' filled={}"],
        "topic_thread": ["tourism", "duration"],
        
        # 정책 변수
        "policy_action": "ask_followup",
        "policy_next_question_style": "natural",
        "policy_max_sentence_count": 2,
    }
    
    # 1. 긴 프롬프트 렌더링 검증
    prompt = _render_developer_instructions(context, use_short=False)
    assert "Confirmed Facts" in prompt
    assert "The purpose of visit is tourism." in prompt
    assert "Forbidden Repeats" in prompt
    assert "What is the purpose of your visit?" in prompt
    assert "Open Hooks" in prompt
    assert "tourism" in prompt
    assert "hotel" in prompt
    assert "Last NPC Intent" in prompt
    assert "ask_travel_purpose" in prompt
    assert "Recent Turns" in prompt
    assert "T-1 player=" in prompt
    assert "Dialogue Policy" in prompt
    assert "Action: ask_followup" in prompt
    assert "Next-question style: natural" in prompt
    assert "Max sentences: 2" in prompt

    # 2. 짧은 프롬프트 렌더링 검증
    short_prompt = _render_developer_instructions(context, use_short=True)
    assert "Confirmed:" in short_prompt
    assert "Forbidden repeats:" in short_prompt
    assert "Hooks" in short_prompt
    assert "Last NPC intent:" in short_prompt

