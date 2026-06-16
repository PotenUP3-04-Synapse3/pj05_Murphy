# Developer A 작업계획서 — NPC별 voice_id 라우팅 복구

> 작성일: 2026-06-16
> 작성자: Developer A / kimyonghee
> 소유 영역: `backend/app/services/service_a/`
> 관련 변경 요청: 후속으로 본 문서의 §5에 신규 등록 예정 (Developer A 단독 소유 영역이므로 cross-owner 변경 요청은 불필요할 가능성 높음)

---

## 1. 요약

`npc_roster_service._NPC_ROSTER` 에는 NPC별 `elevenlabs_voice_id` 가 정확히 정의되어 있으나(arabella=Z3R5..., hale=dXtC..., brielle=6u6J... 등), **세 군데 코드 결함이 누적되어 모든 NPC가 항상 `.env`에 박힌 단일 voice 로 합성**되고 있습니다.

| # | 위치 | 결함 | 결과 |
|---|---|---|---|
| 버그 A | `voice_output_service.py:430,452` | `_env_value(key, voice_id or ...)` → env가 항상 우선, NPC voice는 fallback | `.env` 두 줄이 모든 NPC voice를 덮어씀 |
| 버그 B | `voice_profile_service.py:32-38` | `NPCProfile.elevenlabs_voice_id` 를 읽지 않음. ElevenLabs voice 매핑 경로 부재 | ElevenLabs 호출에도 Edge voice 문자열(`en-US-GuyNeural`)이 전달됨 |
| 버그 C | `voice_profile_service.py:36` | `provider="edge"` 하드코딩 | TTS provider 메타데이터 항상 `edge`, 로그/디버그 추적 어긋남 |

본 계획서는 세 결함을 한 번에 정리해 **per-NPC voice 라우팅이 ElevenLabs/Edge 양 경로 모두에서 정상 작동**하도록 복구합니다. 전부 Developer A 소유 영역이라 cross-owner 변경 요청 없이 진행할 수 있습니다.

---

## 2. 상세 분석

### 2-1. 현재 데이터 흐름 (버그 상태)

```
npc_roster_service._NPC_ROSTER  ← elevenlabs_voice_id 정확히 정의되어 있음
        │
        ▼
voice_profile_service.resolve_voice_profile(user_id, npc_id)
        │  ┌─────────────────────────────────┐
        │  │ VoiceProfile(                   │
        │  │   provider="edge",         ◀────┼── 버그 C: 하드코딩
        │  │   voice_id=_NPC_EDGE_VOICES… ◀──┼── 버그 B: ElevenLabs 매핑 누락
        │  │ )                               │
        │  └─────────────────────────────────┘
        ▼
voice_output_service._build_provider_request(provider_name, ..., voice_id=voice_profile.voice_id)
        │  if provider_name == "elevenlabs":
        │      voice_id=_env_value(            ◀── 버그 A: env 우선, NPC fallback
        │          "MURPHY_ELEVENLABS_VOICE_ID",
        │          voice_id or "CwhRBWXzGAHq8TQ4Fs17",
        │      )
        ▼
ElevenLabs API → 모든 NPC가 동일 voice
```

### 2-2. 버그 A — `_env_value` 우선순위 역전

**파일:** `backend/app/services/service_a/voice_output_service.py`

```python
# L430 (ElevenLabs)
voice_id=_env_value("MURPHY_ELEVENLABS_VOICE_ID", voice_id or "CwhRBWXzGAHq8TQ4Fs17"),

# L452 (Edge)
edge_voice=_env_value("MURPHY_EDGE_TTS_VOICE",  voice_id or "en-US-GuyNeural"),
```

`_env_value(key, default)` 정의:
```python
def _env_value(key: str, default: str) -> str:
    return os.getenv(key) or _read_env_file(Path(".env")).get(key, default)
```

`.env` 현재 내용:
```
MURPHY_EDGE_TTS_VOICE=en-US-GuyNeural
MURPHY_ELEVENLABS_VOICE_ID=CwhRBWXzGAHq8TQ4Fs17
```

→ env에 값이 있으므로 `voice_id` 인자는 **never used**. 모든 NPC 동일 voice.

### 2-3. 버그 B — ElevenLabs voice_id 가 NPC별로 라우팅되지 못함

**파일:** `backend/app/services/service_a/voice_profile_service.py`

```python
_NPC_EDGE_VOICES: dict[str, str] = {
    "arabella": "en-US-AvaNeural",
    "novak": "en-US-BrianNeural",
    "hale": "en-US-GuyNeural",
    ...
}

def resolve_voice_profile(user_id: str, npc_id: str) -> VoiceProfile:
    npc_profile = resolve_npc_profile(npc_id)
    return VoiceProfile(
        ...
        provider="edge",                                              # ← 항상 edge
        voice_id=_NPC_EDGE_VOICES.get(npc_profile.npc_id, "en-US-GuyNeural"),
        #          ↑ Edge voice만 매핑. npc_profile.elevenlabs_voice_id 무시.
    )
```

문제점:
- `NPCProfile.elevenlabs_voice_id` 필드(예: `Z3R5wn05IrDiVCyEkUrK`)가 **roster에 정의만 되고 어디서도 읽히지 않음**. dead field.
- ElevenLabs 호출 시에도 `voice_profile.voice_id` 가 `"en-US-AvaNeural"` 같은 Edge voice 문자열이라 ElevenLabs API가 해석할 수 없음.
- 설사 버그 A를 고쳐 `voice_id or default` 가 첫 우선이 되어도, 그 `voice_id` 가 이미 Edge voice 문자열이라 ElevenLabs voice가 들어가지 않음.

### 2-4. 버그 C — `provider` 하드코딩

같은 파일 L36. `provider="edge"` 가 고정이라 ElevenLabs 사용 시에도 VoiceProfile.provider 는 `"edge"` 가 들어감. AgentRun 로그/디버그 추적이 어긋남.

### 2-5. 현재 동작 검증 시나리오

| 시나리오 | 호출 | 기대 voice | 실제 voice (현재) |
|---|---|---|---|
| Edge + `.env` 미설정 + npc=arabella | `MURPHY_EDGE_TTS_VOICE` 없음 | `en-US-AvaNeural` | `en-US-AvaNeural` ✅ |
| Edge + `.env`에 GuyNeural 설정 + npc=arabella | `MURPHY_EDGE_TTS_VOICE=en-US-GuyNeural` | `en-US-AvaNeural` | `en-US-GuyNeural` ❌ |
| ElevenLabs + `.env` 미설정 + npc=arabella | 없음 | `Z3R5wn05IrDiVCyEkUrK` | `en-US-AvaNeural` ❌ (Edge voice가 흘러감) |
| ElevenLabs + `.env`에 hale 설정 + npc=arabella | `MURPHY_ELEVENLABS_VOICE_ID=CwhRBWXzGAHq8TQ4Fs17` | `Z3R5wn05IrDiVCyEkUrK` | `CwhRBWXzGAHq8TQ4Fs17` ❌ |

3/4 시나리오가 깨져 있음. 현재 운영 형태(`.env`에 두 값 모두 박혀 있음)에서는 **사실상 100% 단일 voice**.

---

## 3. 목표 동작 (정합된 라우팅)

**원칙:**
1. 우선순위는 **`NPCProfile` > `.env` > 하드코딩 디폴트** 순. `.env`는 NPC가 미등록일 때만 fallback 으로 작동.
2. ElevenLabs 사용 시 `NPCProfile.elevenlabs_voice_id` 를 정식으로 사용.
3. Edge 사용 시 `_NPC_EDGE_VOICES` 또는 신설된 `NPCProfile.edge_voice_id` (선택) 사용.
4. `VoiceProfile.provider` 는 실제 사용될 TTS 엔진을 반영.
5. `.env` 오버라이드는 운영 중 일시적 강제 변경에만 사용 — **per-NPC 라우팅을 무력화하지 않음**. 명시적 토글(`MURPHY_TTS_FORCE_VOICE_OVERRIDE=true`) 이 활성화된 경우에만 env가 우선되도록 명확하게 분리.

**수정 후 데이터 흐름:**

```
npc_roster_service._NPC_ROSTER
  + elevenlabs_voice_id  ← 그대로 유지
  + edge_voice_id        ← 신설 (또는 _NPC_EDGE_VOICES 유지 후 _resolve_edge_voice 헬퍼 경유)
        │
        ▼
voice_profile_service.resolve_voice_profile(user_id, npc_id, *, tts_provider)
        │  VoiceProfile(
        │    provider=tts_provider,      ◀── 호출자에서 받은 실제 엔진 반영
        │    voice_id=
        │      elevenlabs_voice_id  if provider=="elevenlabs"
        │      else edge_voice_id,
        │  )
        ▼
voice_output_service._build_provider_request(provider_name, ..., voice_id=voice_profile.voice_id)
        │  if provider_name == "elevenlabs":
        │      voice_id = (
        │          os.getenv("MURPHY_ELEVENLABS_VOICE_ID_FORCE") or  # 명시적 강제 override만
        │          voice_id or                                        # NPC voice 우선
        │          "CwhRBWXzGAHq8TQ4Fs17"                             # 최종 안전망
        │      )
```

---

## 4. 작업 계획 (Phased)

### Phase A — `VoiceProfile` 확장 + provider 인자화 + ElevenLabs voice 매핑 (1.0d)

**대상 파일:** `backend/app/services/service_a/voice_profile_service.py`

1. `_NPC_EDGE_VOICES` 사전은 유지 (Edge 매핑). ElevenLabs 매핑은 `NPCProfile.elevenlabs_voice_id` 를 직접 사용.
2. `resolve_voice_profile` 시그니처 확장:
   ```python
   def resolve_voice_profile(
       user_id: str,
       npc_id: str,
       *,
       tts_provider: str = "edge",
   ) -> VoiceProfile:
       safe_user_id = user_id or "user_unknown"
       npc_profile = resolve_npc_profile(npc_id)

       if tts_provider == "elevenlabs":
           voice_id = npc_profile.elevenlabs_voice_id or "CwhRBWXzGAHq8TQ4Fs17"
       else:
           voice_id = _NPC_EDGE_VOICES.get(npc_profile.npc_id, "en-US-GuyNeural")

       return VoiceProfile(
           user_id=safe_user_id,
           npc_id=npc_profile.npc_id,
           voice_profile_id=f"{safe_user_id}:{npc_profile.npc_id}:{tts_provider}",
           provider=tts_provider,
           voice_id=voice_id,
       )
   ```
3. `voice_profile_id` 에 provider 를 포함해 같은 NPC 라도 엔진별로 캐시 키가 갈리도록 함 (audio cache key 충돌 방지).
4. `VoiceProfile` 에 추가 필드 도입 검토 — 일단 본 Phase에서는 `voice_id` 만 분기.

### Phase B — 호출자(`voice_output_service`) 정렬 (0.5d)

**대상 파일:** `backend/app/services/service_a/voice_output_service.py`

1. `_selected_tts_provider(...)` 결과를 먼저 결정한 뒤 `resolve_voice_profile(..., tts_provider=tts_provider_name)` 으로 호출하도록 순서 변경.
2. `_build_provider_request` 의 env 우선순위 역전 해소:
   ```python
   # before
   voice_id=_env_value("MURPHY_ELEVENLABS_VOICE_ID", voice_id or "CwhRBWXzGAHq8TQ4Fs17"),
   edge_voice=_env_value("MURPHY_EDGE_TTS_VOICE",  voice_id or "en-US-GuyNeural"),

   # after
   voice_id=_per_npc_voice_or_override(
       npc_voice=voice_id,
       force_env_key="MURPHY_ELEVENLABS_VOICE_ID_FORCE",
       fallback="CwhRBWXzGAHq8TQ4Fs17",
   ),
   edge_voice=_per_npc_voice_or_override(
       npc_voice=voice_id,
       force_env_key="MURPHY_EDGE_TTS_VOICE_FORCE",
       fallback="en-US-GuyNeural",
   ),
   ```
3. 신규 헬퍼:
   ```python
   def _per_npc_voice_or_override(*, npc_voice: str, force_env_key: str, fallback: str) -> str:
       """
       per-NPC voice 가 기본 우선.
       명시적 환경변수(`*_FORCE`)가 설정된 경우에만 운영 강제 override.
       """
       forced = os.getenv(force_env_key) or _read_env_file(Path(".env")).get(force_env_key, "")
       if forced:
           return forced
       return npc_voice or fallback
   ```
4. 기존 `MURPHY_ELEVENLABS_VOICE_ID` / `MURPHY_EDGE_TTS_VOICE` 키는 **deprecated** 표시. `.env.example` 에서 주석으로 안내:
   ```bash
   # DEPRECATED: 모든 NPC를 단일 voice로 강제하던 옛 변수.
   # 이제 voice는 npc_roster_service 의 elevenlabs_voice_id / _NPC_EDGE_VOICES 로 결정됩니다.
   # 운영 중 일시 강제 override가 필요하면 *_FORCE 변수를 사용하세요.
   # MURPHY_ELEVENLABS_VOICE_ID=CwhRBWXzGAHq8TQ4Fs17
   # MURPHY_EDGE_TTS_VOICE=en-US-GuyNeural

   # MURPHY_ELEVENLABS_VOICE_ID_FORCE=
   # MURPHY_EDGE_TTS_VOICE_FORCE=
   ```
5. 호환성을 위해 한 마이너 버전 동안은 옛 키도 읽되 **DeprecationWarning** 로깅 후 NPC voice 보다 낮은 우선순위로 강등.

### Phase C — 캐시 키/메타 검증 (0.5d)

1. `audio_storage_service.build_audio_cache_key` 가 voice id 를 키에 포함하는지 확인. 포함되어 있어야 NPC별로 캐시 파일이 분리됨. 누락 시 voice id 를 키 구성에 추가.
2. `_provider_cache_model_version` 의 ElevenLabs 분기에 voice 가 포함되는지 확인. 누락 시 추가.
3. AgentRun 로그 (`evidence_metadata` / `_tts_summary`) 에 `voice_id` 와 `provider` 가 NPC 별로 다르게 찍히는지 회귀.

### Phase D — 테스트 (1.0d)

1. **신규 단위 테스트** `backend/tests/test_developer_a_voice_profile_routing.py`:
   - `resolve_voice_profile("u", "arabella", tts_provider="elevenlabs")` → `voice_id == "Z3R5wn05IrDiVCyEkUrK"`, `provider == "elevenlabs"`.
   - 같은 NPC, Edge → `voice_id == "en-US-AvaNeural"`, `provider == "edge"`.
   - 미등록 NPC + ElevenLabs → fallback `CwhRBWXzGAHq8TQ4Fs17`.
2. **기존 테스트 갱신** `test_developer_a_npc_roster.py`, `test_developer_a_agent_run_logging.py`:
   - voice_id 단언문이 NPC별 voice 를 기대하도록 갱신.
   - `provider` 가 `"edge"` 고정이 아니라 시나리오에 따라 다르게 들어가는지 검증.
3. **통합 회귀 매트릭스**:
   | provider | NPC | env override | 기대 voice |
   |---|---|---|---|
   | edge | arabella | 없음 | en-US-AvaNeural |
   | edge | hale | 없음 | en-US-GuyNeural |
   | edge | arabella | `_FORCE` 설정 | env 값 |
   | elevenlabs | arabella | 없음 | Z3R5wn05IrDiVCyEkUrK |
   | elevenlabs | hale | 없음 | dXtC3XhB9GtPusIpNtQx |
   | elevenlabs | unknown_npc | 없음 | fallback |
4. **수동 회귀**: `/respond-dialog` Flight(arabella) + Immigration(hale) + Baggage(brielle) 1회씩 합성 후 ElevenLabs 대시보드/audio 파일 voice 매핑 확인.

### Phase E — 정리 / 문서화 (0.5d)

1. `npc_roster_service.NPCProfile` 의 `elevenlabs_voice_id` 가 더 이상 dead field 가 아님을 docstring 명시.
2. `docs/handoff.md` 에 본 PR 결과 기재.
3. `.env.example` 정리 (Phase B step 4).
4. `agent_a_structure.md` 의 service_a 섹션에 `resolve_voice_profile(provider 인자화)` 변경 반영.

---

## 5. 일정 / 의존성

| Phase | 산출물 | 공수 |
|---|---|---|
| A. `resolve_voice_profile` 확장 + ElevenLabs 매핑 | voice_profile_service.py | 1.0d |
| B. 호출자 정렬 + env 우선순위 정정 | voice_output_service.py, .env.example | 0.5d |
| C. 캐시 키/메타 검증 | audio_storage_service.py 점검 | 0.5d |
| D. 테스트 | test_developer_a_voice_profile_routing.py 신설 + 기존 갱신 | 1.0d |
| E. 정리/문서화 | handoff.md, agent_a_structure.md, .env.example | 0.5d |
| **합계** | | **~3.5d** |

P0(Dialogue Agent 품질) 다음 또는 병행으로 진행 가능. P1 (Alpha NPC 라인업) 의 voice 검증 단계와 직접 맞물리므로 P1 시작 전에 본 작업이 머지되는 것이 가장 효율적입니다.

---

## 6. 위험 요소 및 완화

| 위험 | 영향 | 완화 |
|---|---|---|
| 기존 `MURPHY_ELEVENLABS_VOICE_ID` / `MURPHY_EDGE_TTS_VOICE` 사용처가 운영 환경에 있을 가능성 | 사일런트 voice 변경 | Phase B-5: 옛 키는 DeprecationWarning 로깅 후 한 마이너 버전 유예. handoff에 명시. |
| `voice_profile_id` 에 provider 가 포함되면서 audio cache 가 무효화됨 | 첫 호출 시 모든 NPC 신규 합성 | 의도된 동작. 캐시 디스크 사용량 일시 증가 가능 — 운영 알림. |
| `NPCProfile.elevenlabs_voice_id == None` 인 NPC | 일부 NPC ElevenLabs 호출 시 fallback voice | Phase A 도입 시 roster 전수 점검. 누락 NPC 보충하거나 안전한 fallback 명시. |
| `voice_profile_service.resolve_voice_profile` 시그니처 변경으로 외부 호출자 깨짐 | import 실패 | 호출처는 `voice_output_service` 1곳만 확인됨 (Developer A 영역). C-side import 없음을 grep 으로 사전 검증. |
| ElevenLabs voice ID가 dashboard 에서 폐기되었을 가능성 | 합성 실패 | Phase D 수동 회귀로 사전 검증. 실패 시 roster 의 elevenlabs_voice_id 보정 PR 분리. |

---

## 7. PR 머지 체크리스트

- [ ] `grep -rn "_NPC_EDGE_VOICES\|elevenlabs_voice_id" backend/app/services/service_a` 로 매핑 경로가 1곳에서 단일 책임으로 정리됨을 확인
- [ ] `grep -rn "_env_value(\"MURPHY_ELEVENLABS_VOICE_ID\"\|_env_value(\"MURPHY_EDGE_TTS_VOICE\"" backend/app/services/service_a` → 0건 (deprecated 키 직접 사용 제거)
- [ ] `uv run pytest backend/tests/test_developer_a_voice_profile_routing.py` 그린
- [ ] `uv run pytest` 그린, ruff/mypy 그린
- [ ] `.env` 의 옛 키 두 줄을 빈 값으로 두고 `/respond-dialog` 회귀 시 arabella/hale/brielle voice 가 다르게 들림
- [ ] B/C 영역 파일 0 변경 (가드레일)
- [ ] `docs/handoff.md` 에 변경 기록 + `docs/contracts/change_requests.md` 는 신규 등록 불필요 (A 단독)

---

## 8. 후속 (별도 RFC)

1. **`NPCProfile.edge_voice_id` 필드 도입**: 현재 Edge voice 매핑이 `_NPC_EDGE_VOICES` 라는 별도 dict 에 분리되어 있어 한 NPC 의 voice 정의가 두 곳에 흩어짐. roster 단일 소스로 통합하면 가독성/유지보수 향상.
2. **`tts_provider` 를 RunnableConfig.configurable 로 흘려보내기**: LangChain 1.0+ DI 표준에 정렬해 `voice_output_service` 내 분기 단순화.
3. **per-NPC ElevenLabs voice 보정값**(stability/style/speed/similarity_boost) 도 roster 의 NPC 정의에 함께 두기. 현재는 emotion 단위로만 매핑되어 NPC 페르소나가 음향에 직접 반영되지 않음.
