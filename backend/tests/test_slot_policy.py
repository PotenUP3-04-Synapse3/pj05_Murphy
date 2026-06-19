from backend.app.schemas.slot_policy import get_slot_policy

def test_get_slot_policy():
    # Numeric slots
    assert get_slot_policy("stay_duration") == "numeric"
    assert get_slot_policy("cash_amount") == "closed"

    # System slots
    assert get_slot_policy("final_recommendation") == "system"

    # Open slots (default)
    assert get_slot_policy("occupation") == "open"
    assert get_slot_policy("stay_location") == "open"
    assert get_slot_policy("visit_purpose") == "open"
    assert get_slot_policy("random_non_existent_slot") == "open"
