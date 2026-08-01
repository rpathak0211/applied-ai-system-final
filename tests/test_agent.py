from src.agent import recommend_with_agent

SONGS = [
    {
        "id": 1, "title": "Sunrise City", "artist": "Neon Echo", "genre": "pop",
        "mood": "happy", "energy": 0.82, "tempo_bpm": 118, "valence": 0.84,
        "danceability": 0.79, "acousticness": 0.18,
    },
    {
        "id": 3, "title": "Storm Runner", "artist": "Voltline", "genre": "rock",
        "mood": "intense", "energy": 0.91, "tempo_bpm": 152, "valence": 0.48,
        "danceability": 0.66, "acousticness": 0.10,
    },
    {
        "id": 15, "title": "Rainlight Sonata", "artist": "Elena Cho", "genre": "classical",
        "mood": "melancholy", "energy": 0.20, "tempo_bpm": 66, "valence": 0.30,
        "danceability": 0.15, "acousticness": 0.97,
    },
]


def test_confident_match_stops_after_first_attempt():
    user_prefs = {"genre": "pop", "mood": "happy", "energy": 0.8, "likes_acoustic": False}

    result = recommend_with_agent(user_prefs, SONGS, k=3)

    assert result["confident"] is True
    assert len(result["trace"]) == 1
    assert result["recommendations"][0][0]["title"] == "Sunrise City"


def test_adversarial_profile_is_flagged_not_hidden():
    # Genre+mood match (classical/melancholy) but energy is nowhere near the target,
    # the exact failure mode documented in model_card.md.
    user_prefs = {"genre": "classical", "mood": "melancholy", "energy": 0.9, "likes_acoustic": False}

    result = recommend_with_agent(user_prefs, SONGS, k=3)

    assert result["confident"] is False
    assert len(result["trace"]) == 3
    assert any("energy_mismatch" in issue for issue in result["trace"][-1]["issues"])
    # The agent re-plans by raising the energy weight on every retry.
    assert result["trace"][1]["weights"]["energy"] > result["trace"][0]["weights"]["energy"]
    assert result["trace"][2]["weights"]["energy"] > result["trace"][1]["weights"]["energy"]


def test_no_match_profile_stops_early_with_no_fixable_issue():
    # No genre/mood match exists in the catalog and energy is already within the
    # gap threshold, so raising the energy weight can't fix anything -- the agent
    # should recognize that and stop after one attempt instead of retrying blindly.
    user_prefs = {"genre": "opera", "mood": "furious", "energy": 0.5, "likes_acoustic": False}

    result = recommend_with_agent(user_prefs, SONGS, k=3)

    assert result["confident"] is False
    assert len(result["trace"]) == 1
    assert any("low_confidence" in issue for issue in result["trace"][-1]["issues"])


def test_empty_catalog_raises_value_error():
    import pytest

    with pytest.raises(ValueError):
        recommend_with_agent({"genre": "pop", "mood": "happy", "energy": 0.5, "likes_acoustic": False}, [])
