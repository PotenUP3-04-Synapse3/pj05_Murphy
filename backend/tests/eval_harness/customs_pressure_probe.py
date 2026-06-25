"""억까(trick) 세관 물품 압박 판정 진단 하네스.

목적
----
BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM 노드에서, 난이도/카테고리가 제각각인 모든
세관 물품에 대해 "generic하고 불충분한 설명"을 했을 때 시스템이 그냥 통과시키는지
(SUCCESS) 아니면 압박/제지하는지(REASK/FAIL)를 전수 확인한다.

배경 가설: 물품의 suspicion_reason / difficulty / category 가 판정 파이프라인
(understanding -> decide)에 전혀 전달되지 않으므로, generic 답변("선물이에요")이
물품 난이도와 무관하게 전부 통과될 것이다. 로그로 이를 확인하고 다음 수정 계획의
근거로 삼는다.

실행
----
    .venv/Scripts/python.exe -m backend.tests.eval_harness.customs_pressure_probe
    .venv/Scripts/python.exe -m backend.tests.eval_harness.customs_pressure_probe --mode llm
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Literal

from backend.app.agents.agent_c.understanding_agent import UnderstandingAgent
from backend.app.data.challenge_tables import CUSTOMS_ITEMS, CustomsItemEntry
from backend.app.schemas.game_turn import (
    DevBPolicyInput,
    InputSource,
    PlayerProfile,
    RandomCustomsItemContext,
    ScenarioState,
)
from backend.app.services.service_b.scenario_state_machine import ScenarioStateMachine
from backend.app.services.service_c.openkb_service import OpenKBService
from backend.app.services.service_c.settings_service import AppSettings

CHAPTER_ID = "CH0_04_BAGGAGE_CLAIM"
NODE_ID = "BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM"

# 의도적으로 generic·불충분한 설명들. 물품의 구체적 의심 사유(수량/신고/검역 등)를
# 전혀 다루지 않는 답변이라, 난이도 높은 물품이면 추가 압박이 있어야 정상이다.
INSUFFICIENT_ANSWERS = [
    "It's a gift for my friend.",
    "It's just a personal item.",
    "I bought it as a souvenir.",
]

INSUFFICIENT_ANSWERS_POOL = [
    "It's a gift for my friend.",
    "It's just a personal item.",
    "I bought it as a souvenir.",
    "It's something I brought from home.",
    "It's mine, nothing special.",
    "I just have it for myself, honestly.",
]


@dataclass
class ProbeResult:
    item_id: str
    difficulty: int
    category: str
    answer: str
    verdict: str
    branch_type: str
    next_action: str

    @property
    def passed_through(self) -> bool:
        """SUCCESS/ADVANCE = '그냥 넘어감'."""
        return self.branch_type == "success"


@dataclass
class MultiturnProbeResult:
    item_id: str
    difficulty: int
    category: str
    turns: list[dict[str, Any]]

    @property
    def leaked(self) -> bool:
        # High difficulty (>=7) leaked if success occurred at all
        if self.difficulty >= 7:
            return any(t["branch_type"] == "success" for t in self.turns)
        return False

    @property
    def held(self) -> bool:
        # High difficulty holds pressure if success never occurred
        if self.difficulty >= 7:
            return not self.leaked
        # Low difficulty holds if it successfully passed on turn 1 (or any turn)
        return any(t["branch_type"] == "success" for t in self.turns)


def _build_payload(
    item: CustomsItemEntry,
    answer: str,
    understanding,
    node_ctx,
    declared: bool = False,
    scenario_state: ScenarioState | None = None,
) -> DevBPolicyInput:
    if scenario_state is None:
        scenario_state = ScenarioState(
            patience=100,
            suspicion=0,
            retry_count=0,
            hint_count=0,
            previous_fail_count=0,
            completed_intents=[],
        )
    return DevBPolicyInput(
        contract_version="dev_b_policy.v1",
        request_id="probe",
        session_id="probe",
        player_id="probe",
        chapter_id=CHAPTER_ID,
        scene_id="JFK_BAGGAGE_CLAIM",
        current_node_id=NODE_ID,
        turn_index=1,
        player_text=answer,
        input_source=InputSource(
            input_type="voice",
            stt_confidence=1.0,
            language_detected="en-US",
            needs_repeat=False,
        ),
        player_profile=PlayerProfile(
            nickname="Probe",
            english_confidence="beginner",
            tier="Silver",
            travel_speaking_level="TSL_2_FUNCTIONAL",
        ),
        scenario_state=scenario_state,
        node_context=node_ctx,
        understanding=understanding,
        client_allowed_next_nodes=node_ctx.allowed_next_nodes,
        random_customs_item=RandomCustomsItemContext(
            item_id=item.item_id,
            item_name=item.name_en,
            item_category=item.item_category,
            item_description=item.suspicion_reason,
            declared=declared,
            difficulty=item.difficulty,
            suspicion_reason=item.suspicion_reason,
        ),
    )


def run(mode: Literal["rule", "llm"]) -> tuple[list[ProbeResult], list[ProbeResult]]:
    settings = AppSettings(murphy_understanding_mode=mode)
    agent = UnderstandingAgent(settings=settings)
    sm = ScenarioStateMachine()
    node_ctx = OpenKBService().get_node_context(CHAPTER_ID, NODE_ID)

    insufficient_results: list[ProbeResult] = []
    sufficient_results: list[ProbeResult] = []

    from backend.app.schemas.game_turn import CustomsItemJudgeContext

    # 1. Test insufficient answers (expected to fail/clarify/stop for diff >= 7)
    for item in CUSTOMS_ITEMS:
        for answer in INSUFFICIENT_ANSWERS:
            node_ctx_copy = node_ctx.model_copy()
            node_ctx_copy.customs_item_context = CustomsItemJudgeContext(
                item_name=item.name_en,
                item_category=item.item_category,
                difficulty=item.difficulty,
                suspicion_reason=item.suspicion_reason,
                declared=False,
            )
            understanding = agent.analyze_player_text(answer, node_ctx_copy)
            payload = _build_payload(item, answer, understanding, node_ctx_copy, declared=False)
            decision = sm.decide(payload)
            insufficient_results.append(
                ProbeResult(
                    item_id=item.item_id,
                    difficulty=item.difficulty,
                    category=item.item_category,
                    answer=answer,
                    verdict=decision.verdict,
                    branch_type=decision.branch_type,
                    next_action=decision.next_action,
                )
            )

    # 2. Test sufficient answers (positive controls, expected to succeed/pass)
    for item in CUSTOMS_ITEMS:
        declared_status = item.item_category in {"valuable", "luxury"}
        # For rule mode keyword matching, include "personal item" slot keyword and the item name
        answer = f"It's my personal item, this is {item.name_en.lower()}."
        node_ctx_copy = node_ctx.model_copy()
        node_ctx_copy.customs_item_context = CustomsItemJudgeContext(
            item_name=item.name_en,
            item_category=item.item_category,
            difficulty=item.difficulty,
            suspicion_reason=item.suspicion_reason,
            declared=declared_status,
        )
        understanding = agent.analyze_player_text(answer, node_ctx_copy)
        payload = _build_payload(item, answer, understanding, node_ctx_copy, declared=declared_status)
        decision = sm.decide(payload)
        sufficient_results.append(
            ProbeResult(
                item_id=item.item_id,
                difficulty=item.difficulty,
                category=item.item_category,
                answer=answer,
                verdict=decision.verdict,
                branch_type=decision.branch_type,
                next_action=decision.next_action,
            )
        )

    return insufficient_results, sufficient_results


def run_multiturn(mode: Literal["rule", "llm"]) -> list[MultiturnProbeResult]:
    settings = AppSettings(murphy_understanding_mode=mode)
    agent = UnderstandingAgent(settings=settings)
    sm = ScenarioStateMachine()
    node_ctx = OpenKBService().get_node_context(CHAPTER_ID, NODE_ID)

    from backend.app.schemas.game_turn import CustomsItemJudgeContext

    results: list[MultiturnProbeResult] = []

    for item in CUSTOMS_ITEMS:
        patience = 30
        suspicion = 0
        retry_count = 0
        hint_count = 0
        previous_fail_count = 0

        turns_data = []

        for turn_idx in range(1, 9):
            answer = INSUFFICIENT_ANSWERS_POOL[(turn_idx - 1) % len(INSUFFICIENT_ANSWERS_POOL)]

            node_ctx_copy = node_ctx.model_copy()
            node_ctx_copy.customs_item_context = CustomsItemJudgeContext(
                item_name=item.name_en,
                item_category=item.item_category,
                difficulty=item.difficulty,
                suspicion_reason=item.suspicion_reason,
                declared=False,
            )

            current_state = ScenarioState(
                patience=patience,
                suspicion=suspicion,
                retry_count=retry_count,
                hint_count=hint_count,
                previous_fail_count=previous_fail_count,
                completed_intents=[],
            )

            understanding = agent.analyze_player_text(answer, node_ctx_copy)
            payload = _build_payload(
                item,
                answer,
                understanding,
                node_ctx_copy,
                declared=False,
                scenario_state=current_state,
            )
            decision = sm.decide(payload)

            turns_data.append({
                "turn_index": turn_idx,
                "answer": answer,
                "verdict": decision.verdict,
                "branch_type": decision.branch_type,
                "next_action": decision.next_action,
                "patience": patience,
                "retry_count": retry_count,
                "hint_count": hint_count,
                "suspicion": suspicion,
                "previous_fail_count": previous_fail_count,
            })

            # Update state with deltas
            patience = max(0, patience + decision.patience_delta)
            suspicion = max(0, suspicion + decision.suspicion_delta)
            retry_count = retry_count + decision.retry_count_delta
            hint_count = hint_count + decision.hint_count_delta
            previous_fail_count = previous_fail_count + 1

            if decision.branch_type == "success":
                break

            if decision.branch_type in {"bad_end", "final"} or patience <= 0:
                break

        results.append(
            MultiturnProbeResult(
                item_id=item.item_id,
                difficulty=item.difficulty,
                category=item.item_category,
                turns=turns_data,
            )
        )

    return results


def report(insufficient: list[ProbeResult], sufficient: list[ProbeResult], mode: Literal["rule", "llm"]) -> None:
    print(f"\n=== Customs pressure probe (mode={mode}) ===")
    print("\n--- 1. INSUFFICIENT GENERIC ANSWERS ---")
    print(f"{'item_id':<28}{'diff':>4}  {'verdict':<12}{'branch':<10}{'pass?':<6} answer")
    print("-" * 100)
    for r in insufficient:
        flag = "PASS" if r.passed_through else "stop"
        print(
            f"{r.item_id:<28}{r.difficulty:>4}  {r.verdict:<12}{r.branch_type:<10}"
            f"{flag:<6} {r.answer}"
        )

    total_ins = len(insufficient)
    passed_ins = sum(1 for r in insufficient if r.passed_through)
    print("-" * 100)
    print(f"INSUFFICIENT TOTAL: {passed_ins}/{total_ins} generic answers were let through (branch=success)")

    # Leaking high difficulty items (difficulty >= 7)
    by_item: dict[str, list[ProbeResult]] = {}
    for r in insufficient:
        by_item.setdefault(r.item_id, []).append(r)
    leaky_high = [
        iid for iid, rs in by_item.items()
        if rs[0].difficulty >= 7 and any(x.passed_through for x in rs)
    ]
    print(f"HIGH DIFFICULTY ITEMS leaking: {len(leaky_high)}/{sum(1 for item in CUSTOMS_ITEMS if item.difficulty >= 7)}")
    if leaky_high:
        print("  " + ", ".join(sorted(leaky_high)))

    print("\n--- 2. SUFFICIENT ANSWERS (POSITIVE CONTROLS) ---")
    print(f"{'item_id':<28}{'diff':>4}  {'verdict':<12}{'branch':<10}{'pass?':<6} answer")
    print("-" * 100)
    for r in sufficient:
        flag = "PASS" if r.passed_through else "stop"
        print(
            f"{r.item_id:<28}{r.difficulty:>4}  {r.verdict:<12}{r.branch_type:<10}"
            f"{flag:<6} {r.answer}"
        )
    total_suf = len(sufficient)
    passed_suf = sum(1 for r in sufficient if r.passed_through)
    print("-" * 100)
    print(f"SUFFICIENT PASS RATE: {passed_suf}/{total_suf} (branch=success)")


def report_multiturn(results: list[MultiturnProbeResult], mode: Literal["rule", "llm"]) -> None:
    print(f"\n=== Customs pressure probe (mode={mode}, multi-turn) ===")
    print(f"{'item_id':<28}{'diff':>4}  {'category':<10}{'turns':>5}  {'status':<6} {'final_branch':<10}")
    print("-" * 100)

    leaks = []
    helds = []

    for r in results:
        final_turn = r.turns[-1]
        status = "LEAK" if r.leaked else ("HELD" if r.held else "stop")
        print(
            f"{r.item_id:<28}{r.difficulty:>4}  {r.category:<10}{len(r.turns):>5}  "
            f"{status:<6} {final_turn['branch_type']:<10}"
        )

        if r.leaked:
            leaks.append(r)
        else:
            helds.append(r)

    print("-" * 100)
    total_high = sum(1 for r in results if r.difficulty >= 7)
    leaked_high = sum(1 for r in leaks if r.difficulty >= 7)

    total_low = sum(1 for r in results if r.difficulty < 7)
    passed_low = sum(1 for r in results if r.difficulty < 7 and r.held)

    print(f"HIGH DIFFICULTY LEAKS: {leaked_high}/{total_high} high diff items leaked success.")
    print(f"LOW DIFFICULTY PASS RATE: {passed_low}/{total_low} low diff items passed.")

    if leaks:
        print("\n--- LEAK DETAILS ---")
        for r in leaks:
            print(f"\nItem: {r.item_id} (diff={r.difficulty})")
            for t in r.turns:
                print(
                    f"  Turn {t['turn_index']}: '{t['answer']}' -> "
                    f"{t['verdict']}/{t['branch_type']}/{t['next_action']} "
                    f"(patience={t['patience']}, retry={t['retry_count']})"
                )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="rule", choices=["rule", "llm"])
    parser.add_argument("--multiturn", action="store_true", help="Run multi-turn pressure test")
    args = parser.parse_args()

    if args.multiturn:
        results = run_multiturn(args.mode)
        report_multiturn(results, args.mode)
    else:
        insufficient, sufficient = run(args.mode)
        report(insufficient, sufficient, args.mode)


if __name__ == "__main__":
    main()
