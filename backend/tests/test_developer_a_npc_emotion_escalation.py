from backend.app.services.service_a.dialogue_policy_service import build_dialogue_policy
from backend.app.services.service_a.npc_emotion_service import infer_npc_emotion_state
from backend.app.services.service_a.player_language_profile_service import build_player_language_profile
from backend.app.services.service_a.tts_service import build_edge_provider_request
from backend.app.services.service_a.tts_text_polisher_service import polish_tts_text


def test_retry_attempts_escalate_npc_emotion_and_policy_tone() -> None:
    normalized = {
        "branch_type": "retry",
        "tone_hint": "firm",
        "retry_count": 2,
        "task_success": 0,
        "clarity": 1,
        "english_level": "beginner",
        "needs_hint": True,
    }

    emotion = infer_npc_emotion_state(normalized)
    profile = build_player_language_profile(normalized)
    policy = build_dialogue_policy(normalized, profile, emotion)

    assert emotion.emotion == "stern_official"
    assert emotion.intensity == 0.82
    assert policy.tone == "formal_stern"
    assert policy.next_question_style == "direct_repeat_stern"


def test_repeated_blocking_escalates_to_warning_tone() -> None:
    normalized = {
        "branch_type": "fail",
        "tone_hint": "warning",
        "retry_count": 3,
        "task_success": 0,
        "clarity": 0,
        "english_level": "beginner",
        "needs_hint": True,
    }

    emotion = infer_npc_emotion_state(normalized)
    profile = build_player_language_profile(normalized)
    policy = build_dialogue_policy(normalized, profile, emotion)

    assert emotion.emotion == "warning_official"
    assert emotion.intensity == 0.92
    assert policy.tone == "formal_warning"
    assert policy.max_sentence_count == 1


def test_edge_request_slows_down_as_officer_gets_stricter() -> None:
    firm = build_edge_provider_request(
        text="I need a clear answer.",
        speaker_id="officer_miller",
        voice_profile_id="session_1:officer_miller",
        edge_voice="en-US-GuyNeural",
        tone="formal_firm",
        english_level="beginner",
    )
    warning = build_edge_provider_request(
        text="Answer directly.",
        speaker_id="officer_miller",
        voice_profile_id="session_1:officer_miller",
        edge_voice="en-US-GuyNeural",
        tone="formal_warning",
        english_level="beginner",
    )

    assert firm.speaking_rate == 0.9
    assert warning.speaking_rate == 0.84
    assert warning.intensity == 0.92


def test_tts_polisher_removes_pause_for_warning_official() -> None:
    normalized = {
        "branch_type": "fail",
        "tone_hint": "warning",
        "retry_count": 3,
        "task_success": 0,
        "clarity": 0,
        "english_level": "beginner",
        "needs_hint": True,
    }
    emotion = infer_npc_emotion_state(normalized)
    profile = build_player_language_profile(normalized)
    policy = build_dialogue_policy(normalized, profile, emotion)

    text = polish_tts_text("Sir... answer the question directly.", profile, emotion, policy)

    assert text == "Sir. answer the question directly."
