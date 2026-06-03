# Real Kokoro 테스트 방법 - kimyonghee

## Dependency 추가 명령어

```powershell
$env:UV_CACHE_DIR='C:\5th_project\pj05_Murphy\.tmp\uv-cache'
uv add kokoro soundfile torch espeakng-loader
```

## 현재 테스트 설정값

```json
{
  "provider": "kokoro",
  "npc_id": "officer_miller",
  "speaker": "Officer Miller",
  "voice_id": "am_michael",
  "lang_code": "a",
  "speed": 0.95,
  "sample_rate": 24000,
  "output_format": "wav",
  "runtime_root": "backend/runtime",
  "audio_url_base": "http://localhost:8000/runtime/audio"
}
```

## 샘플 JSON 기준 생성 결과

생성 대사:

```text
You're here for tourism. How long will you stay?
```

생성 wav:

```text
backend/runtime/audio/kokoro/70684d4be5afdd2a7be69612516bd5e2729b30212ca823cde238f6166ac92451.wav
```

생성 metadata:

```text
backend/runtime/metadata/real_kokoro_smoke_kimyonghee.json
```

Unreal 전달 후보 URL:

```text
http://localhost:8000/runtime/audio/kokoro/70684d4be5afdd2a7be69612516bd5e2729b30212ca823cde238f6166ac92451.wav
```

## 확인된 metadata

```json
{
  "provider": "kokoro",
  "voice_id": "am_michael",
  "sample_rate": 24000,
  "format": "wav",
  "audio_seconds": 3.675,
  "status": "ok",
  "quality_metadata": {
    "sample_rate": 24000,
    "channels": 1,
    "bit_depth": 16,
    "duration_ms": 3675,
    "silent_ratio": 0.45652173913043476
  },
  "postprocess_policy": {
    "target_sample_rate": 24000,
    "target_format": "wav",
    "target_channels": 1,
    "target_peak_dbfs": -3.0,
    "trim_outer_silence": true,
    "preserve_sentence_pause": true,
    "actual_dsp_applied": false
  }
}
```

## 다음 테스트 방법

현재 서비스 함수 기준으로는 `build_voice_output_from_level_design(..., use_real_tts=True, audio_url_base="http://localhost:8000/runtime/audio")`를 호출하면 실제 Kokoro wav와 metadata를 생성할 수 있다.

Developer C가 static route를 열면 Unreal은 `audio_url`을 통해 wav를 요청하면 된다. static route가 열리기 전에는 `audio_path`로 로컬 파일 존재 여부를 확인한다.

## Profile/Emotion/Policy 반영 후 최신 생성 결과

샘플 JSON에는 직접적인 `npc_emotion` 필드는 없지만, 아래 필드로 감정상태를 추론한다.

- `evaluation_summary.task_success`
- `evaluation_summary.clarity`
- `in_game_feedback.priority`
- `in_game_feedback.blocks_progression`
- `branch.branch_type`
- `dialogue_directive.tone_hint`
- `in_game_feedback.feedback_strategy`

최신 생성 결과:

```json
{
  "npc_text": "Alright. You're here for tourism. How long will you stay?",
  "tts_text": "Alright. You're here for tourism. ... How long will you stay?",
  "player_language": {
    "english_level": "beginner",
    "complexity": "simple",
    "feedback_depth": "brief_recast"
  },
  "npc_emotion": {
    "emotion": "calm_official",
    "intensity": 0.35,
    "reason": "successful_low_priority_answer"
  },
  "dialogue_policy": {
    "action": "recast_and_advance",
    "tone": "formal_neutral",
    "next_question_style": "short"
  }
}
```

최신 생성 wav:

```text
backend/runtime/audio/kokoro/c4abebc8604d7dfddb997ba8fa16db2dbcbaaf9a6bb0dd1d474656e5bf9056b0.wav
```

최신 생성 metadata:

```text
backend/runtime/metadata/real_kokoro_policy_smoke_kimyonghee.json
```

최신 Unreal 전달 후보 URL:

```text
http://localhost:8000/runtime/audio/kokoro/c4abebc8604d7dfddb997ba8fa16db2dbcbaaf9a6bb0dd1d474656e5bf9056b0.wav
```
