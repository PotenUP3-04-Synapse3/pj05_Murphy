from __future__ import annotations

from typing import Any, NotRequired, TypedDict

from langgraph.graph import END, START, StateGraph

from backend.app.schemas.game_turn import DevBPolicyInput, DevBPolicyOutput, OpenKBWriteResult
from backend.app.services.service_b.feedback_hint_generator import FeedbackHintGeneration
from backend.app.services.service_b.scenario_state_machine import ScenarioDecision
from backend.app.services.service_b.tier_difficulty_controller import TierDifficultyResult
from backend.app.tools.tool_b.developer_b_policy_graph_tools import (
    DEVELOPER_B_POLICY_GRAPH_NODE_NAMES as _DEVELOPER_B_POLICY_GRAPH_NODE_NAMES,
    DeveloperBPolicyGraphTools,
)


DEVELOPER_B_POLICY_GRAPH_NODE_NAMES = _DEVELOPER_B_POLICY_GRAPH_NODE_NAMES


class DeveloperBPolicyState(TypedDict):
    """
    Developer B 정책 결정 그래프(Policy Graph)의 내부 상태(State)를 나타내는 사전(TypedDict) 타입입니다.
    
    초보자 가이드: LangGraph 기반으로 상태를 관리하며, 각 단계(노드)를 거칠 때마다 이 상태 객체에 데이터가 누적되고 업데이트됩니다.
    
    Attributes:
        payload: 외부(Developer C)로부터 넘어온 입력 데이터 (현재 노드 ID, 플레이어 프로필 등)
        tools: 그래프의 각 노드에서 실행할 수 있는 비즈니스 로직 도구 모음 (DeveloperBPolicyGraphTools)
        agent_run: 에이전트 실행 기록 로깅을 위한 사전형 메타데이터
        input_summary: 입력 데이터 요약 정보
        decision: 시나리오 상태 머신이 도출한 다음 분기 판단 정보
        english_level: 현재 분석된 영어 레벨
        hint_policy: 힌트 제공 여부 및 내용 정보
        feedback_strategy: 어떤 방식으로 피드백을 전달할지 결정된 전략
        has_form_issue: 문법 오류나 어색한 표현 등의 형태적 결함 여부
        tier_result: 티어 및 레벨 난이도 평가 결과
        output: 최종적으로 반환할 Developer B 정책 결과
        feedback_generation: LLM을 통해 생성된 피드백의 디버그 정보
        openkb_write: OpenKB 데이터베이스에 기록한 결과 정보
    """
    payload: DevBPolicyInput
    tools: DeveloperBPolicyGraphTools
    agent_run: NotRequired[dict[str, Any]]
    input_summary: NotRequired[dict[str, Any]]
    decision: NotRequired[ScenarioDecision]
    english_level: NotRequired[str]
    hint_policy: NotRequired[tuple[bool, str, str | None, str | None]]
    feedback_strategy: NotRequired[str]
    has_form_issue: NotRequired[bool]
    tier_result: NotRequired[TierDifficultyResult]
    output: NotRequired[DevBPolicyOutput]
    feedback_generation: NotRequired[FeedbackHintGeneration]
    openkb_write: NotRequired[OpenKBWriteResult]


def build_initial_developer_b_policy_state(
    *,
    payload: DevBPolicyInput,
    tools: DeveloperBPolicyGraphTools,
) -> DeveloperBPolicyState:
    """
    Developer B 정책 결정 그래프에 입력할 최초 상태(State) 객체를 생성합니다.
    
    Args:
        payload: 에이전트 실행에 필요한 입력 매개변수
        tools: 각 노드에서 작동할 비즈니스 로직 툴 객체
        
    Returns:
        초기 payload와 tools 정보만 담긴 DeveloperBPolicyState 딕셔너리
    """
    return {"payload": payload, "tools": tools}


def build_developer_b_policy_graph() -> Any:
    """
    LangGraph를 사용하여 Developer B의 모든 정책 결정 노드를 순차적으로 연결한 워크플로우 그래프를 생성하고 컴파일합니다.
    
    초보자 가이드: 시나리오 분기 판단 -> 영어 레벨 산정 -> 피드백 전략 수립 -> 난이도 조정 -> 피드백 생성 -> OpenKB 기록 등의 
    일련의 노드들을 파이프라인처럼 연결해 줍니다.
    
    Returns:
        컴파일된 LangGraph 인스턴스 (invoke를 통해 실행 가능)
    """
    graph = StateGraph(DeveloperBPolicyState)
    graph.add_node("start_agent_run", _start_agent_run)
    graph.add_node("decide_scenario_branch", _decide_scenario_branch)
    graph.add_node("derive_level_and_hint", _derive_level_and_hint)
    graph.add_node("derive_feedback_strategy", _derive_feedback_strategy)
    graph.add_node("evaluate_tier_difficulty", _evaluate_tier_difficulty)
    graph.add_node("build_base_policy_output", _build_base_policy_output)
    graph.add_node("generate_feedback_hint", _generate_feedback_hint)
    graph.add_node("apply_feedback_generation", _apply_feedback_generation)
    graph.add_node("attach_report_and_dialogue_seeds", _attach_report_and_dialogue_seeds)
    graph.add_node("validate_policy_output", _validate_policy_output)
    graph.add_node("write_openkb_feedback", _write_openkb_feedback)
    graph.add_node("finish_agent_run", _finish_agent_run)

    graph.add_edge(START, "start_agent_run")
    graph.add_edge("start_agent_run", "decide_scenario_branch")
    graph.add_edge("decide_scenario_branch", "derive_level_and_hint")
    graph.add_edge("derive_level_and_hint", "derive_feedback_strategy")
    graph.add_edge("derive_feedback_strategy", "evaluate_tier_difficulty")
    graph.add_edge("evaluate_tier_difficulty", "build_base_policy_output")
    graph.add_edge("build_base_policy_output", "generate_feedback_hint")
    graph.add_edge("generate_feedback_hint", "apply_feedback_generation")
    graph.add_edge("apply_feedback_generation", "attach_report_and_dialogue_seeds")
    graph.add_edge("attach_report_and_dialogue_seeds", "validate_policy_output")
    graph.add_edge("validate_policy_output", "write_openkb_feedback")
    graph.add_edge("write_openkb_feedback", "finish_agent_run")
    graph.add_edge("finish_agent_run", END)
    return graph.compile()


def _start_agent_run(state: DeveloperBPolicyState) -> dict[str, Any]:
    """
    에이전트 실행 기록(AgentRun 로그)을 시작하는 노드 함수입니다.
    """
    return state["tools"].start_agent_run_tool(state)


def _decide_scenario_branch(state: DeveloperBPolicyState) -> dict[str, Any]:
    """
    플레이어 발화에 부합하는 시나리오 분기 및 진행 방향(성공, 재시도, 경고 등)을 판정하는 노드 함수입니다.
    """
    return state["tools"].decide_scenario_branch_tool(state)


def _derive_level_and_hint(state: DeveloperBPolicyState) -> dict[str, Any]:
    """
    학습자의 영어 실력 레벨을 산정하고, 등급에 맞춤화된 힌트 정책을 결정하는 노드 함수입니다.
    """
    return state["tools"].derive_level_and_hint_tool(state)


def _derive_feedback_strategy(state: DeveloperBPolicyState) -> dict[str, Any]:
    """
    어떤 언어적 수정 기법(재진술, 명료화 등)으로 피드백을 전달할지 결정하는 노드 함수입니다.
    """
    return state["tools"].derive_feedback_strategy_tool(state)


def _evaluate_tier_difficulty(state: DeveloperBPolicyState) -> dict[str, Any]:
    """
    플레이어 등급과 대화 상태에 부합하는 세부 루브릭 영역 평가와 난이도 설정을 산출하는 노드 함수입니다.
    """
    return state["tools"].evaluate_tier_difficulty_tool(state)


def _build_base_policy_output(state: DeveloperBPolicyState) -> dict[str, Any]:
    """
    1차적인 평가 분석 결과들이 담긴 기본 정책 출력 객체를 빌드하는 노드 함수입니다.
    """
    return state["tools"].build_base_policy_output_tool(state)


def _generate_feedback_hint(state: DeveloperBPolicyState) -> dict[str, Any]:
    """
    LLM 또는 룰 기반 로직을 활용해 학습자를 위한 한글 피드백과 모범 예문을 생성하는 노드 함수입니다.
    """
    return state["tools"].generate_feedback_hint_tool(state)


def _apply_feedback_generation(state: DeveloperBPolicyState) -> dict[str, Any]:
    """
    생성된 한글 힌트와 피드백 상세 정보를 최종 출력 필드에 반영하고 병합하는 노드 함수입니다.
    """
    return state["tools"].apply_feedback_generation_tool(state)


def _attach_report_and_dialogue_seeds(state: DeveloperBPolicyState) -> dict[str, Any]:
    """
    최종 성적표 작성 및 다음 턴 NPC 대사 생성을 돕기 위한 보고서/대화 시드(Seed)를 추가하는 노드 함수입니다.
    """
    return state["tools"].attach_report_and_dialogue_seeds_tool(state)


def _validate_policy_output(state: DeveloperBPolicyState) -> dict[str, Any]:
    """
    최종 완성된 정책 결과가 데이터 스키마 규칙과 유효성을 총족하는지 검사하는 노드 함수입니다.
    """
    return state["tools"].validate_policy_output_tool(state)


def _write_openkb_feedback(state: DeveloperBPolicyState) -> dict[str, Any]:
    """
    결정된 피드백 및 로그 데이터를 OpenKB 데이터베이스 파일에 기록하는 노드 함수입니다.
    """
    return state["tools"].write_openkb_feedback_tool(state)


def _finish_agent_run(state: DeveloperBPolicyState) -> dict[str, Any]:
    """
    에이전트 실행 완료 로그를 마감하고 기록을 마치는 노드 함수입니다.
    """
    return state["tools"].finish_agent_run_tool(state)
