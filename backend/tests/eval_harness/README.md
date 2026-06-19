# Developer A - 평가 하네스 (Evaluation Harness) 사용 가이드

본 평가는 NPC 페르소나(Persona) 지침 보강, 스몰토크(Smalltalk) 토픽 관리 기법의 변경 사항이 미치는 영향을 객관적인 점수(Pass Rate)로 측정하기 위한 검증 인프라(Infrastructure)입니다.

---

## 1. 실행 방법

기본적으로 실제 OpenAI API 키(Key) 없이도 결정형(Deterministic) 채점을 수행하도록 동작합니다. CI/CD 환경이나 로컬 환경에서 다음과 같이 구동할 수 있습니다.

```powershell
# 전체 테스트 실행 시 자동으로 스모크 테스트 포함
uv run pytest backend/tests/test_eval_harness_smoke.py -s
```
`-s` 플래그를 붙이면 콘솔에 요약된 리포트(Report Summary) 테이블이 직접 출력됩니다.

---

## 2. 시나리오 추가 방법

`backend/tests/eval_harness/scenarios/` 디렉토리 아래에 존재하는 적합한 YAML 파일에 새로운 테스트 항목을 추가할 수 있습니다. 

### 시나리오 YAML 스키마(Schema) 구조:
```yaml
- id: flight_a001_arabella_custom_case
  npc_id: arabella
  node_id: FLIGHT_A_001_SEATMATE_SMALLTALK
  description: "테스트 시나리오 설명"
  payload_overrides:
    # 베이스 페이로드 위에 추가로 오버라이드할 데이터 명세
    dialogue_directive:
      purpose: smalltalk_diagnostic
  player_inputs:
    - "입력 문장 1"
  expected:
    # 1. 주는 사람 역할 방지 가드 검사 여부 (기본 true 권장)
    npc_role_must_not_be_giver: true
    # 2. 반드시 대사에 포함되어야 하는 키워드 목록
    must_include_any: ["pen", "borrow"]
    # 3. 포함되어서는 안 되는 금지 표현 목록
    must_not_include_any: ["here you go"]
    # 4. 기대되는 최종 도달 분기 리스트
    branch_type_in: ["retry", "clarify"]
    # 5. LLM Judge용 루브릭 (옵션)
    rubric_for_judge: "Check if the NPC stays warm and patient while requesting a pen."
```

---

## 3. LLM-as-Judge 활성화 방법

환경변수(Environment Variable)를 설정하여 GPT-4o-mini 모델 기반의 대사 루브릭(Rubric) 정성 평가를 결합할 수 있습니다.

```powershell
# Windows PowerShell 환경변수 설정
$env:MURPHY_EVAL_USE_LLM_JUDGE="1"
$env:OPENAI_API_KEY="sk-..."

# 테스트 실행
uv run pytest backend/tests/test_eval_harness_smoke.py -s
```
*주의: LLM Judge 사용 시 비용이 발생하므로 로컬 검증 및 주기적인 릴리즈 일정에 한해 선택적으로 구동하는 것을 권장합니다.*

---

## 4. 리포트(Report) 확인 및 임계값(Threshold) 변경

### 리포트 파일 위치
모든 하네스 실행 기록은 실행 완료 후 JSON 형태로 자동 저장됩니다.
- **경로**: `backend/tests/eval_harness/reports/report_{timestamp}.json`

### 통과율 임계값 변경 방법
현재 스모크 테스트의 통과 임계치(Threshold)는 기본적으로 **80% (0.8)** 로 선언되어 있습니다. 이 임계값은 `backend/tests/test_eval_harness_smoke.py` 파일 내의 `assert summary["pass_rate"] >= 0.8` 부분을 수정하여 동적으로 조절할 수 있습니다.
