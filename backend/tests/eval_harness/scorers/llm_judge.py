import os
from typing import Any, Dict

def judge_turn(rubric: str, turn_result: Dict[str, Any]) -> Dict[str, Any]:
    """환경변수 MURPHY_EVAL_USE_LLM_JUDGE=1일 때만 동작하여 LLM-as-judge 채점을 수행합니다."""
    if not os.getenv("MURPHY_EVAL_USE_LLM_JUDGE"):
        return {"passed": True, "skipped": True, "details": "LLM Judge가 비활성화되어 있습니다. (MURPHY_EVAL_USE_LLM_JUDGE 미설정)"}

    # API 키가 환경에 정의되어 있는지 확인
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {"passed": False, "skipped": True, "details": "OPENAI_API_KEY 환경변수가 설정되지 않아 LLM Judge를 실행할 수 없습니다."}

    player_text = turn_result.get("player_text", "")
    result = turn_result.get("result", {})
    npc_text = result.get("npc_text", "")
    tts_text = result.get("tts_text", "")
    speaker = result.get("speaker", "")
    tone = result.get("tone", "")
    llm_reason = result.get("llm_reason", "")

    # LangChain ChatOpenAI 또는 원시 OpenAI 클라이언트 사용
    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage, SystemMessage
        
        chat = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.0,
            api_key=api_key,  # type: ignore
            model_kwargs={"response_format": {"type": "json_object"}}
        )

        system_prompt = (
            "You are an impartial evaluator for an English learning game's dialogue agent.\n"
            "Evaluate whether the NPC's response matches the provided rubric.\n"
            "Provide your assessment in a strict JSON format:\n"
            "{\n"
            "  \"passed\": true/false,\n"
            "  \"reason\": \"brief explanation of why it passed or failed based on the rubric\"\n"
            "}"
        )

        user_content = (
            f"Rubric: {rubric}\n\n"
            f"Conversation Turn Data:\n"
            f"- NPC Speaker Name: {speaker}\n"
            f"- Player Input: \"{player_text}\"\n"
            f"- NPC Response (Text): \"{npc_text}\"\n"
            f"- NPC Response (TTS SSML): \"{tts_text}\"\n"
            f"- NPC Tone: {tone}\n"
            f"- NPC Generation Internal Reason: \"{llm_reason}\"\n"
        )

        response = chat.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_content)
        ])

        import json
        content_str = response.content if isinstance(response.content, str) else str(response.content)
        res_data = json.loads(content_str)
        return {
            "passed": bool(res_data.get("passed", False)),
            "details": str(res_data.get("reason", "No reason provided by LLM Judge.")),
            "skipped": False
        }
    except Exception as e:
        return {
            "passed": False,
            "details": f"LLM Judge 수행 중 에러가 발생했습니다: {str(e)}",
            "skipped": True
        }
