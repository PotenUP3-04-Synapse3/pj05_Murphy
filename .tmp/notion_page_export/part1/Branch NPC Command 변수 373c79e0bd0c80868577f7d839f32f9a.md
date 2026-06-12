# Branch / NPC / Command 변수

담당자: 용희 김, William Kim
상태: 진행 중
시작일: 06/02/2026
마감일: 06/04/2026
우선순위: 보통
작업 유형: Data
마감기한: 프로토
요약:   • Branch / NPC / Command 변수

| 변수 | 생성/소유 | 소비 | 왜 필요한가 |
| --- | --- | --- | --- |
| `branch_type` | Scenario State Machine | Response Builder, NPC Dialogue | 성공, 재시도, 추가 질문, 배드엔딩 등 분기 유형 |
| `next_node_id` | Scenario State Machine | Validator, Unreal | 다음으로 이동할 노드 |
| `branch_reason` | Scenario State Machine | Debug, Portfolio, QA | 왜 그 노드로 갔는지 설명 |
| `npc_text` | NPC Dialogue Agent | Unreal, TTS | NPC가 실제로 말할 문장 |
| `npc_tone` | NPC Dialogue Agent | TTS, Animation | NPC 음성/표정 톤 |
| `animation` | NPC Dialogue Agent | Unreal, Validator | 실행할 NPC 애니메이션 |
| `feedback_kr` | NPC Dialogue Agent / Level Hint | UI | 플레이어에게 보여줄 학습 피드백 |
| `commands` | Response Builder | Unreal | Unreal이 실제로 실행할 명령 목록 |
| `validation_result` | Validator | Orchestrator | 최종 JSON이 안전한지 확인 |