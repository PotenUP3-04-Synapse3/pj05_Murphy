# Developer A 구현 로그 - kimyonghee

## 2026-06-03 21:25:58 +09:00

- 작업 시작.
- `AGENTS.md`와 `docs/prompts/developer_a_start_prompt.md`를 다시 읽고 소유권을 확인했다.
- 구현 범위는 Developer A 소유 영역인 `backend/app/agents`, `backend/app/services`, `backend/app/prompts` 중심으로 제한한다.
- `backend/tests`, `backend/app/middleware`, `backend/app/tools`, 실제 Kokoro dependency 추가는 계약 합의가 필요하므로 직접 구현 범위에서 제외한다.
- 현재 `backend/tests/test_developer_a_npc_dialogue.py`가 이미 untracked 상태로 존재하지만, 이번 작업에서는 테스트 파일을 새로 수정하지 않는다.

## 2026-06-03 21:26:00 +09:00

- `docs/contracts/change_requests.md`에 Developer A 테스트 위치, Kokoro dependency, Developer C adapter output field, runtime audio serving 정책에 대한 Change Request를 추가했다.
- 구현은 fake Kokoro provider 기반으로 진행하고, 실제 Kokoro dependency 추가는 승인 전까지 보류한다.

## 2026-06-03 21:27:00 +09:00

- Developer A service 파일을 추가했다.
- 추가 파일:
  - `backend/app/services/developer_a_input_service.py`
  - `backend/app/services/developer_a_fallback_service.py`
  - `backend/app/services/tts_provider_service.py`
  - `backend/app/services/voice_profile_service.py`
  - `backend/app/services/audio_storage_service.py`
  - `backend/app/services/audio_quality_service.py`
  - `backend/app/services/developer_a_runtime_log_service.py`
- 실제 TTS dependency 없이 검증 가능한 `FakeKokoroProvider`를 구현했다.
- fake provider는 단순 바이트가 아니라 `wave` 모듈로 분석 가능한 최소 유효 wav 파일을 생성한다.

## 2026-06-03 21:28:00 +09:00

- `backend/app/agents/npc_dialogue_agent.py`에 `generate_npc_dialogue_from_level_design`를 추가했다.
- 기존 `generate_npc_dialogue`와 `NPCDialogueResult`는 기존 adapter/test 호환성을 위해 유지했다.
- `backend/app/services/tts_service.py`에 `build_kokoro_provider_request`를 추가했다.
- `backend/app/services/voice_output_service.py`에 `build_voice_output_from_level_design`를 추가했다.
- 새 voice output 경로는 fake Kokoro wav 생성, cache key 생성, wav 품질 metadata, postprocess policy, runtime event logging을 결합한다.

## 2026-06-03 21:29:00 +09:00

- Developer A 변경 파일 대상 `uv run ruff check ...` 실행 결과 PASS.
- `uv run python -c ...`와 `uv run pytest -q`는 사용자 AppData Python 런타임 실행 문제로 실패했다.
- 실패 메시지: `Unable to create process using ... AppData ... python.exe`
- 동일 검증을 sandbox escalation으로 재시도한다.

## 2026-06-03 21:30:00 +09:00

- sandbox escalation으로 import smoke 검증 PASS.
- sandbox escalation으로 `uv run pytest -q` 실행 결과 `5 passed, 1 warning`.
- warning: Python 3.13에서 제거 예정인 `audioop` deprecation warning이 발생했다. 현재 프로젝트 Python은 3.12이므로 1차 구현에서는 유지한다.
- Level Design voice output smoke 검증을 `python -c` 한 줄 명령으로 시도했으나 PowerShell/Python 문자열 인용 문제로 실패했다.
- 실패 메시지: `SyntaxError: unterminated string literal`.
- 검증 명령 작성 실패이므로 임시 smoke script 방식으로 재시도한다.

## 2026-06-03 21:31:00 +09:00

- `.tmp/developer_a_smoke.py` 임시 검증 스크립트를 작성했다.
- 첫 실행은 `.tmp`에서 실행된 Python의 import path에 repo root가 없어 실패했다.
- 실패 메시지: `ModuleNotFoundError: No module named 'backend'`.
- 임시 스크립트에 repo root를 `sys.path`로 추가해 재시도한다.

## 2026-06-03 21:32:00 +09:00

- 수정한 임시 smoke script 실행 결과 PASS.
- 확인 결과:
  - NPC text: `You're here for tourism. How long will you stay?`
  - TTS provider: `kokoro`
  - TTS status: `ok`
  - sample rate: `24000`
  - sentence pause 보존 정책: `True`
- 임시 smoke script와 `.tmp/developer_a_runtime` 산출물을 정리했다.

## 2026-06-03 21:33:00 +09:00

- 최종 검증 실행:
  - `uv run ruff check .`: PASS
  - `uv run pytest -q`: `5 passed, 1 warning`
  - `uv run mypy .`: PASS
- `audioop` deprecation warning은 Python 3.12 기준 동작에는 문제가 없지만, Python 3.13 전환 시 대체 구현 검토가 필요하다.
- 코드 주석 검색 결과 자연어 주석은 한국어로 작성되어 있음을 확인했다.
- `# type: ignore` 타입 검사 지시문을 제거하고 `typing.cast`로 대체했다.

## 2026-06-03 21:34:00 +09:00

- 마지막 변경 이후 전체 검증을 다시 실행했다.
- 최종 결과:
  - `uv run ruff check .`: PASS
  - `uv run pytest -q`: `5 passed, 1 warning`
  - `uv run mypy .`: PASS
- 남은 warning은 `audioop` deprecation warning 1건이다.
- 실제 Kokoro dependency 추가, Developer A 테스트 위치, Developer C adapter field, runtime audio URL 정책은 Change Request 응답 대기 상태다.

## 2026-06-03 21:35:00 +09:00

- 사용자가 Kokoro dependency 추가를 승인했다.
- field name은 미정이지만 현재 제안 필드(`speaker`, `npc_text`, `feedback_kr`, `tone`, `animation`, `tts`, `fallback`)로 진행한다.
- Unreal은 파일을 `audio_url`로 받을 가능성이 높다고 확인했다.
- dependency 추가 명령어는 `uv add kokoro soundfile torch espeakng-loader`로 정했다.
- Windows/CUDA 세부 설정은 아직 확정되지 않았으므로 우선 CPU/기본 설치 기준으로 진행한다.

## 2026-06-03 21:36:00 +09:00

- `uv add kokoro soundfile torch espeakng-loader` 실행 완료.
- 설치된 핵심 dependency:
  - `kokoro==0.9.4`
  - `soundfile==0.13.1`
  - `torch==2.12.0`
  - `espeakng-loader==0.2.4`
- `pyproject.toml`과 `uv.lock`이 갱신되었다.
- `kokoro`, `soundfile`, `torch`, `espeakng_loader`, `KPipeline` import 검증 PASS.

## 2026-06-03 21:37:00 +09:00

- `backend/app/services/tts_provider_service.py`에 `RealKokoroProvider`와 `configure_espeak_runtime`를 추가했다.
- 첫 mypy 검증은 외부 패키지 stub 부재로 실패했다.
- 실패 항목: `soundfile`, `kokoro`, `espeakng_loader`, `phonemizer.backend.espeak.wrapper` missing stubs.
- `importlib.import_module` 기반 지연 import로 수정해 mypy missing stub 문제를 제거했다.
- 수정 후 `uv run ruff check backend/app/services/tts_provider_service.py`: PASS.
- 수정 후 `uv run mypy backend/app/services/tts_provider_service.py`: PASS.

## 2026-06-03 21:38:00 +09:00

- `backend/app/services/voice_output_service.py`에 `use_real_tts`와 `audio_url_base` 인자를 추가했다.
- 기본값은 fake TTS 유지이므로 기존 호출과 테스트 호환성을 보존한다.
- 실제 Kokoro 테스트 시 `audio_url_base="http://localhost:8000/runtime/audio"`를 전달하면 Unreal 전달 후보 URL을 생성한다.
- `uv run ruff check backend/app/services/voice_output_service.py`: PASS.
- `uv run mypy backend/app/services/voice_output_service.py`: PASS.

## 2026-06-03 21:39:00 +09:00

- 아까 전달받은 샘플 JSON과 동일한 payload로 실제 Kokoro wav 생성 smoke를 실행했다.
- 실행 결과 PASS.
- 생성 대사: `You're here for tourism. How long will you stay?`
- 생성 wav: `backend/runtime/audio/kokoro/70684d4be5afdd2a7be69612516bd5e2729b30212ca823cde238f6166ac92451.wav`
- 생성 metadata: `backend/runtime/metadata/real_kokoro_smoke_kimyonghee.json`
- 생성 audio_url 후보: `http://localhost:8000/runtime/audio/kokoro/70684d4be5afdd2a7be69612516bd5e2729b30212ca823cde238f6166ac92451.wav`
- 품질 metadata: `sample_rate=24000`, `duration_ms=3675`, `silent_ratio=0.4565`.
- 실제 실행 중 spaCy `en_core_web_sm==3.8.0` 모델이 추가 설치되었다.
- `torch`의 LSTM dropout warning과 `weight_norm` FutureWarning이 출력됐지만 생성은 성공했다.
- 임시 smoke script는 제거했고, 생성된 wav/metadata는 테스트 산출물로 유지했다.
- 재현 방법 문서 `docs/implementation_logs/real_kokoro_test_method_kimyonghee.md`를 추가했다.
- `docs/contracts/dependency_contract.md`에 승인된 Kokoro dependency와 제약 사항을 반영했다.

## 2026-06-03 21:40:00 +09:00

- Kokoro dependency와 real provider 추가 이후 전체 검증을 실행했다.
- 최종 결과:
  - `uv run ruff check .`: PASS
  - `uv run pytest -q`: `5 passed, 1 warning`
  - `uv run mypy .`: PASS
- 남은 warning은 기존과 동일한 `audioop` deprecation warning 1건이다.
- `backend/runtime/`은 실제 Kokoro 테스트 산출물 보존을 위해 삭제하지 않았다.

## 2026-06-03 21:57:09 +09:00

- 사용자가 원하는 목표가 단순 TTS가 아니라 Level Design Agent JSON 기반의 `유저 언어 실력 + NPC 감정상태` 반영 대사 생성임을 확인했다.
- 샘플 JSON에는 직접적인 `npc_emotion` 필드는 없지만, 감정상태 추론에 필요한 `branch_type`, `blocks_progression`, `priority`, `task_success`, `clarity`, `tone_hint`, `feedback_strategy`가 포함되어 있다고 판단했다.
- 다음 구현 범위:
  - player language profile 산출
  - NPC emotion state 산출
  - dialogue policy 산출
  - Kokoro용 TTS text polish
  - Agent 결과 metadata에 profile/emotion/policy/tts_text 포함

## 2026-06-03 21:58:00 +09:00

- 정규화 service에 `needs_hint`, `task_success`, `clarity`, `priority`를 추가했다.
- 신규 service 추가:
  - `backend/app/services/player_language_profile_service.py`
  - `backend/app/services/npc_emotion_service.py`
  - `backend/app/services/dialogue_policy_service.py`
  - `backend/app/services/tts_text_polisher_service.py`
- `NPCDialogueAgent`가 player language profile, NPC emotion state, dialogue policy를 산출하도록 확장했다.
- Agent 결과에 `generation_profile`, `tts_text`를 추가했다.
- `voice_output_service`는 Kokoro 생성 시 `npc_text` 대신 `tts_text`를 우선 사용하도록 변경했다.
- `tts_service.build_kokoro_provider_request`는 emotion/intensity를 받을 수 있게 확장했다.

## 2026-06-03 21:59:00 +09:00

- 변경 파일 대상 `uv run ruff check ...`: PASS.
- 변경 파일 대상 `uv run mypy ...`: PASS.
- 샘플 JSON smoke를 `python -c` 한 줄 명령으로 시도했으나 PowerShell/Python 문자열 인용 문제로 실패했다.
- 실패 메시지: `SyntaxError: unterminated string literal`.
- 임시 smoke script 방식으로 재시도한다.

## 2026-06-03 22:00:00 +09:00

- 임시 smoke script로 샘플 JSON 기반 대사 생성 정책을 검증했다.
- 1차 결과에서 `tts_text`가 `Alright. ... You're here...`로 생성되어 pause 위치가 부자연스러운 문제를 발견했다.
- `tts_text_polisher_service._add_sentence_pause`를 수정해 `Alright.` 인사말 뒤가 아니라 recast 문장 뒤에 pause가 들어가도록 변경했다.
- 수정 후 smoke 결과:
  - `npc_text`: `Alright. You're here for tourism. How long will you stay?`
  - `tts_text`: `Alright. You're here for tourism. ... How long will you stay?`
  - player language: `english_level=beginner`, `complexity=simple`, `feedback_depth=brief_recast`
  - NPC emotion: `calm_official`, `intensity=0.35`, `reason=successful_low_priority_answer`
  - dialogue policy: `recast_and_advance`, `formal_neutral`, `next_question_style=short`
- 임시 smoke script는 제거했다.

## 2026-06-03 22:01:00 +09:00

- 대사 생성 정책 확장 후 전체 검증을 실행했다.
- 결과:
  - `uv run ruff check .`: PASS
  - `uv run pytest -q`: `5 passed, 1 warning`
  - `uv run mypy .`: PASS
- 남은 warning은 기존과 동일한 `audioop` deprecation warning 1건이다.

## 2026-06-03 22:02:00 +09:00

- 확장된 `generation_profile`, `npc_emotion`, `dialogue_policy`, `tts_text`를 실제 Kokoro 생성까지 연결해 smoke 검증했다.
- 실행 결과 PASS.
- 생성 wav: `backend/runtime/audio/kokoro/c4abebc8604d7dfddb997ba8fa16db2dbcbaaf9a6bb0dd1d474656e5bf9056b0.wav`
- 생성 metadata: `backend/runtime/metadata/real_kokoro_policy_smoke_kimyonghee.json`
- 생성 audio_url 후보: `http://localhost:8000/runtime/audio/kokoro/c4abebc8604d7dfddb997ba8fa16db2dbcbaaf9a6bb0dd1d474656e5bf9056b0.wav`
- `torch` warning 2건과 Kokoro repo_id default warning이 출력됐지만 wav 생성은 성공했다.

## 2026-06-03 22:06:54 +09:00

- 사용자가 GPT-4o mini급 대사 생성 품질을 요구했다.
- OpenAI API key는 제공되지 않았으므로 실제 OpenAI API 호출은 하지 않는다.
- 현재 ChatGPT/Codex 세션에서 Level Design JSON을 기준으로 대사를 직접 생성하고, 생성문을 Kokoro real TTS로 음성화한다.
- 생성 기준:
  - 유저 영어 실력: beginner
  - 평가: task_success=3, clarity=2
  - feedback strategy: recast
  - branch: success, ADVANCE
  - NPC tone: calm official / formal neutral
  - Officer Miller 스타일: 짧고 공식적이며 다음 질문으로 자연스럽게 진행

## 2026-06-03 22:07:00 +09:00

- 현재 세션에서 GPT-4o mini 스타일 목표 품질로 대사를 생성했다.
- 실제 OpenAI API 호출은 하지 않았다.
- 생성 대사:
  - `npc_text`: `Alright. You're here for tourism. How long will you stay in the United States?`
  - `tts_text`: `Alright. You're here for tourism. ... How long will you stay in the United States?`
- Kokoro real TTS 생성 결과 PASS.
- 생성 wav: `backend/runtime/audio/kokoro/8c0189de824cc6fd480351bfcb6575358168c913a2e312586f373cd9531e5271.wav`
- 생성 metadata: `backend/runtime/metadata/gpt4o_mini_style_kokoro_generation_kimyonghee.json`
- 생성 audio_url 후보: `http://localhost:8000/runtime/audio/kokoro/8c0189de824cc6fd480351bfcb6575358168c913a2e312586f373cd9531e5271.wav`
- audio metadata:
  - `sample_rate=24000`
  - `duration_ms=5400`
  - `silent_ratio=0.3852`
  - `status=ok`
- 임시 생성 스크립트는 제거했고, wav/metadata 산출물은 보존했다.

## 2026-06-03 22:08:00 +09:00

- 사용자가 `.env`에 OpenAI API key를 추가할 예정이라고 확인했다.
- 실제 코드에서 OpenAI API를 호출해 대사를 생성할 수 있도록 `backend/app/agents/npc_llm_client.py`를 추가했다.
- SDK dependency는 추가하지 않고 기존 `httpx`로 OpenAI Responses API `POST /v1/responses`를 호출한다.
- `.env` 또는 환경변수에서 읽는 값:
  - `OPENAI_API_KEY`
  - `NPC_DIALOGUE_LLM_MODEL` 기본값: `gpt-4o-mini`
  - `NPC_DIALOGUE_LLM_TIMEOUT_SECONDS` 기본값: `10`
- Structured Outputs용 `json_schema`를 사용해 `speaker`, `npc_text`, `tts_text`, `feedback_kr`, `tone`, `animation`, `llm_reason`을 받도록 구현했다.
- `generate_npc_dialogue_from_level_design(..., use_llm=True)`일 때 OpenAI client를 호출하도록 연결했다.
- `build_voice_output_from_level_design(..., use_llm_dialogue=True)` 옵션을 추가했다.
- OpenAI 호출 실패 또는 key 미설정 시 기존 rule-based 결과로 fallback한다.
- 변경 파일 검증:
  - `uv run ruff check backend/app/agents/npc_llm_client.py backend/app/agents/npc_dialogue_agent.py backend/app/services/voice_output_service.py`: PASS
  - `uv run mypy backend/app/agents/npc_llm_client.py backend/app/agents/npc_dialogue_agent.py backend/app/services/voice_output_service.py`: PASS

## 2026-06-03 22:09:00 +09:00

- smoke 실행 중 `OPENAI_API_KEY`가 환경 또는 `.env`에서 감지되어 실제 OpenAI 호출이 성공했다. 키 값은 출력하거나 기록하지 않았다.
- fake LLM client 주입 경로와 실제 OpenAI client 경로를 모두 검증했다.
- 실제 OpenAI + Kokoro real TTS 생성 결과 PASS.
- 생성 대사:
  - `npc_text`: `Alright. You're here for tourism. How long will you stay?`
  - `tts_text`: `Alright. You're here for tourism. ... How long will you stay?`
- LLM metadata: `used=true`, `fallback_used=false`.
- 생성 wav: `backend/runtime/audio/kokoro/c4abebc8604d7dfddb997ba8fa16db2dbcbaaf9a6bb0dd1d474656e5bf9056b0.wav`
- 생성 metadata: `backend/runtime/metadata/openai_real_kokoro_generation_kimyonghee.json`
- 생성 audio_url 후보: `http://localhost:8000/runtime/audio/kokoro/c4abebc8604d7dfddb997ba8fa16db2dbcbaaf9a6bb0dd1d474656e5bf9056b0.wav`
- 임시 smoke script는 제거했고, wav/metadata 산출물은 보존했다.

## 2026-06-03 22:18:03 +09:00

- 사용자가 `.env`에 OpenAI API key를 추가했다고 확인했다.
- 키 값은 읽거나 출력하지 않고, 코드의 `.env` loader가 자동으로 사용하게 둔다.
- 샘플 Level Design JSON 기준으로 실제 OpenAI 대사 생성과 Kokoro wav 생성을 다시 실행한다.

## 2026-06-03 22:18:30 +09:00

- 실제 OpenAI API 대사 생성과 Kokoro wav 생성 실행 결과 PASS.
- 키 값은 출력하지 않았다.
- 생성 대사:
  - `npc_text`: `You're here for tourism. How long will you stay?`
  - `tts_text`: `You're here for tourism. ... How long will you stay?`
- LLM metadata: `used=true`, `fallback_used=false`.
- 생성 wav: `backend/runtime/audio/kokoro/d8137a4e4e7592c88bf2f78e5763e50b7eb073b5e8ed48036636de9694a83521.wav`
- 생성 metadata: `backend/runtime/metadata/openai_key_added_generation_kimyonghee.json`
- 생성 audio_url 후보: `http://localhost:8000/runtime/audio/kokoro/d8137a4e4e7592c88bf2f78e5763e50b7eb073b5e8ed48036636de9694a83521.wav`
- audio metadata:
  - `sample_rate=24000`
  - `duration_ms=3800`
  - `silent_ratio=0.4474`
  - `status=ok`
- 임시 실행 스크립트는 제거했고, wav/metadata 산출물은 보존했다.

## 2026-06-03 22:26:23 +09:00

- 사용자가 `C:\Users\user\Downloads\녹음.wav`를 제공했다.
- 요청 범위: 실제 Understanding/Level Design Agent가 없으므로 임시 Level Design Agent 역할로 예상 JSON을 생성하고, 그 JSON을 NPC Dialogue Agent에 전달한다.
- 오디오 파일 확인: `770126 bytes`.
- 다음 단계는 OpenAI transcription으로 플레이어 발화를 추정한 뒤 임시 Level Design JSON을 생성하는 것이다.

## 2026-06-03 22:27:00 +09:00

- `녹음.wav`를 OpenAI transcription API로 전송해 전사하고, 이어서 NPC Dialogue Agent와 Kokoro TTS까지 실행하는 임시 스크립트를 만들었다.
- 실행은 승인 단계에서 차단되었고 실제 음성 파일 업로드는 발생하지 않았다.
- 차단 사유: 사용자의 음성 파일을 외부 API로 전송하는 작업이므로 명시적 위험 고지가 필요하다.
- 임시 스크립트는 삭제했다.
- 다음 진행 방식:
  - 사용자가 음성 파일 외부 전송을 명시 승인하면 OpenAI transcription으로 진행한다.
  - 또는 사용자가 직접 발화 텍스트를 제공하면 외부 전송 없이 임시 Level Design JSON을 생성한다.
  - 또는 정확도 낮음을 감수하고 “예상 답변” 기준 JSON을 생성한다.

## 2026-06-03 22:29:09 +09:00

- 사용자가 녹음 발화 텍스트를 직접 제공했다: `I will stay five days`.
- 음성 파일 외부 전송 없이 해당 텍스트를 기준으로 임시 Level Design Agent JSON을 생성한다.
- 생성한 JSON은 NPC Dialogue Agent에 전달하고, `use_llm_dialogue=True`, `use_real_tts=True`로 OpenAI 대사 생성과 Kokoro wav 생성을 실행한다.

## 2026-06-03 22:30:00 +09:00

- 사용자 제공 텍스트 `I will stay five days`를 OpenAI API로 전송해 NPC 대사 생성에 사용하는 것을 사용자가 명시 승인했다.
- 승인 후 임시 Level Design JSON 생성, NPC Dialogue Agent 실행, OpenAI 대사 생성, Kokoro wav 생성을 진행한다.

## 2026-06-03 22:31:00 +09:00

- 사용자 제공 텍스트 기준 임시 Level Design JSON 생성 결과 PASS.
- 생성 JSON: `backend/runtime/level_design/imm_003_duration_user_text_kimyonghee.json`
- 실제 OpenAI 대사 생성과 Kokoro wav 생성 결과 PASS.
- 생성 대사:
  - `npc_text`: `Alright. You'll stay for five days. Where will you be staying?`
  - `tts_text`: `Alright. You'll stay for five days. ... Where will you be staying?`
- LLM metadata: `used=true`, `fallback_used=false`.
- 생성 wav: `backend/runtime/audio/kokoro/02160bafedccd24e454895e852ceafd3aa9de82429259566f87eb5af41c8cf38.wav`
- 생성 metadata: `backend/runtime/metadata/user_text_duration_to_npc_kimyonghee.json`
- 생성 audio_url 후보: `http://localhost:8000/runtime/audio/kokoro/02160bafedccd24e454895e852ceafd3aa9de82429259566f87eb5af41c8cf38.wav`
- audio metadata:
  - `sample_rate=24000`
  - `duration_ms=4625`
  - `silent_ratio=0.4310`
  - `status=ok`
- 임시 실행 스크립트는 제거했고, JSON/wav/metadata 산출물은 보존했다.

## 2026-06-03 22:45:43 +09:00

- 사용자가 wav 파일명을 사람이 구분 가능한 형식으로 변경해달라고 요청했다.
- 적용할 규칙: `{node_id}_{target_slot}_{branch_type}_{voice_id}_{hash8}.wav`
- cache key는 그대로 유지하고, 파일명에 짧은 hash를 붙여 충돌 방지와 사람이 읽기 쉬운 구분을 함께 유지한다.
- 기존 생성된 runtime wav와 metadata/audio_url 참조도 함께 갱신한다.

## 2026-06-03 22:46:00 +09:00

- `audio_storage_service.audio_output_path`를 확장해 사람이 구분 가능한 파일명을 생성하도록 수정했다.
- 새 파일명 생성 함수 `build_audio_filename`을 추가했다.
- `voice_output_service`에서 `node_id`, `target_slot`, `branch_type`, `voice_id`를 audio path 생성에 넘기도록 수정했다.
- 기존 runtime wav 5개를 새 파일명으로 rename했다.
- 기존 metadata의 `audio_path`, `audio_url`도 새 파일명으로 갱신했다.
- 1차 rename 중 source metadata가 부족한 파일에서 `short`가 target slot으로 들어간 문제를 발견했고, `stay_duration`/`stay_address`로 보정했다.

## 2026-06-04 00:00:00 +09:00

- Developer A/B/C 합의에 따라 `agents`와 `services` 하위에 개발자별 전용 패키지를 분리했다.
- Developer A 파일은 `backend/app/agents/agent_a/`, `backend/app/services/service_a/`로 이동했다.
- Developer C 파일은 병합 합의 범위 안에서 `backend/app/agents/agent_c/`, `backend/app/services/service_c/`로 이동했다.
- Developer B는 아직 구현 파일이 없으므로 `backend/app/agents/agent_b/`, `backend/app/services/service_b/` 패키지 초기화 파일만 추가했다.
- `backend/app/agents/__init__.py`와 `backend/app/services/__init__.py`는 공용 패키지 설명만 남기고 하위 모듈 import/export를 하지 않도록 정리했다.
- 새 경로에 맞게 실행 코드와 테스트 import 경로를 수정했다.
- `AGENTS.md`에 개발자별 agents/services 폴더 소유 구조를 명시했다.
## 2026-06-04 00:30:00 +09:00

- Slack Agent의 AgentRun 구조를 참고해 NPC Dialogue Agent 실행 기록을 구조화 로그로 남기는 기능을 구현했다.
- 추가한 Developer A 전용 tool:
  - `backend/app/tools/tool_a/npc_dialogue_evidence_tool.py`
  - `backend/app/tools/tool_a/npc_dialogue_cost_tool.py`
  - `backend/app/tools/tool_a/npc_dialogue_artifact_tool.py`
- 추가한 Developer A 전용 middleware:
  - `backend/app/middleware/middleware_a/npc_dialogue_agent_run_middleware.py`
- 추가한 Developer A 전용 저장소:
  - `backend/app/services/service_a/npc_dialogue_agent_run_store.py`
- AgentRun JSONL 저장 위치:
  - `backend/runtime/agent_runs/npc_dialogue_agent_runs.jsonl`
  - `backend/runtime/agent_runs/npc_dialogue_artifacts.jsonl`
- `build_voice_output_from_level_design`가 실행될 때 AgentRun과 Artifact를 append 방식으로 누적 저장하도록 연결했다.
- 반환 dict에 `agent_run_id`, `agent_run_path`, `artifact_path`, `agent_run`, `agent_run_artifact`를 포함하도록 했다.
- OpenAI LLM 응답에서 token usage가 있으면 `llm` metadata에 `model_name`, `input_tokens`, `output_tokens`, `total_tokens`를 남기도록 했다.
- `AGENTS.md`에 각 agent 전용 tool/middleware 소유권과 FastAPI 전역 middleware 금지 원칙을 추가했다.
- `docs/contracts/change_requests.md`에 공용 AgentRun persistence contract 요청을 추가했다.
- 검증 결과:
  - `uv run pytest backend/tests/test_developer_a_agent_run_logging.py -q`: PASS, 7 passed, 1 warning
  - `uv run ruff check ...`: PASS
  - `uv run mypy ...`: PASS
- warning은 기존 `audioop` deprecation warning이며 이번 AgentRun 구현과 직접 관련은 없다.
## 2026-06-04 00:45:00 +09:00

- AgentRun 로그에 agent 시작/종료와 tool 호출 흐름이 부족하다는 피드백을 반영했다.
- `NPCDialogueAgentRunMiddleware.record_event()`를 추가해 `metadata.events` timeline을 기록하도록 했다.
- `voice_output_service`에서 다음 이벤트를 AgentRun에 남기도록 연결했다.
  - `agent_start`
  - `developer_a_input_service.normalize_level_design_payload`
  - `agent_a.npc_dialogue_agent.generate_npc_dialogue_from_level_design`
  - `voice_profile_service.resolve_voice_profile`
  - `tts_service.build_kokoro_provider_request`
  - `tts_provider_service.KokoroProvider.synthesize`
  - `agent_end`
  - 실패 시 `agent_error`
- 각 이벤트에는 `tool_name`, `data_loaded`, `input_summary`, `output_summary`, `error`를 가능한 범위에서 남긴다.
- 검증 결과:
  - `uv run pytest backend/tests/test_developer_a_agent_run_logging.py -q`: PASS, 7 passed, 1 warning
  - `uv run ruff check ...`: PASS
  - `uv run mypy ...`: PASS
  - `uv run pytest -q`: PASS, 47 passed, 13 warnings

## 2026-06-04 01:10:00 +09:00

- Developer A의 NPC Dialogue AgentRun을 공통 실행 로그에도 함께 저장하도록 구현했다.
- 새 공통 저장소:
  - `backend/app/services/shared/agent_run_log_store.py`
  - `backend/app/services/shared/agent_run_markdown_formatter.py`
  - `backend/app/services/shared/__init__.py`
- 공통 로그 저장 위치:
  - `backend/runtime/generated/agent_runs/unified_agent_runs.jsonl`
  - `backend/runtime/generated/agent_runs/unified_agent_runs.md`
- 기존 Developer A 전용 로그는 유지한다.
  - `npc_dialogue_agent_runs.jsonl`
  - `npc_dialogue_artifacts.jsonl`
- `voice_output_service` 성공/실패 경로 모두에서 공통 로그 append를 호출하도록 연결했다.
- 반환 payload에 추적용 경로를 추가했다.
  - `unified_agent_run_path`
  - `readable_agent_run_path`
- B/C 구현 파일은 수정하지 않았고, B/C가 각자 owned entrypoint에서 같은 공통 writer를 호출하도록 `docs/contracts/change_requests.md`에 Change Request를 추가했다.
- 검증:
  - `uv run pytest backend/tests/test_developer_a_agent_run_logging.py -q`: PASS, 9 passed, 1 warning

## 2026-06-05 00:00:00 +09:00

- NPC Dialogue AgentRun 로그 저장 정책을 공통 `unified_agent_run.v1` 로그로 단일화했다.
- 더 이상 Developer A 전용 런타임 로그 파일을 생성하지 않는다.
  - `npc_dialogue_agent_runs.jsonl`
  - `npc_dialogue_artifacts.jsonl`
  - `backend/runtime/logs/developer_a_events.jsonl`
- `NPCDialogueAgentRunStore`는 `unified_agent_runs.jsonl`과 `unified_agent_runs.md` append만 담당하도록 정리했다.
- `voice_output_service`에서 `runtime/logs/developer_a_events.jsonl` start/end/error 기록을 제거했다.
- `build_voice_output_from_level_design` 반환 payload에서 중복 로그 경로 필드를 제거했다.
  - 제거: `agent_run_path`
  - 제거: `artifact_path`
  - 제거: `agent_run_artifact`
- 유지되는 추적 필드는 다음과 같다.
  - `agent_run_id`
  - `unified_agent_run_path`
  - `readable_agent_run_path`
  - `agent_run`
- 검증:
  - `uv run pytest backend/tests/test_developer_a_agent_run_logging.py::test_voice_output_writes_only_unified_agent_run_records backend/tests/test_developer_a_agent_run_logging.py::test_agent_run_store_appends_only_unified_agent_run_jsonl -q`: PASS, 2 passed, 1 warning
  - `uv run pytest backend/tests/test_developer_a_agent_run_logging.py -q`: PASS, 9 passed, 1 warning
  - `uv run pytest backend/tests/test_unified_agent_run_log.py backend/tests/test_developer_a_agent_run_logging.py -q`: PASS, 10 passed, 1 warning
  - `uv run ruff check .`: PASS
  - `uv run mypy .`: PASS

## 2026-06-05 00:10:00 +09:00

- TTS 생성 속도 로그를 Developer A unified AgentRun에 추가했다.
- `FakeKokoroProvider`와 `RealKokoroProvider` 모두 TTS metadata에 다음 값을 남긴다.
  - `generation_seconds`: TTS wav 생성에 걸린 시간(초)
  - `audio_seconds`: 생성된 음성 길이(초)
  - `real_time_factor`: 생성 시간 / 음성 길이
- `voice_output_service`는 `tts_provider_service.KokoroProvider.synthesize` timeline event의 `output_summary.generation_speed`에 같은 값을 기록한다.
- `metadata.tts_summary.generation_speed`에도 같은 값을 기록해 사람이 읽는 로그와 JSONL 분석 양쪽에서 확인할 수 있게 했다.
- 검증:
  - `uv run pytest backend/tests/test_developer_a_agent_run_logging.py::test_voice_output_writes_only_unified_agent_run_records -q`: PASS, 1 passed, 1 warning

## 2026-06-05 00:30:00 +09:00

- 향후 NPC 추가를 쉽게 하기 위해 `npc_roster_service.py`를 추가했다.
- `officer_miller` 하드코딩을 voice profile, dialogue result, TTS mock voice, AgentRun metadata 경로에서 roster 조회 방식으로 줄였다.
- Kokoro voice는 모델에서 지원하는 voice id 중 NPC별 후보를 `kokoro_voices`에 명시하고, 새 NPC를 추가할 때 선택 의도를 한국어 주석으로 남기도록 했다.
- 현재 `officer_miller`의 Kokoro voice 후보는 사용자 환경의 최근 기본값에 맞춰 `am_onyx`로 유지했다.
- Developer C adapter가 Unreal `npc` context를 Developer A level-design payload의 `npc` 필드로 전달하도록 했다.
- LLM dialogue 경로에서도 LLM 응답의 `speaker`와 `animation`을 그대로 신뢰하지 않고 roster profile의 표시 이름과 기본 animation으로 고정하도록 했다.
- AgentRun metadata에 `dialogue_source_trace`를 추가해 다음 NPC 대사 생성에 사용한 node context, player text preview, Developer B feedback/directive, branch, NPC profile, voice profile을 기록한다.
- TTS 결과 metadata에 `voice_profile_id`와 `speaker_id`를 포함해 로그와 반환 payload에서 같은 voice 선택 근거를 추적할 수 있게 했다.
- 검증:
  - `uv run pytest backend/tests/test_developer_a_npc_roster.py backend/tests/test_developer_a_npc_dialogue.py backend/tests/test_developer_a_agent_run_logging.py -q`: PASS, 22 passed, 1 warning
  - `uv run pytest backend/tests/test_preprototype_flow.py backend/tests/test_unified_agent_run_log.py -q`: PASS, 14 passed, 2 warnings
  - `uv run ruff check .`: PASS
  - `uv run mypy .`: PASS
  - `git diff --check`: PASS
  - `uv run pytest -q`: PASS, 76 passed, 2 warnings

## 2026-06-05 00:45:00 +09:00

- NPC 감정상태를 더 세분화했다.
- 기존 `firm_official` 하나로 처리하던 재시도/차단 상황을 `firm_official`, `stern_official`, `warning_official` 단계로 나눴다.
- `retry_count`, `branch_type`, `tone_hint`, `blocks_progression`을 기준으로 NPC 감정 강도가 올라가도록 했다.
- 대사 정책에는 다음 tone을 추가했다.
  - `formal_stern`: 반복 재시도 후 더 짧고 딱딱한 톤
  - `formal_warning`: 실패 또는 경고 상황에서 추가 심사 가능성을 암시하는 톤
- Kokoro 요청 생성 시 강한 tone일수록 speaking rate를 낮춰 더 단호하게 들리도록 했다.
  - `formal_firm`: `0.90`
  - `formal_stern`: `0.87`
  - `formal_warning`: `0.84`
- Kokoro가 emotion prompt를 직접 지원하지 않는 한계는 유지되므로, 감정 표현은 대사 문체, 문장 길이, pause 제거, speaking rate 조합으로 구현한다.
- 검증:
  - `uv run pytest backend/tests/test_developer_a_npc_emotion_escalation.py -q`: PASS, 4 passed
  - `uv run pytest backend/tests/test_developer_a_npc_emotion_escalation.py backend/tests/test_developer_a_npc_dialogue.py backend/tests/test_developer_a_agent_run_logging.py -q`: PASS, 21 passed, 1 warning
  - `uv run ruff check backend/app/services/service_a backend/app/agents/agent_a backend/tests/test_developer_a_npc_emotion_escalation.py`: PASS
  - `uv run mypy backend/app/services/service_a backend/app/agents/agent_a`: PASS

## 2026-06-05 01:00:00 +09:00

- 사용자 요청에 따라 Officer Miller의 Kokoro voice 후보를 다시 `am_michael`로 변경했다.
- `npc_roster_service.py`, Kokoro provider fallback 기본값, voice output fallback, Developer A 테스트 fixture, C 계약 예시, 실제 Kokoro 테스트 방법 문서를 같은 voice 기준으로 맞췄다.
- 현재 실행 경로에서 Officer Miller의 실제 Kokoro voice는 `am_michael`이다.

## 2026-06-05 01:15:00 +09:00

- GPT key 문제를 임시 우회할 수 있도록 Developer A NPC Dialogue LLM 경로에 Gemini provider를 추가했다.
- `NPC_DIALOGUE_LLM_PROVIDER=openai|gemini`로 provider를 선택할 수 있고, Gemini 사용 시 `GEMINI_API_KEY`와 `NPC_DIALOGUE_LLM_MODEL=gemini-2.5-flash`를 사용한다.
- SDK dependency는 추가하지 않고 기존 `httpx`로 Gemini `generateContent` REST API를 호출한다.
- OpenAI provider는 기본값으로 유지해 언제든 되돌릴 수 있게 했다.
## 2026-06-05 01:35:00 +09:00

- 임시 Gemini provider 경로를 제거하고 학원 서버 Gemma4 vLLM fallback 방식으로 전환했다.
- 기본 provider는 계속 `NPC_DIALOGUE_LLM_PROVIDER=openai`이며, GPT key가 없거나 OpenAI 요청이 실패하는 경우 `NPC_DIALOGUE_LLM_FALLBACK=gemma4_vllm` 설정으로 학원 서버를 사용할 수 있다.
- Gemma4 fallback은 OpenAI 호환 `chat/completions` endpoint를 사용하며, 공통 설정은 `GEMMA4_VLLM_BASE_URL`, `GEMMA4_VLLM_MODEL`, `GEMMA4_VLLM_API_KEY`로 관리한다.
- LLM fallback이 실제로 사용되면 AgentRun 로그의 `model_name`에 `google/gemma-4-26B-A4B-it` 같은 fallback 모델명이 남도록 보정했다.
- 검증
  - `uv run pytest backend/tests/test_developer_a_npc_llm_client.py backend/tests/test_developer_a_npc_dialogue.py backend/tests/test_developer_a_agent_run_logging.py backend/tests/test_developer_a_npc_roster.py backend/tests/test_developer_a_npc_emotion_escalation.py -q`: PASS, 29 passed, 1 warning

## 2026-06-05 12:10:00 +09:00

- Developer B 전용 진행 제어 필드인 `blocks_progression`, `do_not_generate_npc_text`를 Developer A 대사 생성 판단에서 제외했다.
- `normalize_level_design_payload()`가 더 이상 두 필드를 Developer A 정규화 결과에 넣지 않으며, AgentRun 이벤트 요약에서도 해당 값을 읽지 않는다.
- NPC 감정/정책 판단도 `blocks_progression` 대신 `branch_type`, `tone_hint`, `retry_count`, `task_success`, `clarity` 같은 A가 실제로 쓰는 입력만 사용하도록 정리했다.
- 검증
  - `uv run pytest backend/tests/test_developer_a_npc_dialogue.py backend/tests/test_developer_a_npc_emotion_escalation.py backend/tests/test_developer_a_agent_run_logging.py -q`: PASS, 23 passed, 1 warning

## 2026-06-05 12:35:00 +09:00

- `MURPHY_NPC_DIALOGUE_MODE=llm`일 때는 Developer B의 `npc_recast_line_candidate`가 없어도 먼저 NPC Dialogue LLM을 호출하도록 순서를 변경했다.
- 이제 후보 대사가 없으면 rule fallback 문장을 최종 결과로 바로 쓰지 않고, LLM에 전달할 seed 후보로만 사용한다.
- LLM/Gemma4가 대사와 `tts_text`를 생성하면 최종 TTS는 해당 LLM 결과를 사용하고, rule fallback은 실제 LLM 실패 시에만 최종 대사로 사용된다.
- OpenAI key가 없어 Gemma4 fallback client가 직접 사용되는 경우도 fallback wrapper를 통과하게 해서 `llm.fallback_used=true`, `model_name=google/gemma-4-26B-A4B-it`로 로그에 남긴다.
- 실제 smoke 결과
  - 입력에 `npc_recast_line_candidate`가 없는 상태에서 `OPENAI_API_KEY=''`, `NPC_DIALOGUE_LLM_FALLBACK=gemma4_vllm`, `use_real_tts=True`, `use_llm_dialogue=True`로 실행했다.
  - Gemma4가 생성한 `npc_text`/`tts_text`가 Kokoro TTS 입력으로 사용됐고 WAV 생성이 성공했다.
  - 결과 로그: `llm.used=true`, `llm.fallback_used=true`, `llm.seed_fallback_used=true`, `tts_status=ok`.
- 검증
  - `uv run pytest backend/tests/test_developer_a_npc_llm_client.py backend/tests/test_developer_a_npc_dialogue.py -q`: PASS, 12 passed, 1 warning
  - `uv run pytest -q`: PASS, 89 passed, 2 warnings
  - `uv run ruff check .`: PASS
  - `uv run mypy .`: PASS
