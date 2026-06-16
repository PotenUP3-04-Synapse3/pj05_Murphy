import pytest
from backend.app.services.service_a.tts_text_polisher_service import validate_and_clamp_ssml, polish_tts_text
from backend.app.services.service_a.player_language_profile_service import PlayerLanguageProfile
from backend.app.services.service_a.npc_emotion_service import NPCEmotionState
from backend.app.services.service_a.dialogue_policy_service import DialoguePolicy


def test_validate_and_clamp_ssml():
    # 1. 3초 초과 클램프
    text1 = "Wait. <break time='4.5s'/> Next."
    assert validate_and_clamp_ssml(text1) == 'Wait. <break time="3.0s"/> Next.'
    
    # 2. ms 단위를 s로 환산 및 클램프
    text2 = "Okay. <break time='500ms'/> Ready."
    assert validate_and_clamp_ssml(text2) == 'Okay. <break time="0.5s"/> Ready.'
    
    # 3. 단위 없음 -> s로 처리
    text3 = "Yes. <break time='1.2'/> Go."
    assert validate_and_clamp_ssml(text3) == 'Yes. <break time="1.2s"/> Go.'
    
    # 4. 잘못된 시간 -> 0.5s로 폴백
    text4 = "No. <break time='abc'/> Wait."
    assert validate_and_clamp_ssml(text4) == 'No. <break time="0.5s"/> Wait.'


def test_polish_tts_text_non_verbal_injection():
    # PlayerLanguageProfile 생성 시 7개의 파라미터를 올바르게 전달합니다.
    profile = PlayerLanguageProfile("low", 0, 0, False, "", "simple", "shallow")
    emotion = NPCEmotionState("anger", 0.8, "player was rude")
    policy = DialoguePolicy("neutral", "formal_firm", 2, False, False, "neutral")
    palette = ["Hmph.", "Tsk.", "<break time='0.4s'/>"]
    
    # anger 감정일 때 negatives 의성어 중 하나가 문장 앞에 자동 삽입되어야 함
    polished = polish_tts_text("Answer the question.", profile, emotion, policy, non_verbal_palette=palette)
    assert polished.startswith(("Hmph. Answer the question.", "Tsk. Answer the question."))
