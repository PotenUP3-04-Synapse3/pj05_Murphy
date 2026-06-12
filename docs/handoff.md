# Handoff

## Current Status

Phase 1 bootstrap is complete, Phase 2 contracts exist, and the AI-only
pre-prototype turn flow is now implemented through merged A/B/C packages. The
repository has a Developer C FastAPI backend package, C-side schemas, real
Developer B deterministic policy wiring, Developer A voice artifact wiring, a
Whisper-large-v3-turbo STT wrapper, an orchestrator, a strengthened validator,
and tests for JSON mock and multipart sample-wav turn flows. The STT contract
is local-first with API fallback. Automated tests keep deterministic STT through
`MURPHY_STT_MODE=mock`. Runtime settings now load from `.env` through
`pydantic-settings`, and the endpoint can enable real Kokoro TTS through
`MURPHY_TTS_MODE=real`. Developer C Understanding Agent now supports
deterministic `rule` mode and optional OpenAI-assisted `llm` mode with rule
fallback.

## Developer C Alpha Plan Notice

2026-06-10 Developer C / Sean Han is moving the prototype toward Alpha in
phases while preserving A/B/C ownership boundaries.

Alpha gameplay direction captured from the latest planning discussion:

- The current prototype is NPC-prompt-first: Unreal sends the fixed current
  NPC question context and player wav, Developer C runs STT and Understanding,
  Developer B evaluates the answer and branch, Developer A returns NPC
  dialogue/TTS, then Developer C assembles AI-to-Unreal JSON.
- Alpha must also support player-initiated interactions where the player walks
  up to an NPC and speaks first.
- NPC interactions must distinguish quest dialogue from ambient daily dialogue.
  Both NPC-first and player-first starts are valid.
- The rough Alpha flow is: start screen, single/multi select, takeoff
  cinematic, name entry on a customs declaration UI, seatmate level-test
  conversation on the plane, JFK arrival objective UI, immigration, baggage
  claim, odd baggage-item explanation, airport exit cinematic, and scoreboard.
- Immigration officer NPCs are fixed-question, NPC-first scenario agents. Desk
  and roaming staff may remain interactable after their main scenario beats.
- Time pressure and failure policy remain gameplay constraints: 30-second
  answers, repeated timeouts or unsatisfactory answers can fail, and dangerous
  words can trigger an immediate bad ending.
- Random baggage item/location keywords should be authored by humans in table
  data for Unreal to consume. AI may generate dialogue around those authored
  keywords but must not invent branch authority.

Developer C Alpha phases:

1. Alpha 0 - Team notice and contract alignment. Document the C-owned plan for
   A/B, keep A/B implementation files read-only, and use
   `docs/contracts/change_requests.md` for any cross-owner behavior changes.
2. Alpha 1 - Request context and timing baseline. Add a C-owned interaction
   context so Unreal can mark NPC-first vs player-first, quest vs ambient, and
   time-limit metadata. Add stage timing to responses/log summaries so STT,
   Understanding, Developer B, Developer A/TTS, response build, and validation
   latency can be measured.
3. Alpha 2 - Understanding Agent generic slot extraction. Replace the current
   per-slot strict schema/repair pattern with a generic slot evidence contract
   that can read `node_context.required_slots`, return allowed slot evidence,
   and keep Developer B as the only branch authority.
4. Alpha 3 - Scenario flow contract. Map Alpha scene ids, quest ids, and
   interactability rules without replacing Developer B's branch authority or
   Developer A's NPC wording authority.
5. Alpha 4 - STT provider benchmark. Compare the current local-first Whisper
   path with an API provider path behind the C-owned STT adapter.
6. Alpha 5 - Realtime voice path. Evaluate WebSocket streaming STT for player
   speech turns if timing data shows batch wav STT is the main latency issue.

No immediate Developer A or Developer B implementation change is required for
Alpha 1 or Alpha 2. Developer C added additive request/response metadata and
C-owned Understanding postprocessing only; any future change requiring A/B logic
changes must be filed as a change request first.

## 2026-06-12 Developer C Follow-up

Developer C implemented Alpha 2 generic slot evidence in the C-owned
Understanding layer. The LLM can now return `slot_evidence` entries for the
current node's required, optional, or critical slots. Developer C filters those
entries to the current node, drops unrelated or forbidden slot names such as
`next_node_id` and `npc_text`, and converts accepted evidence into the existing
`extracted_slots` dict before Developer B receives the policy input.

Changed:

- Added `SlotEvidence` and `UnderstandingOutput.slot_evidence` to the C schema.
- Updated the Understanding LLM strict schema and normalization so generic slot
  evidence can fill `extracted_slots` without adding one strict slot key per
  scenario node.
- Added C postprocessing that accepts only current-node slots and keeps
  Developer B as the sole branch/progression authority.
- Kept deterministic `visit_purpose` and `stay_duration` repairs as regression
  guards for the existing prototype nodes.
- Added tests for `stay_location` generic evidence, forbidden slot filtering,
  and strict schema compatibility.

Changed files for this update:

- `backend/app/schemas/game_turn.py`
- `backend/app/agents/agent_c/understanding_llm_client.py`
- `backend/app/agents/agent_c/understanding_agent.py`
- `backend/tests/test_understanding_agent.py`
- `backend/tests/test_understanding_llm_client.py`
- `docs/contracts/developer_c_schema_contract.md`
- `docs/contracts/developer_c_adapter_contracts.md`
- `docs/handoff.md`

Verification for this update:

- `uv run pytest backend/tests/test_understanding_agent.py backend/tests/test_understanding_llm_client.py backend/tests/test_preprototype_flow.py -q`:
  PASS, 34 passed, 2 warnings.
- `uv run pytest -q`: PASS, 193 passed, 2 warnings.
- `uv run ruff check .`: PASS.
- `uv run mypy .`: PASS, no issues in 91 source files.
- `git diff --check`: PASS with Git's normal CRLF working-copy warnings only.

## 2026-06-11 Developer C Follow-up

Developer C fixed the IMM_003_DURATION progression issue in the C-owned
Understanding layer. The root cause was that rule mode, LLM structured output,
and LLM postprocessing only knew how to fill `visit_purpose`, while the duration
node requires `stay_duration`. C now recognizes duration answers such as
`5 days`, `five days`, `one week`, and `until Friday`, and repairs missing
LLM `stay_duration` slots before calling Developer B. Developer B's
`intent_success and not missing_slots` success policy remains unchanged.

Developer C also documented the Alpha realtime caption transport candidate:
add a C-owned WebSocket STT session for partial and committed transcripts while
keeping the existing multipart wav `/respond` path as the fallback baseline.
Partial transcripts are for Unreal subtitle UI only; committed transcripts enter
the normal C orchestrator path.

Next Alpha priority: refactor the C-owned Understanding Agent around generic
slot evidence before expanding the full Alpha scenario flow. The current
`visit_purpose` and `stay_duration` extractors are acceptable regression guards,
but new scene slots should not require one hardcoded extractor per node.

## Developer A ElevenLabs TTS Provider Update - 2026-06-09

Developer A integrated ElevenLabs as an official selectable TTS provider. The
runtime can now switch providers with:

```text
MURPHY_TTS_PROVIDER=elevenlabs
MURPHY_TTS_PROVIDER=edge
MURPHY_TTS_PROVIDER=kokoro
MURPHY_TTS_PROVIDER=chatterbox
```

Generated ElevenLabs WAV files are stored under:

```text
backend/runtime/generated/audio/elevenlabs/
```

Runtime settings:

```text
MURPHY_ELEVENLABS_API_KEY=
ELEVENLABS_API_KEY=
MURPHY_ELEVENLABS_BASE_URL=https://api.elevenlabs.io/v1
MURPHY_ELEVENLABS_VOICE_ID=CwhRBWXzGAHq8TQ4Fs17
MURPHY_ELEVENLABS_MODEL_ID=eleven_flash_v2_5
MURPHY_ELEVENLABS_API_OUTPUT_FORMAT=mp3_44100_128
MURPHY_ELEVENLABS_OUTPUT_FORMAT=wav
MURPHY_ELEVENLABS_STABILITY=0.52
MURPHY_ELEVENLABS_SIMILARITY_BOOST=0.82
MURPHY_ELEVENLABS_STYLE=0.42
MURPHY_ELEVENLABS_SPEED=0.80
MURPHY_ELEVENLABS_USE_SPEAKER_BOOST=true
MURPHY_ELEVENLABS_TIMEOUT_SECONDS=60
```

Implementation notes:

- The provider uses the existing `httpx` dependency.
- ElevenLabs MP3 responses are converted to 24kHz mono PCM WAV with `ffmpeg`.
- API keys are read from `.env` or process environment but are not returned in
  provider metadata or AgentRun logs.
- AgentRun tool name: `tts_provider_service.elevenlabs.synthesize`.
- Rollback is immediate by setting `MURPHY_TTS_PROVIDER=edge` or
  `MURPHY_TTS_PROVIDER=kokoro`.

Verification:

- Added tests for provider switching, output path, AgentRun logging, and secret
  redaction.
- ElevenLabs provider can be benchmarked through the integrated
  `/api/game/ai/respond` path with `MURPHY_TTS_PROVIDER=elevenlabs`.

## Developer A Chatterbox TTS Provider Update - 2026-06-09

Developer A added a reversible Chatterbox TTS provider path for stronger
emotion and reference-audio voice conditioning experiments. The runtime can now
switch providers with:

```text
MURPHY_TTS_PROVIDER=kokoro
MURPHY_TTS_PROVIDER=edge
MURPHY_TTS_PROVIDER=chatterbox
```

Generated Chatterbox files are stored under:

```text
backend/runtime/generated/audio/chatterbox/
```

Chatterbox runtime parameters are read from `.env`:

```text
MURPHY_CHATTERBOX_VOICE_ID=officer_miller_ref
MURPHY_CHATTERBOX_REFERENCE_AUDIO=backend/app/assets/voices/officer_miller_ref.wav
MURPHY_CHATTERBOX_EXAGGERATION=0.75
MURPHY_CHATTERBOX_CFG_WEIGHT=0.35
MURPHY_CHATTERBOX_TEMPERATURE=0.60
MURPHY_CHATTERBOX_DEVICE=auto
MURPHY_CHATTERBOX_LANGUAGE_ID=en
MURPHY_CHATTERBOX_OUTPUT_FORMAT=wav
```

Dependency note:

- `chatterbox-tts==0.1.7` requires `torch==2.6.0`, so `pyproject.toml` now
  limits Python to `>=3.12,<3.13` and pins torch to `2.6.0`.
- `pyproject.toml` routes `torch` and `torchaudio` to the PyTorch CUDA 12.4
  wheel index on Windows/Linux.
- Local verification currently imports `torch==2.6.0+cu124`,
  `torch.version.cuda==12.4`, and `chatterbox.tts.ChatterboxTTS`.
- `torch.cuda.is_available()` is `True` on the local RTX 4070 Laptop GPU.
- With `MURPHY_CHATTERBOX_DEVICE=auto`, Developer A uses CUDA when available
  and CPU otherwise.
- If `MURPHY_CHATTERBOX_REFERENCE_AUDIO` is missing, Developer A omits
  `audio_prompt_path` and uses the model default voice rather than failing at
  request construction.

Verification:

- `uv run pytest backend/tests/test_developer_a_agent_run_logging.py -q`
  passed: 14 tests, 1 `audioop` deprecation warning.
- Actual Chatterbox model-weight smoke generation completed on CPU without
  reference audio:
  - Output:
    `backend/runtime/generated/audio/chatterbox/chatterbox_smoke_warning_cpu.wav`
  - Text: `Sir. Answer the question directly.`
  - Audio duration: about 1.76 seconds.
  - Generation time: about 29.04 seconds on CPU.
  - Real-time factor: about 16.50.
  - `reference_audio_exists=false`; Officer Miller voice cloning still needs a
    reference wav under `backend/app/assets/voices/`.
- Actual Chatterbox model-weight smoke generation also completed on CUDA
  without reference audio:
  - Output:
    `backend/runtime/generated/audio/chatterbox/chatterbox_smoke_warning_cuda.wav`
  - Text: `Sir. Answer the question directly.`
  - Audio duration: about 2.04 seconds.
  - Generation time: about 18.06 seconds on RTX 4070 Laptop GPU.
  - Real-time factor: about 8.85.
  - `provider_options.device=cuda`.

Rollback is immediate by setting `MURPHY_TTS_PROVIDER=kokoro` or
`MURPHY_TTS_PROVIDER=edge`.

## Developer A Edge TTS Provider Update - 2026-06-09

Developer A added a reversible Edge TTS provider path without removing Kokoro.
The runtime can switch providers with:

```text
MURPHY_TTS_PROVIDER=kokoro
MURPHY_TTS_PROVIDER=edge
```

Edge TTS currently uses the Python `edge-tts` package to generate MP3 and
converts it to PCM WAV with `ffmpeg` when
`MURPHY_EDGE_TTS_OUTPUT_FORMAT=wav`. Generated Edge files are stored under:

```text
backend/runtime/generated/audio/edge/
```

Smoke result on 2026-06-09:

- Audio duration: about 4.656 seconds.
- Total Edge generation plus WAV conversion: about 0.69 seconds.
- WAV conversion time: about 0.04 seconds.

Rollback is immediate by setting `MURPHY_TTS_PROVIDER=kokoro`.

## Last Completed Task

2026-06-05 Developer C updated the `/respond-dialog` tester usage and audio
input workflow.

Changed:

- `/respond-dialog` now shows a CSS stopwatch icon only while the top status is
  `Running`.
- The `Next WAV` area now includes browser microphone recording controls. The
  browser captures PCM audio, encodes a RIFF WAV file client-side, and submits
  it through the existing multipart `audio` field.
- The browser tester tracks request ids sent by the current page and asks
  `session-usage` for only those request ids. This prevents reused session ids
  such as `session_001` from mixing historical or other-person runs into the
  visible token total.
- `GET /api/game/ai/agent-runs/session-usage` now accepts repeated optional
  `request_ids` query params in addition to `session_id`.
- Session usage normalization now accepts canonical unified usage fields and
  OpenAI-compatible aliases such as `prompt_tokens`, `completion_tokens`, and
  `cost_usd`.

Known usage limitation:

- If an upstream A/B/C AgentRun record stores `model_name` but records zero
  token counts and zero cost, Developer C cannot reconstruct the missing
  provider usage after the fact. The updated summary service will display
  costs when token/cost fields are present or when known-model tokens can be
  estimated.

Changed files for this update:

- `backend/app/api/ai_respond.py`
- `backend/app/services/service_c/agent_run_summary_service.py`
- `demo/respond-dialog/index.html`
- `backend/tests/test_demo_ai_respond_page.py`
- `docs/contracts/developer_c_adapter_contracts.md`
- `docs/handoff.md`

Verification for this update:

- `uv sync`: PASS after approved escalation for uv user-cache access.
- `uv run pytest backend/tests/test_demo_ai_respond_page.py -q`: PASS, 8
  passed, 2 warnings.
- `uv run pytest -q`: PASS, 110 passed, 2 warnings.
- `uv run ruff check .`: PASS.
- `uv run mypy .`: PASS, no issues in 87 source files after approved
  escalation for uv user-cache access.

Developer C added a separate multi-turn browser tester at `/respond-dialog`
without changing the existing `/demo/ai-respond` page. The new page starts at
`IMM_002_PURPOSE`, keeps the left-side wav/Turn JSON upload workflow, and
renders the right side as an iMessage-style transcript with user STT text, NPC
text, per-message audio play buttons, and branch dividers. Browser-side state
now advances playable nodes on `ADVANCE`, keeps the current playable node for
`REASK`/`GIVE_HINT`, accumulates `state_delta`, appends
`previous_node_results`, and regenerates `request_id`/`turn_index` per run.
The page also shows per-turn timing metrics (`Total`, `Status`, `STT`,
`Verdict`) above session token/cost usage. A separate `Next WAV` picker and
`Continue` button let testers continue the current auto-updated scenario state
with only a wav file after the first turn.

Developer C also added demo-only helper APIs:

- `GET /api/game/ai/demo/node/{node_id}` for safe Chapter 0 node context used
  by the browser tester.
- `GET /api/game/ai/agent-runs/session-usage?session_id=<optional>` for
  session-level token and estimated USD cost totals from top-level unified
  AgentRun `model` fields.
- `GET /api/game/ai/agent-runs/latest` now includes `model_usage` while keeping
  the previous compact node summary response fields.

Changed files for this update:

- `backend/app/main.py`
- `backend/app/api/ai_respond.py`
- `backend/app/services/service_c/agent_run_summary_service.py`
- `demo/respond-dialog/index.html`
- `backend/tests/test_demo_ai_respond_page.py`
- `backend/tests/test_preprototype_flow.py`
- `docs/contracts/developer_c_adapter_contracts.md`
- `docs/handoff.md`

Verification for this update:

- `uv sync`: PASS. It completed after approved escalation because sandboxed
  `uv` cache access was denied.
- `uv run pytest backend/tests/test_demo_ai_respond_page.py -q`: PASS, 6
  passed, 2 warnings.
- `uv run pytest backend/tests/test_preprototype_flow.py backend/tests/test_unified_agent_run_log.py -q`:
  PASS, 15 passed, 2 warnings.
- `uv run pytest -q`: PASS, 106 passed, 2 warnings.
- `uv run ruff check .`: PASS.
- `uv run mypy .`: PASS, no issues in 86 source files. The sandboxed run hit a
  `uv` cache access-denied error, so the same command was rerun with approved
  escalation.

Developer A NPC dialogue/voice path is now structured around an NPC roster.
`backend/app/services/service_a/npc_roster_service.py` owns NPC display name,
role, default animation, fallback text, mock voice id, and Kokoro voice
candidates. The current roster contains `officer_miller`; unknown or missing
NPC ids fall back to that profile. Kokoro voice ids are configured per NPC
through `kokoro_voices`, with Korean code comments marking that the values must
come from the installed Kokoro model's supported voice list.

Developer C's `DevANpcDialogueClient` forwards Unreal `npc` context into
Developer A's level-design payload, while final NPC dialogue text and voice
style remain Developer A-owned. Developer A AgentRun metadata now includes
`dialogue_source_trace`, which records the node context, player text preview,
Developer B feedback/directive, branch, NPC profile, and voice profile data
used to shape the next NPC line and TTS selection.
LLM dialogue mode also keeps roster-owned speaker and animation values instead
of trusting model-provided presentation identifiers.

Verification for this update:

- `uv run pytest backend/tests/test_developer_a_npc_roster.py backend/tests/test_developer_a_npc_dialogue.py backend/tests/test_developer_a_agent_run_logging.py -q`: PASS, 22 passed, 1 warning.
- `uv run pytest backend/tests/test_preprototype_flow.py backend/tests/test_unified_agent_run_log.py -q`: PASS, 14 passed, 2 warnings.
- `uv run ruff check .`: PASS.
- `uv run mypy .`: PASS.
- `git diff --check`: PASS.
- `uv run pytest -q`: PASS, 76 passed, 2 warnings.

Automated tests remain deterministic and do not require real API keys. User-local
manual verification may enable real API-backed LLM/TTS modes through environment
settings when explicitly requested.

Gemma4 vLLM fallback support replaces the previous temporary Gemini provider
path for the GPT key outage case. OpenAI remains the primary provider, and the
academy server is tried only when the fallback flags are enabled:

- `GEMMA4_VLLM_BASE_URL=http://100.95.34.69:8001/v1`
- `GEMMA4_VLLM_MODEL=google/gemma-4-26B-A4B-it`
- `GEMMA4_VLLM_API_KEY=dummy`
- `MURPHY_UNDERSTANDING_LLM_FALLBACK=gemma4_vllm`
- `NPC_DIALOGUE_LLM_FALLBACK=gemma4_vllm`

The academy server is a vLLM OpenAI-compatible `/v1/chat/completions` endpoint.
Smoke verification on 2026-06-05 confirmed:

- `GET http://100.95.34.69:8001/v1/models`: PASS, model
  `google/gemma-4-26B-A4B-it`, owned by `vllm`.
- `POST /v1/chat/completions`: PASS, returned `OK`.
- Developer A real path with `NPC_DIALOGUE_LLM_FALLBACK=gemma4_vllm` and
  `use_real_tts=True`: PASS, generated
  `backend\runtime\generated\gemma4_wav_smoke\audio\kokoro\IMM_002_PURPOSE_unknown_slot_success_am_michael_737b8af0.wav`.
- Latest AgentRun log includes TTS speed:
  `generation_seconds=4.129077799996594`,
  `audio_seconds=3.575`,
  `real_time_factor=1.1549867972018444`.

Verification for this update:

- `uv run pytest backend/tests/test_developer_a_npc_llm_client.py backend/tests/test_developer_a_npc_dialogue.py backend/tests/test_understanding_llm_client.py backend/tests/test_settings_service.py -q`: PASS, 19 passed, 1 warning.
- `uv run pytest -q`: PASS, 87 passed, 2 warnings.
- `uv run ruff check .`: PASS.
- `uv run mypy .`: PASS.
- `git diff --check`: PASS.

Removed duplicate Developer A-only runtime logs from the NPC dialogue voice
output path. Developer A now appends NPC dialogue AgentRun records only through
the shared `unified_agent_run.v1` sink:
`backend/runtime/generated/agent_runs/unified_agent_runs.jsonl` and
`backend/runtime/generated/agent_runs/unified_agent_runs.md`. The old
`npc_dialogue_agent_runs.jsonl`, `npc_dialogue_artifacts.jsonl`, and
`backend/runtime/logs/developer_a_events.jsonl` write paths were removed from
runtime behavior.

Enabled the real STT plus real Kokoro TTS endpoint demo path. The C-owned
`DevANpcDialogueClient` now reads `MURPHY_TTS_MODE` and
`MURPHY_NPC_DIALOGUE_MODE` from `AppSettings` and passes `use_real_tts` /
`use_llm_dialogue` into Developer A's `build_voice_output_from_level_design()`
service. Deterministic defaults remain `MURPHY_STT_MODE=mock`,
`MURPHY_TTS_MODE=fake`, and `MURPHY_NPC_DIALOGUE_MODE=rule` for tests. A demo
turn fixture now exists at `demo/input/imm_002_purpose.json`.

Developer C also added real AI mode for the Understanding Agent. Set
`MURPHY_UNDERSTANDING_MODE=llm` with `OPENAI_API_KEY` to call the C-owned
OpenAI Responses API client. Missing API key, request failure, invalid JSON,
schema failure, or forbidden authority fields fall back to deterministic rule
mode. Developer C now appends an orchestration-level unified AgentRun record to
Developer A's shared log sink and includes the Understanding Agent's
LLM/fallback trace inside the orchestrator event timeline. The Understanding
LLM structured output schema now follows OpenAI strict schema requirements, and
rule fallback recognizes family, friend, business, study, transit, and tourism
visit-purpose values.

Developer C also debugged a recurring NPC fallback response:
`Okay. Please continue.`. The cause was a valid Understanding LLM response that
missed `visit_purpose=family_visit` for `I'm here to visit my uncle.`, so B
returned `REASK/clarify` and A intentionally used its safe fallback dialogue.
C now applies a narrow post-processing guard when a valid LLM response leaves a
required `visit_purpose` slot empty but the deterministic allowed-value
classifier can clearly fill it. The guard records
`last_trace.postprocessing.slot_repair_applied=true` and preserves LLM mode
rather than treating it as provider fallback.

## Changed Files

- `.env.example`
- `.gitignore`
- `README.md`
- `demo/input/imm_002_purpose.json`
- `backend/app/services/service_c/settings_service.py`
- `backend/app/services/service_c/stt_service.py`
- `backend/tests/test_settings_service.py`
- `backend/app/integrations/dev_a_npc_dialogue_client.py`
- `backend/app/agents/agent_c/understanding_agent.py`
- `backend/app/agents/agent_c/understanding_llm_client.py`
- `backend/app/agents/agent_c/visit_purpose_classifier.py`
- `backend/app/middleware/middleware_c/developer_c_agent_run_middleware.py`
- `backend/app/integrations/dev_b_level_hint_client.py`
- `backend/app/main.py`
- `backend/app/schemas/game_turn.py`
- `backend/app/services/service_c/openkb_service.py`
- `backend/app/services/service_c/response_builder.py`
- `backend/app/services/service_c/validator.py`
- `backend/tests/test_preprototype_flow.py`
- `backend/tests/test_understanding_agent.py`
- `backend/tests/test_understanding_llm_client.py`
- `docs/contracts/dependency_contract.md`
- `docs/contracts/developer_c_adapter_contracts.md`
- `docs/contracts/developer_c_schema_contract.md`
- `docs/handoff.md`
- `backend/app/services/shared/__init__.py`
- `backend/app/services/shared/agent_run_log_store.py`
- `backend/app/services/shared/agent_run_markdown_formatter.py`
- `backend/app/services/service_a/npc_dialogue_agent_run_store.py`
- `backend/app/services/service_a/npc_roster_service.py`
- `backend/app/services/service_a/voice_profile_service.py`
- `backend/app/services/service_a/tts_service.py`
- `backend/app/services/service_a/voice_output_service.py`
- `backend/app/agents/agent_a/npc_dialogue_agent.py`
- `backend/app/services/service_a/developer_a_runtime_log_service.py` (removed)
- `backend/runtime/logs/developer_a_events.jsonl` (removed)
- `backend/tests/test_developer_a_agent_run_logging.py`
- `backend/tests/test_developer_a_npc_roster.py`
- `backend/tests/test_developer_a_npc_dialogue.py`
- `backend/tests/test_unified_agent_run_log.py`
- `docs/implementation_logs/developer_a_implementation_log_kimyonghee.md`
- `docs/contracts/developer_a_agent_spec.md`
- `docs/contracts/change_requests.md`
- `AGENTS.md`
- `docs/preprototype_status_demo_plan.md`
- `docs/superpowers/plans/2026-06-04-real-understanding-agent-mode.md`
- `docs/superpowers/plans/2026-06-04-real-stt-kokoro-endpoint-demo.md`
- `docs/superpowers/plans/2026-06-04-preprototype-abc-integration.md`

## Commands Run

- `git status --short --branch`
- `Get-Content -Path backend\app\services\stt_service.py`
- `Get-Content -Path .gitignore`
- `Get-Content -Path .env.example`
- `Get-Content -Path backend\tests\test_stt_service.py`
- `Get-Content -Path README.md`
- `Get-Content -Path docs\contracts\dependency_contract.md`
- `Get-Content -Path docs\contracts\developer_c_schema_contract.md`
- `Get-Content -Path docs\preprototype_status_demo_plan.md`
- `Get-Content -Path docs\handoff.md`
- `uv run pytest backend/tests/test_settings_service.py -q` (RED: settings service did not exist)
- `uv run pytest backend/tests/test_settings_service.py -q` (GREEN: 2 passed)
- `rg --files -g ".gitignore" -g ".env*" -g "*.env" -g "pyproject.toml" -g "*.md"`
- `rg -n "MURPHY_STT|OPENAI_API_KEY|\.env|Runtime STT|STT Runtime Setup" README.md docs\contracts\dependency_contract.md docs\contracts\developer_c_schema_contract.md docs\contracts\developer_c_adapter_contracts.md docs\preprototype_status_demo_plan.md docs\handoff.md`
- `git diff --stat`
- `uv sync` (first sandboxed attempt failed on user-level uv cache initialization)
- `uv sync` (rerun with approved escalation: resolved 93 packages, audited 55 packages)
- `uv run pytest` (9 passed, 1 warning)
- `uv run ruff check .` (passed)
- `uv run mypy .` (initially failed on typed `_env_file` constructor usage)
- `uv run mypy .` (passed)
- `git diff --check` (passed)
- `uv run pytest backend/tests/test_preprototype_flow.py -q` (RED: OpenKB only supported `IMM_002_PURPOSE`; B adapter was still mock)
- `uv run pytest backend/tests/test_preprototype_flow.py::test_api_accepts_multipart_turn_json_and_sample_wav -q` (RED: A adapter did not produce next-question dialogue or `npc.audio_url`)
- `uv run pytest backend/tests/test_preprototype_flow.py::test_validator_rejects_developer_b_hint_payload_when_hint_is_not_needed backend/tests/test_preprototype_flow.py::test_validator_requires_npc_audio_url_for_preprototype_response -q` (RED: validator did not enforce these invariants)
- `uv run pytest backend/tests/test_preprototype_flow.py backend/tests/test_developer_a_npc_dialogue.py backend/tests/dev_b/test_developer_b_policy_engine.py -q` (20 passed, 2 warnings)
- `uv run pytest` (27 passed, 2 warnings)
- `uv run ruff check .` (passed)
- `uv run mypy .` (passed)
- `uv run pytest backend/tests/test_settings_service.py::test_app_settings_reads_values_from_env_file -q` (RED: `AppSettings` had no `murphy_tts_mode`)
- `uv run pytest backend/tests/test_preprototype_flow.py::test_dev_a_adapter_uses_real_tts_and_llm_modes_from_settings -q` (RED: `DevANpcDialogueClient` had no settings or builder injection)
- `uv run pytest backend/tests/test_settings_service.py::test_app_settings_reads_values_from_env_file -q` (GREEN: 1 passed)
- `uv run pytest backend/tests/test_preprototype_flow.py::test_dev_a_adapter_uses_real_tts_and_llm_modes_from_settings -q` (GREEN: 1 passed, 2 warnings)
- `uv run pytest` (28 passed, 2 warnings)
- `uv run ruff check .` (passed)
- `uv run mypy .` (passed)
- `git diff --check` (passed with CRLF conversion warnings only)
- `uv run pytest backend/tests/test_settings_service.py::test_app_settings_reads_values_from_env_file -q` (RED: `AppSettings` had no `murphy_understanding_mode`)
- `uv run pytest backend/tests/test_understanding_agent.py -q` (RED: `UnderstandingAgent` had no settings or LLM client injection)
- `uv run pytest backend/tests/test_settings_service.py::test_app_settings_reads_values_from_env_file -q` (GREEN: 1 passed)
- `uv run pytest backend/tests/test_understanding_agent.py -q` (GREEN: 2 passed)
- `uv run pytest backend/tests/test_preprototype_flow.py -q` (GREEN: 9 passed, 2 warnings after deterministic runtime fixture cache clearing)
- `uv run ruff check .` (passed)
- `uv run mypy .` (initially failed on `UnderstandingLLMClient.model` protocol mutability)
- `uv run mypy .` (passed after using a read-only protocol property)
- `uv run pytest backend/tests/test_understanding_agent.py backend/tests/test_settings_service.py -q` (4 passed)
- `uv run pytest` (42 passed, 2 warnings)
- `uv run ruff check .` (passed)
- `uv run mypy .` (passed)
- `git diff --check` (passed with CRLF conversion warnings only)
- `uv run pytest backend/tests/test_understanding_agent.py backend/tests/test_unified_agent_run_log.py -q` (RED: `UnderstandingAgent.last_trace` and `Orchestrator(agent_run_root=...)` were not implemented)
- `uv run pytest backend/tests/test_understanding_agent.py backend/tests/test_unified_agent_run_log.py -q` (GREEN: 3 passed, 1 warning)
- `uv run pytest` (52 passed, 2 warnings)
- `uv run ruff check .` (passed)
- `uv run mypy .` (passed)
- `git diff --check` (passed with CRLF conversion warnings only)
- `uv run pytest backend/tests/test_understanding_llm_client.py backend/tests/test_understanding_agent.py backend/tests/test_preprototype_flow.py::test_orchestrator_advances_family_visit_purpose_to_duration_node -q` (RED: strict schema rejected `extracted_slots`, null slots were not normalized, uncle fallback did not fill `family_visit`, and orchestrator stayed on `REASK`)
- `uv run pytest backend/tests/test_understanding_llm_client.py backend/tests/test_understanding_agent.py backend/tests/test_preprototype_flow.py::test_orchestrator_advances_family_visit_purpose_to_duration_node -q` (GREEN: 8 passed, 2 warnings)
- `uv run pytest` (58 passed, 2 warnings)
- `uv run ruff check .` (passed)
- `uv run mypy .` (passed)
- `git diff --check` (passed with CRLF conversion warnings only)
- `uv run pytest backend/tests/test_understanding_llm_client.py::test_extract_structured_json_preserves_llm_usage backend/tests/test_unified_agent_run_log.py::test_orchestrator_unified_agent_run_includes_understanding_llm_tokens_and_cost -q` (RED: Understanding usage was not preserved and C unified record used zero token/cost values)
- `uv run pytest backend/tests/test_understanding_llm_client.py::test_extract_structured_json_preserves_llm_usage backend/tests/test_unified_agent_run_log.py::test_orchestrator_unified_agent_run_includes_understanding_llm_tokens_and_cost -q` (GREEN: 2 passed, 1 warning)
- `uv run pytest` (60 passed, 2 warnings)
- `uv run ruff check .` (passed)
- `uv run mypy .` (passed)
- `git diff --check` (passed with CRLF conversion warnings only)
- `uv run pytest backend/tests/test_understanding_agent.py::test_understanding_agent_repairs_llm_missing_allowed_visit_purpose_slot -q` (RED: valid LLM output left `intent_success=false` and `visit_purpose` missing)
- `uv run pytest backend/tests/test_preprototype_flow.py::test_orchestrator_uses_repaired_llm_visit_purpose_before_developer_a_dialogue -q` (RED: orchestrator returned `REASK`)
- `uv run pytest backend/tests/test_understanding_agent.py::test_understanding_agent_repairs_llm_missing_allowed_visit_purpose_slot backend/tests/test_preprototype_flow.py::test_orchestrator_uses_repaired_llm_visit_purpose_before_developer_a_dialogue -q` (GREEN: 2 passed, 2 warnings)
- `uv run pytest backend/tests/test_understanding_agent.py backend/tests/test_preprototype_flow.py -q` (GREEN: 16 passed, 2 warnings)
- `uv run pytest` (initial rerun found 2 test-isolation/log-order failures unrelated to the slot repair)
- `uv run pytest backend/tests/dev_b/test_developer_b_agent_run_log.py::test_developer_b_appends_unified_agent_run_for_success_turn backend/tests/test_unified_agent_run_log.py::test_orchestrator_unified_agent_run_includes_understanding_llm_tokens_and_cost -q` (GREEN: 2 passed, 1 warning after deterministic B feedback mode and C-owner record selection test fixes)
- `uv run pytest` (GREEN: 66 passed, 2 warnings)
- `uv run ruff check .` (passed)
- `uv run mypy .` (passed)
- `git diff --check` (passed with CRLF conversion warnings only)
- `uv sync` (removed stale `en-core-web-sm==3.8.0` from the local environment)
- `uv run pytest backend/tests/test_developer_a_agent_run_logging.py::test_voice_output_writes_only_unified_agent_run_records backend/tests/test_developer_a_agent_run_logging.py::test_agent_run_store_appends_only_unified_agent_run_jsonl -q` (RED: old `npc_dialogue_agent_runs.jsonl` was still created)
- `uv run pytest backend/tests/test_developer_a_agent_run_logging.py::test_voice_output_writes_only_unified_agent_run_records backend/tests/test_developer_a_agent_run_logging.py::test_agent_run_store_appends_only_unified_agent_run_jsonl -q` (GREEN: 2 passed, 1 warning)
- `uv run pytest backend/tests/test_developer_a_agent_run_logging.py -q` (GREEN: 9 passed, 1 warning)
- `uv run pytest backend/tests/test_unified_agent_run_log.py backend/tests/test_developer_a_agent_run_logging.py -q` (GREEN: 10 passed, 1 warning)
- `uv run ruff check .` (passed)
- `uv run mypy .` (passed)
- `uv run pytest -q` (failed once because the current environment made Developer B log `model_name=gpt-4o-mini` instead of the test-expected `rule_based`)
- `DEV_B_FEEDBACK_LLM_MODE=rule uv run pytest -q` (GREEN: 62 passed, 2 warnings)

## Current Architecture

The current implementation exposes `GET /health` and
`POST /api/game/ai/respond`. The pre-prototype endpoint accepts JSON mock input
and multipart `turn` JSON plus wav input.

The target Developer C architecture is a FastAPI backend that receives wav
audio from Unreal, runs STT, retrieves OpenKB context, runs a deterministic
Understanding Agent, calls replaceable Developer B and Developer A adapters,
records validated error-capture markdown, assembles Unreal response JSON, and
validates all responses before returning them.

# Developer B Update - 2026-06-04

Developer B added a first deterministic `dev_b_policy.v1` policy engine without
modifying C-owned adapters, schemas, OpenKB runtime, orchestrator, validator, or
response builder.

Added B-owned runtime files:

- `backend/app/agents/agent_b/english_level_hint_agent.py`
- `backend/app/services/service_b/scenario_state_machine.py`
- `backend/app/services/service_b/level_adaptation_controller.py`
- `backend/app/data/scenario_nodes.json`
- `backend/app/prompts/english_level_hint_prompt.md`

Added B-focused tests under `backend/tests/dev_b/` to cover clear success,
broken English, clarify, retry/hint, warning/bad-end, allowed next-node guards,
empty allowed-node failure, node JSON coverage, and report/feedback fields.

Coordination request:

- `docs/contracts/change_requests.md` now requests that Developer C wire
  `backend/app/integrations/dev_b_level_hint_client.py` to
  `backend.app.agents.agent_b.EnglishLevelHintAgent` and sync
  `backend/app/data/scenario_nodes.json` into the C-owned OpenKB runtime.

Verification note:

- After the lockfile repair, Developer B verification passes:
  `uv run pytest backend/tests/dev_b -q` reports `10 passed`,
  `uv run pytest` reports `23 passed, 2 warnings`, `uv run ruff check .`
  passes, and `uv run mypy .` passes when run outside the sandbox because the
  sandboxed run cannot access the user-level uv cache.

# Developer B OpenKB Runtime Write Update - 2026-06-04

Developer B now owns runtime feedback/error writes under the OpenKB `dev_b`
namespace. The B policy engine writes deterministic JSONL and markdown records
to `backend/runtime/openkb/dev_b/` through
`backend/app/services/service_b/openkb_feedback_writer.py`. Static B OpenKB
content seeds live under `backend/app/kb/dev_b/`.

Added/changed B write behavior:

- `DevBPolicyOutput` now has an optional additive `openkb_write` field with the
  write attempt status, namespace, record id, JSONL path, markdown path, and
  error message.
- `EnglishLevelHintAgent.evaluate_turn()` builds the policy output first, then
  attempts the B OpenKB write. Writer failures do not change branch, verdict, or
  state delta; they are surfaced through `openkb_write.succeeded == false`.
- Runtime record ids are deterministic from request id, node id, turn index, and
  error ids, so repeated evaluation of the same turn does not append duplicate
  JSONL entries.

Coordination request:

- Developer C should update logging to avoid duplicate error markdown records
  when `dev_b_policy.openkb_write.succeeded == true`.
- Developer C validator should validate B write references for namespace and
  local path safety.
- Developer C final report retrieval should consume B-authored records by
  `openkb_write.record_id`.

# Developer B LLM-Assisted Feedback Update - 2026-06-04

Developer B now has an optional LLM-assisted feedback/hint layer on top of the
deterministic policy engine. Branch, next-node, verdict, and state-delta remain
rule-based. The LLM layer may only improve learning feedback text, report text,
Focus-on-Form explanations, and rubric score candidates.

Added B-owned runtime files:

- `backend/app/agents/agent_b/feedback_hint_llm_client.py`
- `backend/app/services/service_b/feedback_hint_generator.py`
- `backend/app/services/service_b/tier_difficulty_controller.py`

Added optional `DevBPolicyOutput` fields:

- `rubric_scores`
- `difficulty_profile`
- `feedback_generation`

Runtime behavior:

- `DEV_B_FEEDBACK_LLM_MODE=rule` is the default and does not call an external
  model.
- `DEV_B_FEEDBACK_LLM_MODE=llm` enables the B feedback LLM path.
- `DEV_B_FEEDBACK_LLM_MODEL` defaults to `gpt-4o-mini`.
- `DEV_B_FEEDBACK_LLM_TIMEOUT_SECONDS` defaults to `10`.
- `OPENAI_API_KEY` is required only when B LLM mode is enabled and no fake
  client is injected.
- Missing API keys, failed LLM calls, or invalid LLM JSON produce
  `feedback_generation.mode == "fallback"` and preserve the deterministic
  branch/verdict/state.

Coordination request:

- Developer C should treat `rubric_scores`, `difficulty_profile`, and
  `feedback_generation` as optional metadata.
- Developer C validator should ensure these optional fields never override
  branch, next-node, state-delta, or verdict authority.
- Final report generation can use B's OpenKB records to distinguish rule, LLM,
  and fallback feedback sources.

# Developer B Unified AgentRun Logger Update - 2026-06-04

Developer B now appends execution-level AgentRun records using the shared
`unified_agent_run.v1` format already used by Developer A and Developer C. The
new B logger is separate from `OpenKBFeedbackWriter`: OpenKB records remain
learning feedback/error artifacts, while AgentRun records explain the B policy
engine's runtime decision path.

Added/changed files:

- `backend/app/services/service_b/developer_b_agent_run_logger.py`
- `backend/app/agents/agent_b/english_level_hint_agent.py`
- `backend/app/services/service_b/__init__.py`
- `backend/app/integrations/dev_b_level_hint_client.py`
- `backend/app/services/service_c/orchestrator.py`
- `backend/tests/dev_b/test_developer_b_agent_run_log.py`
- `backend/tests/test_unified_agent_run_log.py`
- `docs/portfolio_dev_b.md`

Runtime behavior:

- B records append to `backend/runtime/generated/agent_runs/unified_agent_runs.jsonl`
  and `backend/runtime/generated/agent_runs/unified_agent_runs.md`.
- B uses `agent_name=english_level_hint_agent` and `owner=developer_b`.
- The B event timeline records state-machine, level, hint, feedback strategy,
  form issue, rubric/difficulty, feedback generation, and OpenKB write steps.
- B log summaries store `player_text_preview`, not a full `player_text` field.
- Logger append failures are best-effort and must not change B branch, verdict,
  state delta, or OpenKB write behavior.

Verification commands for this update:

- `uv run pytest backend/tests/dev_b/test_developer_b_agent_run_log.py -q`
  reports `4 passed`.
- `uv run pytest backend/tests/test_unified_agent_run_log.py -q` reports
  `1 passed, 1 warning`.
- `uv run pytest backend/tests/dev_b/test_developer_b_policy_engine.py backend/tests/dev_b/test_developer_b_agent_run_log.py -q`
  reports `26 passed`.
- `uv run ruff check .` passes.
- `uv run mypy .` passes when run outside the sandbox because the sandboxed
  run cannot access the user-level uv cache.
- `uv run pytest -q` reports `62 passed, 2 warnings`.

# Developer B Objective UI Content Update - 2026-06-04

Developer B added `objective_kr` to Chapter 0 scenario node content and the
shared `NodeContext` schema as an optional field. The field is intended for
Korean Unreal UI objective display, for example `방문 목적 말하기` or `체류 기간
말하기`.

Scope:

- `backend/app/data/scenario_nodes.json` now defines `objective_kr` for every
  Chapter 0 immigration node.
- `backend/app/services/service_c/openkb_service.py` maps `objective_kr` into
  `NodeContext`.
- No `retry_question` or `retry_prompt_seed` field was added. Retry/clarify
  behavior continues to use `npc_question`, B feedback candidates, and Developer
  A dialogue generation.
- Developer C still needs to decide whether and where to expose `objective_kr`
  in the final Unreal response UI payload.

---

Current pre-prototype flow:

```text
Mock Unreal JSON or multipart sample wav
  -> Whisper-large-v3-turbo STT boundary (mock mode in tests, local mode in demo)
  -> Developer C Orchestrator
  -> Developer C OpenKB node_context from backend/app/data/scenario_nodes.json
  -> Developer C Understanding Agent
  -> Developer B Policy Adapter calling EnglishLevelHintAgent
  -> Developer A Dialogue/Voice Adapter calling voice output service
     (fake Kokoro by default, real Kokoro with MURPHY_TTS_MODE=real)
  -> Developer C Response Builder
  -> Developer C Validator
  -> Unreal-safe JSON with npc.audio_url
```

Canonical turn flow:

```text
Unreal wav
  -> Developer C local STT, with API fallback
  -> Developer C Orchestrator
  -> Developer C OpenKB node_context
  -> Developer C Understanding Agent
  -> Developer B Policy / Level / Hint / Feedback Adapter
  -> Developer C Orchestrator
  -> Developer A NPC Dialogue Adapter
  -> Developer C Response Builder
  -> Developer C Validator
  -> Unreal
```

## Contracts / Interfaces

Initial Phase 1 team guardrail, Developer C ownership, dependency, and change
request contracts exist under `docs/contracts/`. `AGENTS.md` now explains
Developer A, B, and C ownership boundaries. Developer A and B start prompts now
exist under `docs/prompts/`. Developer A and Developer B implementation packages
now live under their owner-specific `agent_a`/`service_a` and
`agent_b`/`service_b` folders; Developer C adapters remain the integration
boundary.

New Developer C contract docs:

- `docs/preprototype_status_demo_plan.md` summarizes the current phase status,
  AI-only pre-prototype architecture, target demo request/response plan,
  Developer A/B/C demo responsibilities, and demo readiness criteria.
- `docs/contracts/developer_c_schema_contract.md` defines
  `dev_c_unreal_turn.v1`, STT normalized input, OpenKB node context,
  Understanding output, Developer B policy input mapping, internal turn context,
  and `dev_c_unreal_response.v1`.
- `docs/contracts/developer_c_adapter_contracts.md` defines the STT, OpenKB,
  Understanding, Developer B policy, Developer B final feedback, Developer A
  dialogue, logging, response builder, and validator adapter boundaries.

The Developer B adapter now consumes the broader `dev_b_policy.v1` policy
contract, not only level/hint/branch fields.

Implemented C-owned modules:

- `backend/app/schemas/game_turn.py` contains the pre-prototype Pydantic
  schemas for mock Unreal input, STT normalized input, OpenKB node context,
  Understanding output, Developer A/B adapter payloads, and final response.
- `backend/app/services/service_c/stt_service.py` wraps the configured
  `whisper-large-v3-turbo` model name with real local Whisper transcription,
  OpenAI Transcriptions API fallback, and deterministic mock mode for tests.
- `backend/app/services/service_c/settings_service.py` centralizes `.env` and
  process environment configuration for C-owned runtime settings.
- `backend/app/services/service_c/orchestrator.py` wires STT, OpenKB,
  Understanding, Developer B, Developer A, logging, response building,
  validation, and C-owned unified AgentRun logging.
- `backend/app/middleware/middleware_c/developer_c_agent_run_middleware.py`
  builds the C orchestration AgentRun record and appends it through the shared
  `AgentRunLogStore`.
- `backend/app/services/service_c/validator.py` enforces minimal branch and response
  invariants.
- `backend/app/integrations/dev_b_level_hint_client.py` delegates C's
  `DevBPolicyInput` to Developer B's `EnglishLevelHintAgent`.
- `backend/app/integrations/dev_a_npc_dialogue_client.py` maps C turn context
  and validated B policy output into Developer A's level-design voice output
  service, then returns C-safe dialogue fields plus `audio_url`.
- `backend/app/main.py` serves generated demo wav artifacts from
  `/runtime/audio/...`, backed by `backend/runtime/generated/audio`.

## Dependency State

Package management uses `uv`. Python is set to 3.12. Required runtime and dev
dependencies are recorded in `pyproject.toml` and `uv.lock`, including
`langchain==1.3.2` and `langgraph==1.2.2`.

Local STT dependencies are optional:

```powershell
uv sync --extra local-stt
```

Runtime STT settings:

- `.env.example` is the committed settings template.
- `.env` is local-only and ignored by git.
- `MURPHY_STT_MODE=local` runs local Whisper first.
- `MURPHY_STT_MODE=mock` uses deterministic transcription for tests.
- `MURPHY_STT_LOCAL_MODEL=turbo` uses the local Whisper large-v3-turbo alias.
- `MURPHY_STT_API_MODEL=whisper-1` controls API fallback.
- `OPENAI_API_KEY` is required only if API fallback is needed.

Runtime TTS and NPC dialogue settings:

- `MURPHY_TTS_MODE=fake` keeps deterministic fake Kokoro wav output.
- `MURPHY_TTS_MODE=real` runs Developer A's real Kokoro provider and serves the
  generated wav under `/runtime/audio/...`.
- `MURPHY_NPC_DIALOGUE_MODE=rule` keeps deterministic Developer A dialogue.
- `MURPHY_NPC_DIALOGUE_MODE=llm` enables optional OpenAI NPC dialogue before
  Kokoro TTS and requires `OPENAI_API_KEY`.

Runtime Understanding settings:

- `MURPHY_UNDERSTANDING_MODE=rule` keeps deterministic semantic analysis.
- `MURPHY_UNDERSTANDING_MODE=llm` calls Developer C's OpenAI-backed semantic
  analyzer and falls back to rule mode when the LLM path is unavailable or
  unsafe.
- `MURPHY_UNDERSTANDING_LLM_MODEL=gpt-4o-mini` is the default model.
- `MURPHY_UNDERSTANDING_LLM_TIMEOUT_SECONDS=10` is the default timeout.
- Valid LLM responses can still be post-processed by Developer C when they miss
  a required allowed slot that deterministic evidence can safely recover. The
  current guard only repairs missing `visit_purpose` values such as
  `uncle -> family_visit` and writes the decision to
  `UnderstandingAgent.last_trace.postprocessing`.

Unified AgentRun logging:

- Developer C appends one record per orchestrated turn to
  `backend/runtime/generated/agent_runs/unified_agent_runs.jsonl` and
  `backend/runtime/generated/agent_runs/unified_agent_runs.md`.
- The C record uses `agent_name=ai_backend_orchestrator` and
  `owner=developer_c`.
- Timeline events cover STT, OpenKB, Understanding, Developer B, Developer A,
  response builder, validator, and error-capture boundaries.
- If Understanding LLM mode returns provider usage, the C record's `model`
  object now includes `input_tokens`, `output_tokens`, `total_tokens`, and
  `estimated_cost_usd`. The same summary is copied into the Understanding trace
  event. Developer A/B costs remain in their own AgentRun records.
- `metadata.data_flow` summarizes payload movement between services/agents.
  It intentionally stores compact summaries, not wav bytes, API keys, or full
  provider prompts.

## 2026-06-05 Final Result Score Policy Update

Implemented the remaining Developer B/C pre-prototype final score path.

Changed:

- Added B-owned `FinalResultScorePolicy` and B OpenKB final-result record
  reader under `backend/app/services/service_b/`.
- Added typed `FinalResult`, `FinalScoreState`, `QuantitativeScores`, and
  `UnrealResultResponse` schemas in the C-owned schema layer.
- `DevBPolicyClient.evaluate_turn(...)` now attaches B-scored
  `final_result` on final-branch outputs, and
  `DevBPolicyClient.final_result_for_session(session_id)` exposes the same B
  policy for result UI lookups.
- `/api/game/ai/respond` includes final score data under `report.final_result`
  when B returns it.
- Added `GET /api/game/ai/result/{session_id}` returning
  `dev_c_unreal_result.v1`.
- Developer C validator now checks `final_result.final_score_100`,
  `quantitative_scores.overall`, and `scoring_policy`.
- C-owned Developer A adapter normalizes leading `Alright` to `All right` and
  uses the final node's NPC line for final-branch candidate text.

Score policy:

- Per-turn `rubric_scores.total` is converted from 0-12 to 0-100.
- Chapter 0 v1 uses simple unweighted average.
- `IMM_007_FINAL_DECISION` is excluded from the average when prior scored
  records exist.
- feedback/error/focus-on-form records affect `reason_tags` and
  `report_summary`, not a separate numeric penalty.

Verification so far:

- `uv run pytest backend/tests/dev_b/test_final_result_score_policy.py backend/tests/test_final_result_payload.py backend/tests/test_preprototype_flow.py::test_orchestrator_connects_stt_understanding_dev_b_dev_a_and_response backend/tests/test_preprototype_flow.py::test_dev_a_adapter_uses_final_node_line_for_final_branch -q`
  passed with 9 tests and 2 warnings.
- `uv sync` passed after using the known uv cache escalation workaround.
- `uv run pytest -q` passed with 76 tests and 2 warnings.
- `uv run ruff check .` passed.
- `uv run mypy .` passed with no issues in 82 source files after using the
  known uv cache escalation workaround.

The sandboxed `uv sync`, `uv lock`, and `uv run ...` attempts can fail while
initializing the user-level uv cache. Rerunning with approved escalation is the
known workaround in this environment.

## Known Issues

The pre-prototype now wires merged Developer A/B packages through C adapters.
The automated path still uses deterministic STT and fake Kokoro TTS so it
passes without local model downloads, real API keys, Unreal Engine runtime, or
remote OpenKB. STT can execute real local Whisper in `local` mode, but the
first real local run needs `uv sync --extra local-stt`, `ffmpeg`, and time to
download/load the Whisper model. Real Kokoro can execute with
`MURPHY_TTS_MODE=real`, but the first run may download/load model assets and
can emit known torch/Kokoro warnings. Developer C Understanding is still a
deterministic prototype analyzer. The final score/result payload is implemented,
and Developer B has a directly tested Focus-on-Form practice-card report
builder, but C still needs to expose that report as optional out-game feedback.
Generated runtime artifacts for the integrated endpoint are written under
`backend/runtime/generated/` and ignored by git.

## Next Recommended Step

Next, run a live endpoint smoke test on the demo machine with
`MURPHY_STT_MODE=local` and `MURPHY_TTS_MODE=real`, then add API-level retry,
clarify, warning, and bad-end demo cases. After that, implement out-game
feedback/final report and prepare the real Unreal multipart bridge.

## 2026-06-08 Developer B IMMIGRATION_ALPHA Tier Policy Update

Developer B extended the current immigration prototype toward the Alpha
`IMMIGRATION_ALPHA` plan without editing Developer A or Developer C
implementation files.

Changed:

- Added a B-owned Gold-only immigration challenge node,
  `IMM_ALPHA_GOLD_BAG_CONTENT_CHECK`, to `backend/app/data/scenario_nodes.json`.
- Updated B-owned scenario policy so Gold players can route from
  `IMM_005_RETURN_TICKET` into the bag-content challenge when the return-ticket
  answer is strong and the node is allowed.
- Kept Bronze on the baseline immigration route and preserved rule-based branch
  authority.
- Added B-owned output self-checks before OpenKB writes for allowed next-node,
  hint payload, feedback payload, error capture, final-report seed, and rubric
  invariants.
- Added immigration-specific Focus-on-Form target names for final-report seeds,
  including `return_ticket_statement` and `bag_content_explanation`.
- Tightened optional LLM feedback handling so forbidden authority keys such as
  `branch`, `state_delta`, or `verdict` force rule fallback instead of being
  accepted as LLM feedback.
- Expanded `backend/tests/dev_b/test_developer_b_policy_engine.py` to cover
  Bronze baseline routing, Gold challenge routing, final-report seed behavior,
  Dev B output self-checks, and forbidden LLM fallback.

Verification so far:

- `uv run pytest backend/tests/dev_b/test_developer_b_policy_engine.py -q`
  passed with 29 tests.
- `uv run pytest backend/tests/dev_b -q` passed with 37 tests.
- `uv run pytest backend/tests/test_preprototype_flow.py backend/tests/test_final_result_payload.py backend/tests/test_demo_ai_respond_page.py -q`
  passed with 26 tests and 2 existing warnings.
- `uv run pytest -q` passed with 117 tests and 2 existing warnings.
- `uv run ruff check .` passed.
- `uv run mypy .` passed with no issues in 87 source files after using the
  known uv cache permission workaround.

## 2026-06-08 Developer B Direct Next Work Update

Developer B completed the next B-owned Alpha/Chapter 0 package without editing
Developer A or Developer C implementation files.

Changed:

- Expanded Chapter 0 policy tests to cover success and retry behavior across
  playable immigration nodes, the Gold challenge node, and new baggage nodes.
- Added `FocusOnFormReportPolicy` as a B-owned out-game report builder under
  `backend/app/services/service_b/`.
- Added static B-owned Focus-on-Form learning cards under
  `backend/app/kb/dev_b/focus_on_form_cards.json`.
- Added additive OpenKB v2 record metadata:
  `record_schema_version=dev_b_openkb_record.v2` and
  `record_kind=policy_turn_feedback`.
- Added B-owned `BAGGAGE_MISSING` node definitions:
  `BAG_002_FIND_STAFF` through `BAG_007_RESOLUTION`.
- Added baggage Focus-on-Form target mapping for problem statement, bag
  description, flight/tag statement, delivery request, and follow-up question.
- Preserved existing OpenKB record keys for compatibility.
- Added optional LLM usage capture in AgentRun feedback-generator event
  summaries without exposing usage on public `DevBPolicyOutput`.
- Kept forbidden LLM authority keys in fallback-only mode.
- Converted `backend/app/services/service_b/__init__.py` to lazy exports to
  avoid package import cycles while preserving exported service names.

Change requests:

- Added a C-owned request to expose optional Developer B Focus-on-Form report v1
  metadata through the final result response or a result detail endpoint.

Verification:

- `uv run pytest backend/tests/dev_b/test_focus_on_form_report_policy.py -q`
  passed with 5 tests.
- `uv run pytest backend/tests/dev_b/test_developer_b_policy_engine.py -q`
  passed with 63 tests.
- `uv run pytest backend/tests/dev_b/test_developer_b_agent_run_log.py -q`
  passed with 6 tests.
- `uv run pytest backend/tests/dev_b -q` passed with 78 tests.
- `uv run pytest backend/tests/test_preprototype_flow.py backend/tests/test_final_result_payload.py backend/tests/test_demo_ai_respond_page.py -q`
  passed with 26 tests and 2 existing warnings.
- `uv run pytest -q` passed with 158 tests and 2 existing warnings.
- `uv run ruff check .` passed.
- `uv run mypy .` passed with no issues in 89 source files after using the
  known uv cache permission workaround.

## 2026-06-09 Developer B Code Review and Remaining Alpha Plan Update

Developer B reviewed the current Dev B implementation and the 2026-06-08 plan
artifacts.

Dev B-owned fixes:

- `FocusOnFormReportPolicy` now treats
  `out_game_feedback_seed.include_in_final_report=false` as an explicit
  exclusion signal, even when legacy `focus_on_form_targets` are present.
- `FinalResultScorePolicy` now applies the same exclusion rule before adding
  `focus_on_form_recorded` reason tags or report-summary targets.
- Added regression tests for both exclusion paths.
- `backend/app/kb/dev_b/focus_on_form_cards.json` now covers every current
  Dev B Focus-on-Form target emitted by immigration, the Gold challenge, and
  baggage policy nodes.
- `backend/tests/dev_b/test_developer_b_policy_engine.py` now pins
  `DEV_B_FEEDBACK_LLM_MODE=rule` during tests so local `.env` values cannot
  accidentally send default policy tests through the external LLM path.

Cross-owner findings:

- Developer C rule-based `UnderstandingAgent` still handles the deterministic
  prototype mostly through visit-purpose classification. Alpha baggage and
  flight nodes need C-owned understanding coverage for their required slots, or
  an approved LLM-mode/runtime contract.
- Developer A/C dialogue integration currently looks up next-node questions
  only for `IMM_` node ids, so `BAG_` follow-up dialogue will not naturally
  advance in the integrated runtime until that adapter path is expanded.
- Developer C response/result surfaces return B `final_result`, but do not yet
  expose B `FocusOnFormReportPolicy.build_report(...)` as optional
  `out_game_feedback`.
- Alpha scene orchestration for
  `FLIGHT_001_SEATMATE_SMALLTALK -> IMMIGRATION_ALPHA -> BAGGAGE_MISSING`,
  cutscene transition, skip eligibility, and silent level carryover is not yet
  implemented in C-owned runtime code.
- Developer A still needs to consume B difficulty metadata for tier-aware NPC
  response speed/strictness and scene-specific roles such as friendly seatmate
  and baggage service staff.

Docs updated:

- `docs/contracts/change_requests.md` now marks older B integration requests as
  resolved or partially resolved and adds an open Alpha scene-flow request for
  A/C.
- `docs/portfolio_dev_b.md` now reflects that the C adapter delegates to the
  real B engine and that remaining work is Alpha scene/runtime exposure.

## 2026-06-09 Alpha Flow Planning Adjustment

Developer B updated the Alpha planning artifacts after the product direction
changed to include final scenario-end `evaluation` and `out_game_feedback`.

Planning changes:

- Final Alpha scoring should use `scene_normalized_dimension_average` rather
  than raw per-turn averaging, with default scene weights of flight 20%,
  immigration 50%, and baggage 30%.
- Flight small talk still produces a deferred `out_game_feedback_seed`, but the
  final report should frame it as a low-pressure calibration sample rather than
  a surprise grading event.
- Gold immigration strictness should prioritize missing facts, contradictions,
  evasive answers, and credibility risk over harmless grammar mistakes.
- Baggage missing should remain a practical service-desk problem-solving scene,
  not another high-pressure interview.
- Optional post-baggage events should be feature-gated, with at most one enabled
  for the first Alpha pass. Seatmate reunion is the recommended first candidate.

Updated docs:

- `docs/superpowers/plans/2026-06-09-dev-b-remaining-alpha-work.md`
- `docs/superpowers/plans/2026-06-08-alpha-flight-seatmate-smalltalk.md`
- `docs/superpowers/plans/2026-06-08-alpha-immigration.md`
- `docs/superpowers/plans/2026-06-08-alpha-baggage-missing.md`
- `docs/contracts/change_requests.md`

## 2026-06-09 Developer B Remaining Alpha Work Implementation

Developer B implemented the B-owned portions of
`docs/superpowers/plans/2026-06-09-dev-b-remaining-alpha-work.md` without
editing Developer A or Developer C runtime code.

Changed:

- Added `FlightSmallTalkDiagnosticPolicy` with minimum-turn, skip-eligibility,
  deferred-feedback, and fallback-question decisions.
- Added `FLIGHT_001_SEATMATE_SMALLTALK` to B-owned scenario node data.
- Updated `EnglishLevelHintAgent` so `FLIGHT_` nodes always create a deferred
  `out_game_feedback_seed` with `smalltalk_response_clarity`.
- Added a `smalltalk_response_clarity` static Focus-on-Form card.
- Updated `FinalResultScorePolicy` numeric computation to scene-normalized
  dimension averages with default Alpha weights: flight 20%, immigration 50%,
  and baggage 30%.
- Added `FocusOnFormReportPolicy.build_session_report(session_id)` for
  scenario-end `out_game_feedback` generation from local `dev_b` JSONL records.
- Added optional Alpha event seed documentation for customs declaration problem,
  stolen passport, and seatmate reunion.

Still C-owned:

- C-owned `QuantitativeScores.scoring_policy` and validator currently allow only
  `simple_average`. Developer B therefore keeps that field runtime-compatible
  while exposing the new policy through numeric behavior and
  `scene_normalized_dimension_average_policy` reason tags.
- C still needs to orchestrate
  `FLIGHT_001_SEATMATE_SMALLTALK -> IMMIGRATION_ALPHA -> BAGGAGE_MISSING ->
scenario_end` and expose final UI `evaluation` plus `out_game_feedback`.

## 2026-06-09 NPC Metadata Ownership Follow-Up

Developer B recorded the next contract-cleanup plan and cross-owner handoff for
removing B-authored NPC wording from the A-facing dialogue path.

Decision summary:

- Developer B must not author final NPC dialogue.
- Developer C should stop passing `node_context.npc_question` to Developer A as
  candidate dialogue.
- Developer C should stop deriving `in_game_feedback.npc_recast_line_candidate`
  from next-node `npc_question`.
- Developer B should not send `dialogue_directive.do_not_generate_npc_text` once
  C removes or relaxes the current schema field.
- `npc_speech_speed` and `question_complexity` should become 0-10 numeric
  metadata after C updates the schema.
- `hint_frequency` is cancelled as A-facing NPC-generation metadata and remains
  B-owned feedback policy only.
- `pressure_level` is cancelled as A-facing NPC-generation metadata and should
  be replaced by word-only `emotion_change`: `positive`, `neutral`, or
  `negative`.
- Runtime JSON should not include `_comment_*` keys. Value explanations belong
  in contract/plan tables.

Docs added or updated:

- `docs/superpowers/plans/2026-06-09-dev-b-npc-metadata-contract-cleanup.md`
- `docs/contracts/change_requests.md`

Ownership split:

- B-owned later work: update B difficulty/emotion policy output after C schema
  support is available.
- C-owned work: update schemas, validators, and the C-to-A adapter payload.
- A-owned work: generate final NPC utterances and TTS wording from metadata
  rather than polishing B/C-provided dialogue text.

## 2026-06-11 Developer B Report and Dialogue Seed Contract

Developer B added additive seed metadata for report assembly and A-facing
dialogue generation without expanding or reordering scenario nodes.

Changed implementation:

- Added optional `report_seed_summary` and `dialogue_seed` models to
  `backend/app/schemas/game_turn.py`.
- Updated `EnglishLevelHintAgent` to derive deterministic report seed metadata
  from existing evaluation, report item, error capture, Focus-on-Form targets,
  and level/tier data.
- Updated `EnglishLevelHintAgent` to emit `dialogue_seed` metadata containing
  scene, NPC role cue, goals, assessment targets, slots, difficulty cue,
  feedback focus, tone guidance, follow-up intents, and stop condition.
- Kept existing `dialogue_directive` for backward compatibility.
- Updated the Dev B OpenKB writer to store `report_seed_summary` and
  `dialogue_seed` in B-owned runtime records.
- Tightened LLM feedback guardrails so `npc_utterance`,
  `final_dialogue_line`, `npc_text`, `tts_text`, animation, and authority keys
  force fallback rather than changing policy output.

Contract/docs updated:

- Added `docs/contracts/developer_b_report_and_dialogue_seed_contract.md`.
- Updated `docs/contracts/developer_b_json_key_value_contract_v1.md`.
- Updated `docs/contracts/developer_b_json_final_v1.md`.
- Updated `docs/contracts/developer_c_adapter_contracts.md`.
- Updated `docs/contracts/developer_c_schema_contract.md`.

Tests added:

- Dev B output contains `report_seed_summary` fields for UI/report assembly.
- Dev B output contains `dialogue_seed` fields for Developer A generation.
- Dev B output does not contain final NPC utterance keys.
- OpenKB Dev B records include the new seeds.
- LLM-assisted feedback cannot return dialogue/final NPC text keys without
  falling back to rule output.

Verification:

- `uv sync` completed. It removed undeclared local package
  `en-core-web-sm==3.8.0` from the virtualenv because it is not part of the
  locked project dependency set.
- `uv run pytest` passed: 173 tests, 2 existing warnings.
- `uv run ruff check .` passed.
- `uv run mypy .` passed with no issues in 91 source files.

Known issues / coordination:

- This work does not expose `report_seed_summary` or `dialogue_seed` in the
  Unreal response envelope. Dev C or a future final report assembler should
  decide how to aggregate and present these seeds.
- This work does not remove existing legacy feedback candidate fields such as
  `npc_recast_line_candidate`, because doing so would be a breaking contract
  change. The new `dialogue_seed` is the preferred forward path for NPC
  generation metadata.
- Scenario node expansion, Chapter renaming, IMM node-id changes, and Alpha
  node reordering were intentionally not changed.

## 2026-06-11 Alpha Dev B Scenario Node Expansion

Developer B expanded B-owned Alpha scenario policy and node data. Developer A,
Developer C, and Unreal runtime code were not edited.

Changed implementation:

- Replaced the single flight diagnostic node with a five-turn Dev B node route:
  `FLIGHT_001_SEATMATE_SMALLTALK -> FLIGHT_002_TRAVEL_PURPOSE ->
FLIGHT_003_STAY_PLAN -> FLIGHT_004_CLARIFY_OR_ASK_BACK ->
FLIGHT_005_WRAP_UP`.
- Updated `FlightSmallTalkDiagnosticPolicy` to require 5 player turns and make
  skip eligibility available at 5 turns.
- Flight nodes now advance to the next evidence node even for retry, clarify,
  hint, warning, or bad-end branch candidates so small talk collects diagnostic
  samples instead of blocking progression.
- Added `BAG_001_NOTICE_BAG_MISSING` before the existing missing-bag service
  route.
- Routed `BAG_007_RESOLUTION` to `ALPHA_999_FINAL_SCOREBOARD`.
- Updated `ScenarioStateMachine` so `ALPHA_999_FINAL_SCOREBOARD` is the Dev B
  final-branch node. `IMM_007_FINAL_DECISION` now behaves as an
  immigration-clearance transition in B policy.
- Updated `FinalResultScorePolicy` to exclude both
  `IMM_007_FINAL_DECISION` and `ALPHA_999_FINAL_SCOREBOARD` when prior scored
  records exist.
- Flight `dialogue_seed.max_turns` now uses 5 turns.

Docs updated:

- `docs/contracts/developer_b_json_key_value_contract_v1.md`
- `docs/contracts/developer_b_report_and_dialogue_seed_contract.md`
- `docs/contracts/change_requests.md`

Tests added or updated:

- 5-turn flight diagnostic minimum and skip eligibility.
- Five-node flight route coverage.
- Baggage notice node and Alpha final scoreboard route coverage.
- Flight retry still advances to the next evidence node.
- `ALPHA_999_FINAL_SCOREBOARD` is the only Dev B final branch node.
- Alpha final-scoreboard records are excluded from scored averages when prior
  scored records exist.

Verification:

- `uv sync` completed.
- `uv run pytest` passed: 187 tests, 2 existing warnings.
- `uv run ruff check .` passed.
- `uv run mypy .` passed with no issues in 91 source files.

Known issues / coordination:

- Developer C-owned `DevBPolicyClient` still contains legacy final-result
  compatibility for `IMM_007_FINAL_DECISION`. A change request now asks C to
  adopt `ALPHA_999_FINAL_SCOREBOARD` as the Alpha final-result trigger.
- Developer A must generate actual NPC dialogue/TTS for the new `FLIGHT_*` and
  `BAG_001` metadata. Dev B still does not author final NPC utterances.
- Unreal must connect flight exit, airport arrival, baggage claim, final
  scoreboard, and ending cinematic flow states.
- The storyboard's baggage-open/random-item "억까" concept is left as future
  optional-event work; Alpha base route keeps the existing missing-bag flow.

## Resume Instructions

Run `uv sync` from the repository root, then run `uv run pytest`,
`uv run ruff check .`, and `uv run mypy .`. Continue from the integrated
pre-prototype flow unless a newer handoff entry supersedes this one.
