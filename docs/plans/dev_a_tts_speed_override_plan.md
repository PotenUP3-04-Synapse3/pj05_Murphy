# Developer A — TTS 발화 속도 통일 (옵션 A: 환경변수 override) 작업계획서

작성일: 2026-06-21
대상 실행 에이전트: **Gemini (Developer A 페르소나)** 또는 사용자 직접
관련 코드: `backend/app/services/service_a/voice_output_service.py` (이미 구현됨,
변경 없음)

본 계획서는 **코드 변경 없이 `.env` 환경변수만 추가**하여 TTS 속도를 통일하는
가장 가벼운 작업이다. 영구 조정(옵션 B/C)은 별도 계획서에서 다룬다.

---

## 0. 작업 가드레일

### 0.1 수정 가능 파일
- `.env` (사용자 로컬, git 추적 제외 권장)
- `.env.example` (선택. 팀원 참고용)
- 본 계획서 (`docs/plans/dev_a_tts_speed_override_plan.md`)
- `docs/handoff.md` (Developer A 섹션 한 줄 append)

### 0.2 수정 금지 파일
- 코드는 일체 변경 없음. `voice_output_service.py`, 프롬프트, few-shot, 페르소나
  로스터, 테스트 모두 그대로.
- 옵션 A의 핵심은 "기존 코드에 이미 구현된 env override 경로를 활용한다"이다.
  (`voice_output_service.py:459` `_env_float("MURPHY_ELEVENLABS_SPEED", ...)`)

---

## 1. 배경

현재 TTS 속도 결정 흐름:

```
[1] MURPHY_ELEVENLABS_SPEED env  ←── 있으면 무조건 우선 (옵션 A가 여기에 값 주입)
        │ (없으면)
        ▼
[2] LLM이 출력한 speed 값 (0.5~2.0)
[3] EMOTION_TTS_PARAMETERS 감정별 기본
[4] _elevenlabs_speed_for_tone(tone) 톤별 기본
[5] incivility bias (+0.05 × tier)
```

문제: LLM이 few-shot 예시(1.0~1.15)를 본받아 동적 speed를 1.0 이상으로 자주
출력 → 전체 발화가 빠르게 들림. EMOTION_TTS_PARAMETERS 기본값(normal 0.86)이
적용될 기회가 없음.

옵션 A의 효과: 환경변수가 LLM 결정과 감정/톤 매핑을 **전부 override** 하여
모든 NPC가 같은 속도로 발화. 청취 균일성 확보, 체감 속도 즉시 통제.

---

## 2. 작업 항목

### S-1. .env에 환경변수 추가
**파일:** `C:\5th_project\pj05_Murphy\.env`

기존 ElevenLabs 설정 블록 근처에 한 줄 추가:

```
MURPHY_ELEVENLABS_SPEED=0.82
```

권장 시작값은 0.82. (현재 normal 톤 기본값 0.86보다 약간 느림)

### S-2. (선택) .env.example 갱신
**파일:** `C:\5th_project\pj05_Murphy\.env.example`

팀원이 같은 환경을 재현할 수 있도록 한 줄 주석과 함께 추가:

```
# NPC TTS 발화 속도 통일 override. 미지정 시 LLM/감정/톤 매핑이 동적 결정.
# 권장 범위 0.78 ~ 0.92. 1.0은 ElevenLabs 기본 속도.
MURPHY_ELEVENLABS_SPEED=0.82
```

### S-3. 서버 재시작 후 검증
1. uvicorn 재시작:
   ```powershell
   uv run uvicorn backend.app.main:app --reload
   ```
2. `http://localhost:8000/respond-dialog`에서 두 NPC 이상으로 같은 시나리오
   테스트 (예: Arabella seatmate / Officer Hale immigration).
3. 두 NPC 모두 같은 속도로 발화하는지 청취 확인.

### S-4. 속도 튜닝 (필요 시)
청취 후 마음에 들지 않으면 다음 표를 참고해 값 조정 후 재시작.

| 값 | 체감 | 사용 케이스 |
|---|---|---|
| 0.75 | 느린 편 | 학습자에게 천천히 말해야 하는 초급 모드 |
| 0.78 | 다소 느림 | 명료한 발음 우선 |
| **0.82** (권장 기본) | 자연스러움 + 학습자 친화 | **첫 시도 권장값** |
| 0.86 | EMOTION_TTS normal 기본값 | 현재 정적 매핑 그대로 |
| 0.90 | 살짝 빠른 자연 속도 | 캐주얼 톤 강조 |
| 0.95 | 빠른 편 | 긴급/긴장 연출 |

서버 재시작이 매번 필요. .env 변경은 핫리로드 안 됨.

### S-5. 영구 적용 시점이 오면 옵션 B/C로 전환
환경변수로 만족스러운 값을 찾고 1~2주 운영해본 뒤, 영구 반영하려면 별도
계획서로 진행:

- **옵션 B**: `EMOTION_TTS_PARAMETERS`의 모든 speed 값을 새 기준으로 전체 하향
- **옵션 C**: `npc_dialogue_prompt.md` + few-shot speed 값 가이드 강화

옵션 A는 영구 적용까지의 임시 운영 단계로 보면 된다. 영구 적용 후엔 환경변수를
제거해도 무방.

### S-6. handoff.md 한 줄 기록
**파일:** `docs/handoff.md`

Developer A 섹션 맨 아래에 한 줄 append:

```
## 2026-06-21 Developer A: TTS 발화 속도 통일 (env override)
- .env에 MURPHY_ELEVENLABS_SPEED=0.82 추가하여 모든 NPC 발화 속도 통일.
- 코드 변경 없음. voice_output_service.py:459의 기존 _env_float 경로 활용.
- 영구 적용 시 EMOTION_TTS_PARAMETERS 하향(옵션 B) 또는 프롬프트 가이드(옵션 C)로 전환 예정.
```

---

## 3. 검증 체크리스트

- [x] `.env`에 `MURPHY_ELEVENLABS_SPEED=0.82` 한 줄 추가됨.
- [ ] uvicorn 재시작 후 같은 시나리오에서 모든 NPC가 동일 속도로 발화.
- [ ] 다른 NPC(seatmate / officer / baggage / customs) 최소 2종 청취 확인.
- [x] `uv run pytest`는 영향 없음 (테스트는 가짜 voice를 쓰므로 env 무관).
- [x] `docs/handoff.md`에 한 줄 기록.

---

## 4. 영향 분석

| 영역 | 영향 |
|---|---|
| LLM 호출 비용 | 영향 없음 (LLM speed 출력은 사용 안 되지만 호출은 그대로) |
| TTS 합성 비용 | ElevenLabs는 speed 값에 비용 변동 없음 |
| 응답 지연 | 무시 가능 (env 읽기 1회) |
| 다른 개발자 | 영향 없음 (A 영역만, 환경변수만) |
| 회귀 위험 | 매우 낮음 (코드 변경 0) |
| 롤백 | `.env`에서 한 줄 제거 + 재시작 (10초) |

---

## 5. 후속 / 옵션 B·C 진행 시 참고

본 작업으로 만족스러운 속도를 찾으면, 영구 반영을 위한 옵션 B/C 작업계획서를
별도로 작성한다.

- **옵션 B 핵심**: `voice_output_service.py:51-65` EMOTION_TTS_PARAMETERS의
  speed(세 번째 값) 전부 하향. 감정 간 상대 속도 비율은 유지.
- **옵션 C 핵심**: 프롬프트에 "default speed 0.80-0.90 권장" 가이드 + few-shot
  예시 speed 하향.

옵션 B는 LLM 동적 결정이 발동하면 무력해질 수 있으므로 옵션 C와 묶어 진행
권장. 옵션 A → (1~2주 청취) → 옵션 B+C 동시 적용 → 옵션 A 환경변수 제거 순서가
가장 안전.
