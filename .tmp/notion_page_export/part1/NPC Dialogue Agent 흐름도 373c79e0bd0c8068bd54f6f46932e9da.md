# NPC Dialogue Agent 흐름도

담당자: 용희 김
상태: 시작 전
시작일: 06/01/2026
마감일: 06/01/2026
우선순위: 높음
작업 유형: Agent
마감기한: 프로토

## 작업 설명

NPC Dialogue Agent 흐름도 작성

## 하위 작업

- [x]  Agent 역할 명시
- [x]  흐름도 시각화
- [x]  필요 변수 정의

## Agent 역할

1. Level Design Agent의 데이터를 기반으로 NPC 대화 생성
    1. output = text
2. Level Design Agent의 데이터를 기반으로 TTS 데이터 생성
    1. output = text
3. 생성된 TTS 데이터 기반으로 TTS 파일 생성
    1. output = wav

## NPC Dialogue Agent 흐름도 시각화

![NPC_Dialogue_Agent (1).png](NPC_Dialogue_Agent_(1).png)

## 필요 변수 정의

1. Level Design Agent

| 변수 | 생성/소유 | 왜 필요한가 |
| --- | --- | --- |
| `english_level` | Level/Hint Agent | 사용자 영어 수준. 예: `beginner`, `survival`, `confident` |
| `avoid_expression` | Level/Hint AgentUI | Feedback피해야 할 표현 |
| `feedback_focus` | Level/Hint Agent | 이번 피드백이 무엇에 집중해야 하는지 |
| `text` | Understanding Agent | 사용자가 어떻게 말했는지 STT로 변환된 데이터 |

## 지원 파일

[https://www.notion.so](https://www.notion.so)

[NPC_Dialogue_Agent](https://drive.google.com/file/d/1-5f3qYMJCDUkFJi-GFHfUu7T2uFPEpDF/view?usp=drivesdk)

[https://www.notion.so](https://www.notion.so)