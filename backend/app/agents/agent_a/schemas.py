from pydantic import BaseModel, Field
from typing import Literal

class NPCDialogueLLMResult(BaseModel):
    """NPC 대사 및 오디오 생성 결과를 나타내는 구조화된 데이터 모델(Data Model)입니다."""
    speaker: str = Field(
        ...,
        min_length=1,
        max_length=80,
        description="NPC 캐릭터의 이름(Speaker Name)입니다."
    )
    npc_text: str = Field(
        ...,
        min_length=1,
        max_length=180,
        description="화면에 표시될 영어 대사(NPC Text)입니다."
    )
    tts_text: str = Field(
        ...,
        min_length=1,
        max_length=220,
        description="ElevenLabs 음성 합성기(TTS)에 전달할 발음 텍스트(TTS Text)입니다."
    )
    feedback_kr: str = Field(
        ...,
        min_length=1,
        max_length=180,
        description="영어 표현에 대한 한국어 피드백(Feedback in Korean)입니다."
    )
    tone: Literal[
        "formal_neutral",
        "formal_firm",
        "formal_stern",
        "formal_warning",
        "formal_supportive"
    ] = Field(
        ...,
        description="대사의 어조(Tone)입니다."
    )
    animation: str = Field(
        ...,
        description="재생할 애니메이션 이름(Animation Name)입니다."
    )
    npc_emotion: Literal[
        "joy",
        "panic",
        "sad",
        "suspicion",
        "disgust",
        "fear",
        "smirk",
        "normal",
        "anger",
        "surprise",
        "pain",
        "confusion",
        "boredom"
    ] = Field(
        ...,
        description="NPC의 감정 상태(NPC Emotion)입니다."
    )
    stability: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="음성의 일관성 및 안정도(Stability) 설정값입니다."
    )
    style: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="음성의 표현 스타일(Style) 설정값입니다."
    )
    speed: float = Field(
        ...,
        ge=0.5,
        le=2.0,
        description="음성의 재생 속도(Speed) 설정값입니다."
    )
    similarity_boost: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="원래 목소리와의 유사도 부스트(Similarity Boost) 설정값입니다."
    )
    llm_reason: str = Field(
        ...,
        max_length=240,
        description="이러한 대사 및 오디오 파라미터를 도출한 LLM의 판단 근거(Reason)입니다."
    )
