# STT Pipeline

담당자: Sean Han
상태: 진행 중
시작일: 06/01/2026
마감일: 06/02/2026
우선순위: 보통
작업 유형: STT
마감기한: 프로토
요약:   • 플레이어 음성 입력을 텍스트로 변환

```
음성 입력 → STT → 텍스트 + 신뢰도 + 언어 힌트
```

| 작업 | 설명 |
| --- | --- |
| 음성 입력 수신 방식 정의 | Unreal에서 audio file, audio blob, audio_url 중 어떤 방식으로 보낼지 결정 |
| STT 호출 모듈 작성 | 음성 → 텍스트 변환 |
| 한국어+영어 혼합 대응 | Chaos Konglish Mode 때문에 ko/en mixed 입력 허용 |
| STT confidence 처리 | 신뢰도가 낮으면 재확인 분기로 넘길 수 있게 함 |
| 텍스트 입력 fallback | 키보드 입력일 때는 STT를 건너뛰도록 처리 |
| STT 결과 표준화 | Orchestrator가 항상 같은 구조로 받게 만들기 |

## STT 결과 예시

```json
{
  "input_type":"voice",
  "stt_result": {
    "text":"Travel이요. Trouble 아니에요.",
    "confidence":0.87,
    "language_detected":"ko_en_mixed",
    "needs_repeat":false
  }
}
```

##