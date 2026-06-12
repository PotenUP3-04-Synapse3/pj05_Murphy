# OpenKB 문서 축적

담당자: William Kim
상태: 진행 중
마감일: 06/04/2026
우선순위: 높음
작업 유형: OpenKB
마감기한: 프프로토

## 작업 설명

현재 구현 기준으로 OpenKB 문서 축적은 이렇게 진행됩니다.

```jsx
매 turn마다 B agent 실행
 -> B가 evaluation / hint / report_item / rubric / focus_on_form 생성
 -> B OpenKB writer가 dev_b namespace에 저장
 -> session별 JSONL + record별 Markdown 축적
```

저장 위치는 두 곳입니다.

```jsx
backend/runtime/openkb/dev_b/<session_id>.jsonl
backend/runtime/openkb/dev_b/<record_id>.md
```

**1. JSONL 축적**

세션 단위로 계속 append됩니다.

예:

`backend/runtime/openkb/dev_b/session_001.jsonl`

한 turn이 끝날 때마다 한 줄씩 추가됩니다.

```json
{"record_id":"dev_b_abc","turn_index":1,"node_id":"IMM_001_PASSPORT", ...}
{"record_id":"dev_b_def","turn_index":2,"node_id":"IMM_002_PURPOSE", ...}
{"record_id":"dev_b_xyz","turn_index":3,"node_id":"IMM_003_DURATION", ...}
```

즉 같은 session 안에서 플레이어가 답변할수록 OpenKB record가 누적됩니다.

**2. Markdown 축적**

각 turn record마다 별도 .md 파일이 만들어집니다.

```jsx
backend/runtime/openkb/dev_b/dev_b_abc.md
backend/runtime/openkb/dev_b/dev_b_def.md
backend/runtime/openkb/dev_b/dev_b_xyz.md
```

이건 사람이 읽기 위한 기록입니다. 내용은 다음처럼 구성됩니다.

```json
# Developer B OpenKB Record - dev_b_abc

- Session: session_001
- Node: IMM_002_PURPOSE
- Turn: 2
- Player Text: Travel. New York.
- Verdict: SUCCESS
- Branch: success -> IMM_003_DURATION
- Focus-on-Form: sentence_completion
- Feedback Generation: llm
- Difficulty: TSL_2_FUNCTIONAL

## Report Seed

- Summary: ...
- Improvement: ...
- Example: ...

## Error Capture

...
```

**3. 중복 방지**

같은 turn을 다시 평가해도 중복 저장되지 않게 되어 있습니다.

record id는 다음 값으로 결정됩니다.

`request_id + node_id + turn_index + error_id`

같은 record id가 이미 JSONL에 있으면 다시 append하지 않습니다.

**4. 현재 축적되는 내용**

현재 OpenKB record에는 다음이 들어갑니다.

- player_text
- understanding summary
- evaluation
- level_hint
- error_capture
- out_game_feedback_seed
- focus_on_form_targets
- report_item
- rubric_scores
- difficulty_profile
- feedback_generation
- branch
- state_delta

**5. 아직 안 되는 것**

현재는 “축적”까지만 됩니다. 아직 안 되는 것은:

```json
C가 이 record를 검색/retrieval
세션 전체 final report 생성
100점 최종 점수 집계
OpenKB 문서 embedding/vector search
원격 OpenKB 동기화
```

즉 현재는 **B가 OpenKB dev_b namespace에 turn별 학습 기록을 쌓는 단계**이고, 그 기록을 모아 최종 결과 화면으로 조립하는 단계는 아직 남아 있습니다.

## 하위 작업

- [ ]  
- [ ]  
- [ ]  

## 지원 파일

[https://www.notion.so](https://www.notion.so)

[https://www.notion.so](https://www.notion.so)

[https://www.notion.so](https://www.notion.so)