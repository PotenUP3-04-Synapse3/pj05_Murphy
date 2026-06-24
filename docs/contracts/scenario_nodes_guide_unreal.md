# Murphy's Trippin - 전체 시나리오 노드 맵 (Unreal Engine 개발자 가이드)

이 문서는 Unreal Engine 클라이언트 팀이 게임 내 시나리오 흐름, NPC 대사, 유저 목표 및 브랜치(분기) 규칙을 쉽게 이해할 수 있도록 구조화한 표입니다.

## 📌 전체 시나리오 개요 및 진행 흐름
| Chapter ID | 순서 | 타이틀 (Chapter Title) | 시작 노드 (Entry Node) | 설명 |
|---|---|---|---|---|
| `CH0_01_FLIGHT_SMALLTALK` | 1 | **Flight Small Talk** | `FLIGHT_A_001_SEATMATE_SMALLTALK` | 비행기 옆자리 승객과의 가벼운 대화 (영어 레벨 간이 측정) |
| `CH0_02_ARRIVAL_TUTORIAL` | 2 | **Airport Arrival Tutorial** | `N/A` | 공항 도착 및 튜토리얼 (클라이언트 자체 연출) |
| `CH0_03_IMMIGRATION_CHECK` | 3 | **Immigration Check** | `IMM_001_PASSPORT` | JFK 공항 입국 심사 (메인 게임 플레이) |
| `CH0_04_BAGGAGE_CLAIM` | 4 | **Baggage Claim** | `BAG_001_REPORT_MISSING_AT_DESK` | 수하물 분실 서비스 데스크 및 세관 검사 보류 구역 대화 |
| `CH0_05_RESULT` | 5 | **Alpha Result** | `ALPHA_999_FINAL_SCOREBOARD` | 최종 성적 및 피드백 출력 화면 |

---

## 🗺️ 장소 및 챕터별 세부 노드 리스트

### 📍 Chapter 1: Flight Small Talk (`CH0_01_FLIGHT_SMALLTALK`)

#### 1. 대화 진행 노드 (Dialogue Nodes)
| 노드 ID | 미션 목표 (KR) | NPC 대사 (EN) | 추천 답변 예시 | 성공 시 이동 | 실패/재시도 이동 | 비고 |
|---|---|---|---|---|---|---|
| `FLIGHT_A_001_SEATMATE_SMALLTALK` | 옆자리 승객의 부탁에 공손하게 응답하기 | "Could I borrow your pen for this arrival form?" | *"Sure, here you are."* | `FLIGHT_A_001_SEATMATE_SMALLTALK` | 엔딩행: `FLIGHT_BAD_END_VERBAL_ABUSE` | 단독 노드 |

#### 2. 엔딩 및 연출 전환 노드 (Ending & Transition Nodes)
| 노드 ID | 유형 | 목표/설명 (KR) | 관련 연출/이벤트 (Unreal Event) | 다음 진행 노드 |
|---|---|---|---|---|
| `FLIGHT_999_COMPLETE` | 🔄 Transition | **비행기 스몰토크 종료 전환** | `START_AIRPORT_ARRIVAL_TUTORIAL` (챕터 로딩/전환) | `CH0_02_ARRIVAL_TUTORIAL` |
| `FLIGHT_BAD_END_VERBAL_ABUSE` | 🔴 Ending | **강제 종료 — 무례한 발언으로 인한 대화 중단** | `SHOW_BAD_END_SCOREBOARD` (게임 오버/배드엔딩 연출) | `ALPHA_999_FINAL_SCOREBOARD` |

### 📍 Chapter 2: Airport Arrival Tutorial (`CH0_02_ARRIVAL_TUTORIAL`)
이 챕터에는 정의된 대화 노드가 없거나 클라이언트 단독 연출입니다.


### 📍 Chapter 3: Immigration Check (`CH0_03_IMMIGRATION_CHECK`)

#### 1. 대화 진행 노드 (Dialogue Nodes)
| 노드 ID | 미션 목표 (KR) | NPC 대사 (EN) | 추천 답변 예시 | 성공 시 이동 | 실패/재시도 이동 | 비고 |
|---|---|---|---|---|---|---|
| `IMM_001_PASSPORT` | 여권 제출하기 | "Passport, please." | *"Here you are."* | `IMM_002_PURPOSE` | 재시도: `IMM_001_RETRY_PASSPORT`<br>확인요청: `IMM_EXTRA_001_CLARIFY_PASSPORT`<br>엔딩행: `END_SECONDARY_INSPECTION` | 단독 노드 |
| `IMM_002_PURPOSE` | 방문 목적 말하기 | "What is the purpose of your visit?" | *"I'm here for tourism."* | `IMM_003_DURATION` | 재시도: `IMM_002_RETRY_PURPOSE`<br>확인요청: `IMM_EXTRA_001_CLARIFY_PURPOSE`<br>엔딩행: `END_SECONDARY_INSPECTION` | 단독 노드 |
| `IMM_003B_LONG_STAY_REASON` | 장기 체류 사유 설명하기 | "Why are you staying for so long?" | *"I want to travel across the country."* | `IMM_004_STAY_LOCATION` | 재시도: `IMM_003B_LONG_STAY_REASON_RETRY_REASON`<br>확인요청: `IMM_003B_LONG_STAY_REASON_CLARIFY_REASON`<br>엔딩행: `END_SECONDARY_INSPECTION` | **추가 질문 분기**<br>Retry형: `IMM_003B_LONG_STAY_REASON_RETRY_REASON`<br>Clarify형: `IMM_003B_LONG_STAY_REASON_CLARIFY_REASON` |
| `IMM_003_DURATION` | 체류 기간 말하기 | "How long will you be staying?" | *"I'll stay for five days."* | `IMM_004_STAY_LOCATION` | 재시도: `IMM_003_RETRY_DURATION`<br>확인요청: `IMM_EXTRA_002_CLARIFY_DURATION`<br>엔딩행: `END_SECONDARY_INSPECTION` | 단독 노드 |
| `IMM_004B_HOTEL_RESERVATION` | 호텔 예약 증명 제시하기 | "Can you show me your hotel reservation?" | *"Yes, here is my hotel reservation confirmation."* | `IMM_005_RETURN_TICKET` | 재시도: `IMM_004B_HOTEL_RESERVATION_RETRY_RESERVATION`<br>확인요청: `IMM_004B_HOTEL_RESERVATION_CLARIFY_RESERVATION`<br>엔딩행: `END_SECONDARY_INSPECTION` | **추가 질문 분기**<br>Retry형: `IMM_004B_HOTEL_RESERVATION_RETRY_RESERVATION`<br>Clarify형: `IMM_004B_HOTEL_RESERVATION_CLARIFY_RESERVATION` |
| `IMM_004C_WHY_THIS_HOTEL` | 해당 호텔을 선택한 이유 설명하기 | "Why did you choose this hotel?" | *"It is close to the main tourist attractions."* | `IMM_005_RETURN_TICKET` | 재시도: `IMM_004C_WHY_THIS_HOTEL_RETRY_HOTEL`<br>확인요청: `IMM_004C_WHY_THIS_HOTEL_CLARIFY_HOTEL`<br>엔딩행: `END_SECONDARY_INSPECTION` | **추가 질문 분기**<br>Retry형: `IMM_004C_WHY_THIS_HOTEL_RETRY_HOTEL`<br>Clarify형: `IMM_004C_WHY_THIS_HOTEL_CLARIFY_HOTEL` |
| `IMM_004_STAY_LOCATION` | 숙소 위치 말하기 | "Where are you staying?" | *"I'm staying at a hotel in New York."* | `IMM_005_RETURN_TICKET` | 재시도: `IMM_004_RETRY_LOCATION`<br>확인요청: `IMM_EXTRA_003_CLARIFY_LOCATION`<br>엔딩행: `END_SECONDARY_INSPECTION` | **추가 질문 분기** |
| `IMM_005B_TRAVEL_ITINERARY` | 여행 일정표 제시하기 | "Can I see your travel itinerary?" | *"Yes, here is my travel itinerary."* | `IMM_008_FIRST_VISIT` | 재시도: `IMM_005B_TRAVEL_ITINERARY_RETRY_ITINERARY`<br>확인요청: `IMM_005B_TRAVEL_ITINERARY_CLARIFY_ITINERARY`<br>엔딩행: `END_SECONDARY_INSPECTION` | **추가 질문 분기**<br>Retry형: `IMM_005B_TRAVEL_ITINERARY_RETRY_ITINERARY`<br>Clarify형: `IMM_005B_TRAVEL_ITINERARY_CLARIFY_ITINERARY` |
| `IMM_005_RETURN_TICKET` | 귀국 항공권 여부 말하기 | "Do you have a return ticket?" | *"Yes, I do. My return flight is next Friday."* | `IMM_008_FIRST_VISIT` | 재시도: `IMM_005_RETRY_RETURN_TICKET`<br>확인요청: `IMM_EXTRA_004_CLARIFY_RETURN_TICKET`<br>엔딩행: `END_SECONDARY_INSPECTION` | **추가 질문 분기** |
| `IMM_007_FINAL_DECISION` | 입국심사 통과 후 수화물 찾는 곳으로 이동하기 | "All right, you're cleared to enter. Enjoy your stay." | *"Thank you, officer."* | `IMM_999_CLEARED` | 재시도: `IMM_007_RETRY_FINAL_DECISION`<br>확인요청: `IMM_EXTRA_007_CLARIFY_FINAL_DECISION`<br>엔딩행: `END_SECONDARY_INSPECTION` | **추가 질문 분기** |
| `IMM_008_FIRST_VISIT` | 미국 첫 방문 여부 답변하기 | "Is this your first visit to the U.S.?" | *"Yes, this is my first time."* | `IMM_009_OCCUPATION` | 재시도: `IMM_008_FIRST_VISIT_RETRY_VISIT`<br>확인요청: `IMM_008_FIRST_VISIT_CLARIFY_VISIT`<br>엔딩행: `END_SECONDARY_INSPECTION` | **추가 질문 분기**<br>Retry형: `IMM_008_FIRST_VISIT_RETRY_VISIT`<br>Clarify형: `IMM_008_FIRST_VISIT_CLARIFY_VISIT` |
| `IMM_009_OCCUPATION` | 직업 말하기 | "What do you do for a living?" | *"I'm an office worker. I work for a tech company."* | `IMM_007_FINAL_DECISION` | 재시도: `IMM_009_OCCUPATION_RETRY_OCCUPATION`<br>확인요청: `IMM_009_OCCUPATION_CLARIFY_OCCUPATION`<br>엔딩행: `END_SECONDARY_INSPECTION` | **추가 질문 분기**<br>Retry형: `IMM_009_OCCUPATION_RETRY_OCCUPATION`<br>Clarify형: `IMM_009_OCCUPATION_CLARIFY_OCCUPATION` |
| `IMM_010B_WHO_PAID` | 여행 경비 지불 주체 밝히기 | "Who paid for this trip?" | *"I paid for the trip myself."* | `IMM_011_DENIED_ENTRY` | 재시도: `IMM_010B_WHO_PAID_RETRY_PAID`<br>확인요청: `IMM_010B_WHO_PAID_CLARIFY_PAID`<br>엔딩행: `END_SECONDARY_INSPECTION` | **추가 질문 분기**<br>Retry형: `IMM_010B_WHO_PAID_RETRY_PAID`<br>Clarify형: `IMM_010B_WHO_PAID_CLARIFY_PAID` |
| `IMM_010_CASH` | 소지 현금 액수 말하기 | "How much cash are you carrying?" | *"I have about five hundred dollars in cash."* | `IMM_010B_WHO_PAID` | 재시도: `IMM_010_CASH_RETRY_CASH`<br>확인요청: `IMM_010_CASH_CLARIFY_CASH`<br>엔딩행: `END_SECONDARY_INSPECTION` | **추가 질문 분기**<br>Retry형: `IMM_010_CASH_RETRY_CASH`<br>Clarify형: `IMM_010_CASH_CLARIFY_CASH` |
| `IMM_011_DENIED_ENTRY` | 입국 거절 이력 답변하기 | "Have you ever been denied entry to the U.S.?" | *"No, I have never been denied entry."* | `IMM_007_FINAL_DECISION` | 재시도: `IMM_011_DENIED_ENTRY_RETRY_ENTRY`<br>확인요청: `IMM_011_DENIED_ENTRY_CLARIFY_ENTRY`<br>엔딩행: `END_SECONDARY_INSPECTION` | **추가 질문 분기**<br>Retry형: `IMM_011_DENIED_ENTRY_RETRY_ENTRY`<br>Clarify형: `IMM_011_DENIED_ENTRY_CLARIFY_ENTRY` |

#### 2. 엔딩 및 연출 전환 노드 (Ending & Transition Nodes)
| 노드 ID | 유형 | 목표/설명 (KR) | 관련 연출/이벤트 (Unreal Event) | 다음 진행 노드 |
|---|---|---|---|---|
| `END_SECONDARY_INSPECTION` | 🔴 Ending | **심사 통과 실패 — 이차 심사실 회부** | `SHOW_BAD_END_SCOREBOARD` (게임 오버/배드엔딩 연출) | `ALPHA_999_FINAL_SCOREBOARD` |
| `IMM_999_CLEARED` | 🔄 Transition | **입국심사 통과 후 수하물 단계 전환** | `ENTER_BAGGAGE_CLAIM` (챕터 로딩/전환) | `BAG_001_REPORT_MISSING_AT_DESK` |
| `IMM_BAD_END_VERBAL_ABUSE` | 🔴 Ending | **강제 종료 — 입국심사관에 대한 무례한 발언** | `SHOW_BAD_END_SCOREBOARD` (게임 오버/배드엔딩 연출) | `ALPHA_999_FINAL_SCOREBOARD` |

### 📍 Chapter 4: Baggage Claim (`CH0_04_BAGGAGE_CLAIM`)

#### 1. 대화 진행 노드 (Dialogue Nodes)
| 노드 ID | 미션 목표 (KR) | NPC 대사 (EN) | 추천 답변 예시 | 성공 시 이동 | 실패/재시도 이동 | 비고 |
|---|---|---|---|---|---|---|
| `BAG_001_REPORT_MISSING_AT_DESK` | 서비스 데스크에 가방이 나오지 않았다고 말하기 | "Hi. How can I help you?" | *"My suitcase didn't come out at the carousel."* | `BAG_002_PROVIDE_CLAIM_TAG` | 재시도: `BAG_001_RETRY_REPORT_MISSING_AT_DESK`<br>확인요청: `BAG_001_CLARIFY_REPORT_MISSING_AT_DESK`<br>엔딩행: `END_BAGGAGE_REPORT_INCOMPLETE` | **추가 질문 분기** |
| `BAG_002_PROVIDE_CLAIM_TAG` | 수하물표나 티켓을 제시하기 | "Do you have your baggage claim tag or ticket?" | *"Yes, here is my baggage claim tag."* | `BAG_003_CONFIRM_SEARCHED_CAROUSEL` | 재시도: `BAG_002_RETRY_PROVIDE_CLAIM_TAG`<br>확인요청: `BAG_002_CLARIFY_PROVIDE_CLAIM_TAG`<br>엔딩행: `END_BAGGAGE_REPORT_INCOMPLETE` | **추가 질문 분기** |
| `BAG_003_CONFIRM_SEARCHED_CAROUSEL` | 수하물 벨트를 잘 확인했다고 답하기 | "Did you check the carousel carefully?" | *"Yes, I checked carefully, but it wasn't there."* | `BAG_004_STAFF_REDIRECT_TO_CUSTOMS_HOLD` | 재시도: `BAG_003_RETRY_CONFIRM_SEARCHED_CAROUSEL`<br>확인요청: `BAG_003_CLARIFY_CONFIRM_SEARCHED_CAROUSEL`<br>엔딩행: `END_BAGGAGE_REPORT_INCOMPLETE` | **추가 질문 분기** |
| `BAG_004_STAFF_REDIRECT_TO_CUSTOMS_HOLD` | 세관 보류 구역으로 돌아가겠다고 답하기 | "I called the baggage area. Your suitcase is being held for inspection. Please go back to the carousel area." | *"Okay, I'll go back and check there."* | `BAG_005_CUSTOMS_HOLD_EXPLANATION` | 재시도: `BAG_004_RETRY_STAFF_REDIRECT_TO_CUSTOMS_HOLD`<br>확인요청: `BAG_004_CLARIFY_STAFF_REDIRECT_TO_CUSTOMS_HOLD`<br>엔딩행: `END_BAGGAGE_REPORT_INCOMPLETE` | **추가 질문 분기** |
| `BAG_005_CUSTOMS_HOLD_EXPLANATION` | 세관 직원의 검사 보류 설명에 동의하기 | "This suitcase was locked for inspection because there may be a questionable item. I'll unlock it, so please check the contents." | *"Okay, I'll open it and check the contents."* | `BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM` | 재시도: `BAG_005_RETRY_CUSTOMS_HOLD_EXPLANATION`<br>확인요청: `BAG_005_CLARIFY_CUSTOMS_HOLD_EXPLANATION`<br>엔딩행: `END_BAGGAGE_REPORT_INCOMPLETE` | **추가 질문 분기** |
| `BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM` | 무작위 세관 의심 물건을 설명하기 | "Can you explain what this item is and why it is in your suitcase?" | *"It's a personal item. I bought it as a souvenir."* | `BAG_007_CUSTOMS_CLEARANCE` | 재시도: `BAG_006_RETRY_EXPLAIN_RANDOM_CUSTOMS_ITEM`<br>확인요청: `BAG_006_CLARIFY_EXPLAIN_RANDOM_CUSTOMS_ITEM`<br>엔딩행: `END_BAGGAGE_REPORT_INCOMPLETE` | **추가 질문 분기** |
| `BAG_007_CUSTOMS_CLEARANCE` | 세관 통과를 확인하고 감사 인사하기 | "You're cleared now. You may take your suitcase and exit the airport." | *"Thank you, officer. I will take my suitcase now."* | `BAG_999_COMPLETE` | 재시도: `BAG_007_RETRY_CUSTOMS_CLEARANCE`<br>확인요청: `BAG_007_CLARIFY_CUSTOMS_CLEARANCE`<br>엔딩행: `END_BAGGAGE_REPORT_INCOMPLETE` | **추가 질문 분기** |

#### 2. 엔딩 및 연출 전환 노드 (Ending & Transition Nodes)
| 노드 ID | 유형 | 목표/설명 (KR) | 관련 연출/이벤트 (Unreal Event) | 다음 진행 노드 |
|---|---|---|---|---|
| `BAG_999_COMPLETE` | 🔄 Transition | **수하물 단계 종료 후 결과 화면 전환** | `SHOW_ALPHA_SCOREBOARD` (챕터 로딩/전환) | `ALPHA_999_FINAL_SCOREBOARD` |
| `BAG_BAD_END_VERBAL_ABUSE` | 🔴 Ending | **강제 종료 — 세관 직원에 대한 무례한 발언** | `SHOW_BAD_END_SCOREBOARD` (게임 오버/배드엔딩 연출) | `ALPHA_999_FINAL_SCOREBOARD` |
| `END_BAGGAGE_REPORT_INCOMPLETE` | 🔴 Ending | **수하물 신고 실패** | `SHOW_BAD_END_SCOREBOARD` (게임 오버/배드엔딩 연출) | `ALPHA_999_FINAL_SCOREBOARD` |

### 📍 Chapter 5: Alpha Result (`CH0_05_RESULT`)

#### 1. 대화 진행 노드 (Dialogue Nodes)
| 노드 ID | 미션 목표 (KR) | NPC 대사 (EN) | 추천 답변 예시 | 성공 시 이동 | 실패/재시도 이동 | 비고 |
|---|---|---|---|---|---|---|

#### 2. 엔딩 및 연출 전환 노드 (Ending & Transition Nodes)
| 노드 ID | 유형 | 목표/설명 (KR) | 관련 연출/이벤트 (Unreal Event) | 다음 진행 노드 |
|---|---|---|---|---|
| `ALPHA_999_FINAL_SCOREBOARD` | 📊 Result | **알파 시나리오 최종 결과 확인하기** | `N/A` (성적 화면 표시) | `게임 종료` |
| `END_ALPHA_SCENARIO` | 🔴 Ending | **알파 시나리오 완료** | `EXIT_GAME` (게임 오버/배드엔딩 연출) | `END_ALPHA_SCENARIO` |