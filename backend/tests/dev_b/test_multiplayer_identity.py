import pytest
from backend.app.services.service_a.npc_short_term_memory_service import build_thread_id
from backend.app.agents.agent_a.npc_dialogue_agent import generate_npc_dialogue_from_level_design


def test_build_thread_id_scope_and_isolation() -> None:
    # 1. Basic fallback (no player_id)
    assert build_thread_id("room123", "officer_miller") == "room123:officer_miller"

    # 2. Player isolation (with player_id, default scope="player")
    assert build_thread_id("room123", "officer_miller", player_id="playerA") == "room123:playerA:officer_miller"
    assert build_thread_id("room123", "officer_miller", player_id="playerB") == "room123:playerB:officer_miller"

    # 3. Room sharing (scope="room")
    assert build_thread_id("room123", "officer_miller", player_id="playerA", scope="room") == "room123:shared:officer_miller"
    assert build_thread_id("room123", "officer_miller", player_id="playerB", scope="room") == "room123:shared:officer_miller"

    # 4. Fail-fast error conditions
    with pytest.raises(ValueError, match="room_id and npc_id are required"):
        build_thread_id(None, "officer_miller")

    with pytest.raises(ValueError, match="room_id and npc_id are required"):
        build_thread_id("room123", "")


def test_generate_npc_dialogue_resolves_thread_correctly(monkeypatch) -> None:
    # We monkeypatch build_thread_id to capture the arguments it gets invoked with
    captured = []

    def mock_build_thread_id(room_id, npc_id, *, player_id=None, scope="player"):
        captured.append({
            "room_id": room_id,
            "npc_id": npc_id,
            "player_id": player_id,
            "scope": scope
        })
        return f"{room_id}:{player_id}:{npc_id}" if player_id else f"{room_id}:{npc_id}"

    monkeypatch.setattr(
        "backend.app.services.service_a.npc_short_term_memory_service.build_thread_id",
        mock_build_thread_id
    )

    # Let's mock _get_compiled_graph() invoke call to return a dummy result
    class MockGraph:
        def invoke(self, state, config):
            return {"result": {"text": "hello"}}

    monkeypatch.setattr(
        "backend.app.agents.agent_a.npc_dialogue_agent._get_compiled_graph",
        lambda: MockGraph()
    )

    payload = {
        "session_id": "session123",
        "room_id": "room456",
        "player_id": "player_foo",
        "scope": "room",
        "npc": {
            "npc_id": "officer_miller"
        }
    }

    res = generate_npc_dialogue_from_level_design(payload)
    assert res == {"text": "hello"}
    assert len(captured) == 1
    assert captured[0]["room_id"] == "room456"
    assert captured[0]["player_id"] == "player_foo"
    assert captured[0]["scope"] == "room"
    assert captured[0]["npc_id"] == "officer_miller"
