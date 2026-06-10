# Orchestrator

담당자: Sean Han
상태: 진행 중
시작일: 06/01/2026
마감일: 06/04/2026
우선순위: 높음
작업 유형: Orchestrator
마감기한: 프로토
요약:   • AI 백엔드의 중심 흐름을 제어하는 시스템

```
요청 수신
↓
STT 처리
↓
OpenKB 조회
↓
Understanding Agent 호출
↓
다른 Agent / Controller 호출
↓
Validator 검사
↓
최종 JSON 반환
```

| 작업 | 설명 |
| --- | --- |
| `/api/game/ai/respond` 엔드포인트 구현 | Unreal이 호출하는 대표 API |
| 요청 JSON 검증 | session, node_id, player_input 등 필수값 확인 |
| Agent 호출 순서 관리 | Understanding → Level/Hint → State Machine → NPC 순서 |
| 각 모듈 입출력 연결 | Agent 결과를 다음 모듈 입력으로 변환 |
| 실패 fallback 처리 | STT 실패, Agent 실패, Validator 실패 시 기본 응답 반환 |
| 최종 response 조립 | Unreal이 실행 가능한 JSON으로 반환 |

```python
def respond(request):
    normalized_input = process_stt_or_text(request)

    node_context = retrieve_node_context(
        current_node_id=request.session.current_node_id
    )

    understanding = run_understanding_agent(
        player_text=normalized_input.text,
        node_context=node_context,
        game_state=request.game_state
    )

    level_hint = run_level_hint_agent(
        player_text=normalized_input.text,
        understanding=understanding,
        node_context=node_context
    )

    branch = run_scenario_state_machine(
        understanding=understanding,
        level_hint=level_hint,
        node_context=node_context,
        game_state=request.game_state
    )

    npc_dialogue = run_npc_dialogue_agent(
        understanding=understanding,
        level_hint=level_hint,
        branch=branch,
        node_context=node_context
    )

    response = build_unreal_response(
        understanding=understanding,
        level_hint=level_hint,
        branch=branch,
        npc_dialogue=npc_dialogue
    )

    return validate_and_return(response)
```