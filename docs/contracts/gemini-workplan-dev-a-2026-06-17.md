# Developer A 작업계획서 (Gemini 인계용) — 2026-06-17

> 본 문서는 Gemini CLI 가 그대로 읽고 실행할 수 있는 self-contained 작업계획서입니다.
> 작업 대상: Developer A 영역 단독. B/C 영역 파일은 절대 수정 금지.
> 가드레일: `AGENTS.md` 의 Developer A 소유 영역 (`backend/app/agents/agent_a/`, `backend/app/services/service_a/`, `backend/app/tools/tool_a/`, `backend/app/middleware/middleware_a/`, `backend/app/prompts/`) 만 편집.

---

## ⚠ Gemini 안전 작업 규칙 (반드시 준수)

직전 세션에서 batch write 도중 응답이 잘려 11개 파일이 동시에 truncate 된 사고가 있었습니다. 본 작업 진행 시 다음 규칙을 의무적으로 지켜주세요.

1. **한 번에 한 파일만 수정**. 여러 파일을 동시에 write 하지 마세요.
2. **모든 파일 write 직후 즉시 `python -m py_compile <편집한 파일>` 실행** 으로 자가 검증.
3. **응답 잘림 감지 시 그대로 채택하지 말고 재시도** — 응답 끝에 `<truncated>`, `... to be continued`, 미완성 코드 블록이 있으면 파일에 기록하지 말고 사용자에게 보고.
4. **편집 후 마지막 60자 확인** — 파일이 자연스럽게 종결되는지(`}`, `return`, 닫힌 docstring 등) 확인. 한 줄 중간이나 string 도중 EOF 면 truncation 발생.
5. **`git commit --no-verify` 사용 금지**.
6. 본 계획에 없는 파일은 절대 수정 금지. 가드레일 외 영역(B/C) 변경이 발견되면 사용자에게 보고 후 중단.

---

## 컨텍스트 — handoff/change_requests 진단 요약

handoff.md 와 docs/contracts/change_requests.md 확인 결과 A 측에 **2건 즉시 작업**, **2건 검증/갱신**이 남아있습니다.

| ID | 내용 | 상태 |
|---|---|---|
| ① | CR-2026-06-16 — Clean Developer A Ruff Unused Imports | 🔴 Open, A 단독 |
| ② | 신규 발견 — A 측 LLM 호출 시 ValueError → generic 폴백 (handoff 미기록) | 🔴 Open, A 단독 |
| ③ | Bad Ending end-to-end 검증 (B/C 모두 구현 완료, A 측 발화 표현 확인) | 🟡 검증 단계 |
| ④ | CR-2026-06-16 기내 스몰토크 대화형 전환 — A 측 작업 완료, CR Status 갱신만 남음 | 🟡 문서 갱신 |

---

## 작업 ① — Ruff Unused Imports 청소 (5~10분)

### 목적
C 가 incivility 스프린트 완료 후 full `uv run ruff check .` 가 A 영역 파일 2개의 unused import 때문에 막혀있음. C 가 "A 소유 implementation 파일은 silent 편집 안 함" 명시 → A 가 직접 정리.

### 대상 파일
- `backend/app/agents/agent_a/npc_dialogue_agent.py`
- `backend/app/services/service_a/tts_text_polisher_service.py`

### 작업 단계

```powershell
cd C:\5th_project\pj05_Murphy

# 1. 어떤 import가 unused 인지 확인 (F401 코드)
uv run ruff check backend\app\agents\agent_a\npc_dialogue_agent.py backend\app\services\service_a\tts_text_polisher_service.py --select F401

# 2. 출력된 라인 번호의 import 만 정확히 제거 (수기 편집)
#    ⚠ 다른 라인 건드리지 말 것. Gemini 가 본문을 다시 만들지 말 것.
#    Edit 도구로 정확한 라인만 삭제.

# 3. 자가 검증
python -m py_compile backend\app\agents\agent_a\npc_dialogue_agent.py
python -m py_compile backend\app\services\service_a\tts_text_polisher_service.py

# 4. 두 파일 마지막 60자 확인 (truncation 자가 점검)
Get-Content backend\app\agents\agent_a\npc_dialogue_agent.py -Tail 5
Get-Content backend\app\services\service_a\tts_text_polisher_service.py -Tail 5

# 5. 전체 ruff
uv run ruff check .
# → 0 errors 떠야 함

# 6. 전체 회귀
uv run pytest backend\tests -q
# → 296+ passed 떠야 함

# 7. mypy
uv run mypy .
```

### 수용 기준
- [ ] `uv run ruff check .` 0 errors
- [ ] `uv run pytest backend\tests -q` 그린
- [ ] `uv run mypy .` 그린
- [ ] 위 2개 파일 외 0 수정 (`git diff --stat` 으로 확인)

---

## 작업 ② — A 측 LLM ValueError 디버그 (10~30분)

### 목적
오늘 AgentRun 로그에서 "fuck you" 입력 시 다음 흐름이 확인됨:
```json
"llm": {"used": false, "fallback_used": true, "reason": "ValueError"}
"output_decision": {"npc_text_source": "developer_a_fallback"}
```
평상 응답 경로의 LLM 호출이 ValueError 로 실패 → `build_text_fallback` → "Okay. Please continue." 폴백. **어떤 ValueError 인지 traceback 이 안 찍힘**.

### 작업 단계

#### 2-1. except 블록에 traceback 로깅 추가 (1줄)

**파일:** `backend/app/agents/agent_a/npc_dialogue_agent.py`

`node_generate_dialogue_llm` 함수의 LLM 호출 try/except 블록을 찾아 except 처리에 traceback 출력 추가. 다음 grep 으로 위치 확인:
```powershell
Select-String -Path backend\app\agents\agent_a\npc_dialogue_agent.py -Pattern "except.*ValueError" -Context 2,5
```

해당 블록의 except 안에 다음 1줄 추가 (기존 return/error 처리 직전):
```python
except (NPCDialogueLLMUnavailable, httpx.HTTPError, json.JSONDecodeError, KeyError, ValueError) as exc:
    import logging, traceback
    logging.getLogger("backend.app.agents.agent_a").error(
        "LLM ValueError type=%s msg=%s\n%s",
        type(exc).__name__, exc, traceback.format_exc(),
    )
    return {"error": type(exc).__name__}
```

#### 2-2. 자가 검증

```powershell
python -m py_compile backend\app\agents\agent_a\npc_dialogue_agent.py
Get-Content backend\app\agents\agent_a\npc_dialogue_agent.py -Tail 5   # 마지막 종결 확인
```

#### 2-3. 운영 재현

```powershell
# 서버 재시작
uv run uvicorn backend.app.main:app --reload --port 8000
```

다른 창에서 `/respond-dialog` 로 다음 두 케이스:
1. 정상 답변 (예: `"Hi, nice to meet you."`)
2. `"fuck you"`

uvicorn 콘솔에 출력되는 traceback 의 origin 라인을 확인:
- Pydantic ValidationError → schemas.py 의 NPCDialogueLLMResult 검증 실패
- ValueError("invalid_llm_dialogue_language") 또는 ASCII 검증 실패
- profanity_lexicon 차단 → `profanity_lexicon_violation` 에러로 따로 분리되어야 함

#### 2-4. 원인 파악 후 후속 작업 결정

- 원인이 명백한 단일 버그 → 그 자리에서 수정
- 원인이 복잡한 정책 결정 사항 → 사용자에게 보고하고 별도 PR 로 분리

### 수용 기준
- [ ] uvicorn 콘솔에 ValueError 발생 시 traceback 출력 확인
- [ ] 정상 답변에서 LLM 정상 동작 확인 (text_length > 22, fallback_used=false)
- [ ] "fuck you" 케이스의 ValueError 원인 라인 식별 + 보고

---

## 작업 ③ — Bad Ending end-to-end 회귀 검증 (5~10분)

### 목적
handoff 확인 결과 B/C 측 CR-A1, A2, A3, A4 모두 구현 완료:
- C: `IncivilityClassification`, `incivility_classifier.py`, 어댑터 forward (06-16)
- B: Bad Ending 분기 정책 + 시나리오 노드 (06-16)
- C: `validate_dev_b_policy_tool` 의 bad_end 가드 통합 (06-17)

A 측 발화 표현이 적절한지 운영 회귀.

### 작업 단계

```powershell
# /respond-dialog 페이지
# 1. Immigration 시작 (NPC=hale)
# 2. "fuck you" 입력
# 3. 다음 항목 확인:
#    - response.next_node_id 가 IMM_BAD_END_VERBAL_ABUSE 또는 동등 노드로 라우팅
#    - response.npc_text 가 mirror 응답 (예: "Get the hell out of my line.")
#    - audio_url 로 voice 청취 (hale voice = dXtC3XhB9GtPusIpNtQx)
#    - debug.evaluation_verdict 가 FAIL 또는 bad_end 상태
```

### 검증 명령

```powershell
# AgentRun 로그 최신 jsonl
Get-ChildItem backend\runtime\generated\agent_runs -Filter *.jsonl -Recurse |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 1 |
  ForEach-Object {
    Get-Content $_.FullName -Tail 2 | ForEach-Object {
      $_ | ConvertFrom-Json | ConvertTo-Json -Depth 8
    }
  }
```

확인할 필드:
- `metadata.incivility.tier` >= 3 (C 가 잘 산출)
- `branch.branch_type` 가 `bad_end` 또는 동등
- `output_decision.npc_text_source` 가 `developer_a_fallback` 아닌 `llm_dialogue` 또는 mirror 응답 출처
- `npc_text` 가 평이한 "Okay. Please continue." 가 아닌 상태

### 시나리오별 기대값

| 시나리오 | 기대 |
|---|---|
| Flight smalltalk (`FLIGHT_A_001`) + "fuck you" | smalltalk_continue 통과 (의도된 동작), NPC 가 거칠지만 자연스러운 시트메이트 반응 |
| Immigration (`IMM_002_PURPOSE`) + "fuck you" | bad_end 분기, NPC 가 "Get the hell out..." 류 응답, BAD_END 노드 라우팅 |

### 수용 기준
- [ ] Immigration "fuck you" → bad_end 라우팅 ✅
- [ ] A 측 mirror 응답이 자연스럽게 합성됨
- [ ] AgentRun 로그에 `incivility.tier`, `branch_type` 정상 기록
- [ ] generic "Okay. Please continue." 폴백이 더 이상 안 나옴

---

## 작업 ④ — CR Status 갱신 (3~5분)

### 목적
handoff L142 (2026-06-17 Developer A 적응형 진단 연동 완료) 가 있는데 `docs/contracts/change_requests.md` 의 해당 CR Status 가 여전히 `Open`. A 측 작업 완료 사실을 CR 에 명시.

### 대상 파일
- `docs/contracts/change_requests.md`

### 작업 단계

`Change Request - 2026-06-16 - 기내 스몰토크 대화형 전환 (Flight Smalltalk Conversational Mode)` 섹션 (L1499) 의 첫 줄 직후에 다음 add:

```markdown
## Change Request - 2026-06-16 - 기내 스몰토크 대화형 전환 (Flight Smalltalk Conversational Mode)

Status: Resolved (Developer A update - 2026-06-17). Developer A 측 후속 작업
(스몰토크 페르소나 프롬프트, missing_followup_question 우회, SURFACE_GOAL_QUESTIONS
비활성화, recommended_expression 차단, 대화 메모리, generic 중립 폴백, Coherence Guard)
이 모두 구현 완료. 상세 내용은 handoff.md 2026-06-17 "Developer A 기내 스몰토크
적응형 진단(Adaptive Diagnostic) 연동 구현 완료" entry 참고. Developer C 측 후속
(off-topic 가드 씬 인지화, 슬롯 강제 추출 완화)은 별도로 처리됨.

Status: Open. Developer B 작업계획서(`docs/workplan-dev-b.md`) 기준. Dev B는
...
```

### 자가 검증
```powershell
# 변경된 줄만 확인
git diff docs\contracts\change_requests.md
```

### 수용 기준
- [ ] CR 제목 직후에 "Status: Resolved (Developer A update - 2026-06-17)" 추가
- [ ] handoff entry 위치 명시
- [ ] 기존 본문 내용 변경 없음

---

## 머지 전 종합 체크리스트

다음 모두 그린이어야 commit:

- [ ] `uv run ruff check .` 0 errors
- [ ] `uv run pytest backend\tests -q` 모두 그린
- [ ] `uv run mypy .` 0 errors
- [ ] 수정한 파일 마지막 60자 자연 종결 확인
- [ ] `git diff --stat` 결과가 다음 4개 외에 0:
  - `backend/app/agents/agent_a/npc_dialogue_agent.py` (작업 ①, ②)
  - `backend/app/services/service_a/tts_text_polisher_service.py` (작업 ①)
  - `docs/contracts/change_requests.md` (작업 ④)
- [ ] B/C 영역 파일 0 수정 (`git diff --stat | grep -E "(agent_b|agent_c|service_b|service_c|tool_b|tool_c|middleware_b|middleware_c|integrations|graphs|api|schemas)"` 결과 0)

---

## handoff entry 초안

작업 완료 후 `docs/handoff.md` 최상단에 다음 entry 추가:

```markdown
## 2026-06-17 Developer A: Ruff Cleanup + LLM Fallback Debug Logging + Smalltalk CR Status Sync

Developer A 는 handoff/change_requests 인벤토리 확인 후 다음 4가지 후속 작업을 완료했습니다.

Changed:

- **Ruff Unused Imports 청소 (CR-2026-06-16)**: `npc_dialogue_agent.py`, `tts_text_polisher_service.py` 의 unused import 제거. C 측에서 진단된 lint 차단 해소. full `uv run ruff check .` 그린.
- **LLM Fallback ValueError 디버그 로깅 추가**: `node_generate_dialogue_llm` 의 except 블록에 traceback 로깅 추가. 운영 환경에서 어떤 ValueError 가 발생하는지 즉시 식별 가능. [원인 후속 PR 별도]
- **Bad Ending end-to-end 회귀 청취 검증**: Immigration "fuck you" 시 bad_end 라우팅 + A 측 mirror 응답 동작 확인.
- **CR-2026-06-16 기내 스몰토크 대화형 전환 Status 갱신**: A 측 작업이 06-17 에 완료되었음을 change_requests.md 에 명시.

Verification:

- `uv run pytest backend/tests`: PASS
- `uv run ruff check .`: PASS
- `uv run mypy .`: PASS
- `/respond-dialog` Immigration 회귀 청취: PASS
```

---

## 참고

- 본 계획서가 가정하는 main 상태: `git log --oneline -1` → `0761086 Merge pull request #49 from PotenUP3-04-Synapse3/level_agent`
- 작업 분량: 총 ~25~50분
- 우선순위: ① → ② → ③ → ④ 순서
- 도구 사용 권장: Edit (line-by-line), Read (확인용). Write (전체 덮어쓰기) 는 본 계획에서 필요 없음.
