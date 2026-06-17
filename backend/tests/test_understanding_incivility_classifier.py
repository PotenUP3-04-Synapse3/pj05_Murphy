import pytest

from backend.app.services.service_c.incivility_classifier import classify_incivility_rule


@pytest.mark.parametrize(
    ("player_text", "expected_tier", "expected_category"),
    [
        ("I'm here for tourism.", 0, "none"),
        ("Please shut up for a second.", 1, "rudeness"),
        ("You idiot.", 2, "insult"),
        ("fuck you", 3, "profanity"),
        ("f*ck you", 3, "profanity"),
        ("씨발", 3, "profanity"),
    ],
)
def test_classify_incivility_rule_maps_common_tiers(
    player_text: str,
    expected_tier: int,
    expected_category: str,
) -> None:
    result = classify_incivility_rule(player_text)

    assert result.tier == expected_tier
    assert result.category == expected_category
    assert result.source == "rule"
    if expected_tier == 0:
        assert result.detected_terms == []
        assert result.confidence == 0.0
    else:
        assert result.detected_terms
        assert result.confidence > 0.0


def test_classify_incivility_rule_gives_high_confidence_to_severe_profanity() -> None:
    result = classify_incivility_rule("f**k you")

    assert result.tier == 3
    assert result.confidence >= 0.9
