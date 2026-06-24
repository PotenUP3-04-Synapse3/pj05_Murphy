from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.schemas.game_turn import (
    BaggageSetupRequest,
    SetupPlayerProfile,
)
from backend.app.services.service_b.baggage_room_setup_service import BaggageRoomSetupService


def test_baggage_setup_service_logic() -> None:
    service = BaggageRoomSetupService()

    # 1. Compare TSL (lower TSL wins as owner)
    p1 = SetupPlayerProfile(
        player_id="playerA",
        nickname="Alice",
        tier="Bronze",
        travel_speaking_level="TSL_1_SURVIVAL",
        total_score=3,
    )
    p2 = SetupPlayerProfile(
        player_id="playerB",
        nickname="Bob",
        tier="Silver",
        travel_speaking_level="TSL_2_FUNCTIONAL",
        total_score=6,
    )

    req = BaggageSetupRequest(room_id="room123", player1_profile=p1, player2_profile=p2)
    res = service.resolve_setup(req)
    assert res.bag_owner_player_id == "playerA"
    assert res.random_customs_item.difficulty is not None
    assert 1 <= res.random_customs_item.difficulty <= 3  # TSL_1 item has difficulty 1-3

    # Swap levels
    p1_hard = p1.model_copy(update={"travel_speaking_level": "TSL_3_INDEPENDENT"})
    req2 = BaggageSetupRequest(room_id="room123", player1_profile=p1_hard, player2_profile=p2)
    res2 = service.resolve_setup(req2)
    assert res2.bag_owner_player_id == "playerB"
    assert res2.random_customs_item.difficulty is not None
    assert 4 <= res2.random_customs_item.difficulty <= 6  # TSL_2 item has difficulty 4-6


def test_baggage_setup_service_equal_tsl_logic() -> None:
    service = BaggageRoomSetupService()

    # 2. Equal TSL -> lower total_score wins
    p1 = SetupPlayerProfile(
        player_id="playerA",
        nickname="Alice",
        tier="Silver",
        travel_speaking_level="TSL_2_FUNCTIONAL",
        total_score=4,
    )
    p2 = SetupPlayerProfile(
        player_id="playerB",
        nickname="Bob",
        tier="Silver",
        travel_speaking_level="TSL_2_FUNCTIONAL",
        total_score=5,
    )

    req = BaggageSetupRequest(room_id="room123", player1_profile=p1, player2_profile=p2)
    res = service.resolve_setup(req)
    assert res.bag_owner_player_id == "playerA"


def test_baggage_setup_service_deterministic_random() -> None:
    service = BaggageRoomSetupService()

    # 3. Equal TSL and equal total_score -> deterministic random selection based on room_id
    p1 = SetupPlayerProfile(
        player_id="playerA",
        nickname="Alice",
        tier="Silver",
        travel_speaking_level="TSL_2_FUNCTIONAL",
        total_score=5,
    )
    p2 = SetupPlayerProfile(
        player_id="playerB",
        nickname="Bob",
        tier="Silver",
        travel_speaking_level="TSL_2_FUNCTIONAL",
        total_score=5,
    )

    # Let's test two different room_ids to show different players are chosen but deterministically.
    # The output depends on the seed hash, but sorting player IDs ensures player order is identical.
    req_a = BaggageSetupRequest(room_id="room_A", player1_profile=p1, player2_profile=p2)
    req_b = BaggageSetupRequest(room_id="room_B", player1_profile=p1, player2_profile=p2)

    res_a1 = service.resolve_setup(req_a)
    res_a2 = service.resolve_setup(req_a)
    assert res_a1.bag_owner_player_id == res_a2.bag_owner_player_id

    res_b1 = service.resolve_setup(req_b)
    res_b2 = service.resolve_setup(req_b)
    assert res_b1.bag_owner_player_id == res_b2.bag_owner_player_id


def test_baggage_setup_fallback_tsl() -> None:
    service = BaggageRoomSetupService()

    # 4. Fallback TSL based on total_score
    p1 = SetupPlayerProfile(
        player_id="playerA",
        nickname="Alice",
        tier="Bronze",
        total_score=2,  # resolves to TSL_1_SURVIVAL
    )
    p2 = SetupPlayerProfile(
        player_id="playerB",
        nickname="Bob",
        tier="Silver",
        total_score=8,  # resolves to TSL_3_INDEPENDENT
    )
    req = BaggageSetupRequest(room_id="room123", player1_profile=p1, player2_profile=p2)
    res = service.resolve_setup(req)
    assert res.bag_owner_player_id == "playerA"

    # Fallback to tier
    p1_tier = SetupPlayerProfile(
        player_id="playerA",
        nickname="Alice",
        tier="Bronze",  # resolves to TSL_1_SURVIVAL
    )
    p2_tier = SetupPlayerProfile(
        player_id="playerB",
        nickname="Bob",
        tier="Gold",  # resolves to TSL_3_INDEPENDENT
    )
    req2 = BaggageSetupRequest(room_id="room123", player1_profile=p1_tier, player2_profile=p2_tier)
    res2 = service.resolve_setup(req2)
    assert res2.bag_owner_player_id == "playerA"


def test_baggage_setup_api_endpoint() -> None:
    client = TestClient(app)

    payload = {
        "room_id": "room_test_api",
        "player1_profile": {
            "player_id": "player_alice",
            "nickname": "Alice",
            "tier": "Bronze",
            "travel_speaking_level": "TSL_1_SURVIVAL",
            "total_score": 3,
        },
        "player2_profile": {
            "player_id": "player_bob",
            "nickname": "Bob",
            "tier": "Silver",
            "travel_speaking_level": "TSL_2_FUNCTIONAL",
            "total_score": 6,
        }
    }

    response = client.post("/api/game/ai/room/baggage/setup", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["room_id"] == "room_test_api"
    assert data["bag_owner_player_id"] == "player_alice"
    assert "random_customs_item" in data
    assert data["random_customs_item"]["item_id"] is not None
    assert 1 <= data["random_customs_item"]["difficulty"] <= 3
