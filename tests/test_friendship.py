from vaporeon_bot.friendship import build_progress_bar, friendship_level, progress_to_next_tier

def test_friendship_thresholds():
    assert [friendship_level(value).name for value in (0, 19, 20, 99, 100, 299, 300, 999, 1000)] == ["Stranger", "Stranger", "Acquaintance", "Acquaintance", "Friend", "Friend", "Best Friend", "Best Friend", "Vaporeon's Chosen Human"]

def test_progress_bar_and_max_tier():
    assert build_progress_bar(0, 4) == "░░░░"
    assert build_progress_bar(1, 4) == "████"
    assert progress_to_next_tier(1000) == 1.0
