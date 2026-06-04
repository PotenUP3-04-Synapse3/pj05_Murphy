# OpenAI 대사 생성 테스트 방법 - kimyonghee

## .env 설정

프로젝트 루트의 `.env` 파일에 아래 값을 둔다.

```text
OPENAI_API_KEY=your_openai_api_key
NPC_DIALOGUE_LLM_MODEL=gpt-4o-mini
NPC_DIALOGUE_LLM_TIMEOUT_SECONDS=10
```

`OPENAI_API_KEY`는 코드나 로그에 출력하지 않는다.

## 코드 호출 방식

OpenAI로 대사를 생성하고 Kokoro real TTS까지 생성하려면 아래 옵션을 사용한다.

```python
from pathlib import Path

from backend.app.services.voice_output_service import build_voice_output_from_level_design


result = build_voice_output_from_level_design(
    payload,
    runtime_root=Path("backend/runtime"),
    request_id="req_sample",
    session_id="session_sample",
    user_id="user_001",
    use_llm_dialogue=True,
    use_real_tts=True,
    audio_url_base="http://localhost:8000/runtime/audio",
)
```

## OpenAI 출력 schema

OpenAI Responses API는 Structured Outputs `json_schema`로 아래 필드를 반환한다.

```json
{
  "speaker": "Officer Miller",
  "npc_text": "Alright. You're here for tourism. How long will you stay?",
  "tts_text": "Alright. You're here for tourism. ... How long will you stay?",
  "feedback_kr": "방문 목적은 전달됐습니다. 더 자연스럽게는: I'm here for tourism.",
  "tone": "formal_neutral",
  "animation": "officer_check_passport",
  "llm_reason": "Beginner-level official recast and next question."
}
```

## fallback 정책

- `OPENAI_API_KEY`가 없으면 rule-based 대사로 fallback한다.
- OpenAI API timeout, HTTP error, JSON parse error가 발생해도 rule-based 대사로 fallback한다.
- fallback 시 결과의 `llm.fallback_used`가 `true`가 된다.

## 실제 smoke 결과

샘플 JSON 기준 실제 OpenAI + Kokoro 생성이 성공했다.

```text
npc_text: Alright. You're here for tourism. How long will you stay?
tts_text: Alright. You're here for tourism. ... How long will you stay?
```

생성 wav:

```text
backend/runtime/audio/kokoro/c4abebc8604d7dfddb997ba8fa16db2dbcbaaf9a6bb0dd1d474656e5bf9056b0.wav
```

생성 metadata:

```text
backend/runtime/metadata/openai_real_kokoro_generation_kimyonghee.json
```

Unreal 전달 후보 URL:

```text
http://localhost:8000/runtime/audio/kokoro/c4abebc8604d7dfddb997ba8fa16db2dbcbaaf9a6bb0dd1d474656e5bf9056b0.wav
```
