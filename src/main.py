"""
Command line runner for the Music Recommender Simulation.

This file helps you quickly run and test your recommender.

You will implement the functions in recommender.py:
- load_songs
- score_song
- recommend_songs
"""

import logging
import os

from .agent import recommend_with_agent
from .recommender import load_songs

LOG_DIR = "logs"
LOG_PATH = os.path.join(LOG_DIR, "app.log")


def configure_logging() -> None:
    """Logs to both the console and logs/app.log so every run's decisions are traceable."""
    os.makedirs(LOG_DIR, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()],
    )

# Stress-test profiles: three "normal" tastes plus one adversarial profile with
# conflicting signals (high target energy paired with a low-energy, melancholy
# genre/mood) to see how the scoring rule behaves when there's no clean match.
PROFILES = {
    "High-Energy Pop": {"genre": "pop", "mood": "happy", "energy": 0.9, "likes_acoustic": False},
    "Chill Lofi": {"genre": "lofi", "mood": "chill", "energy": 0.3, "likes_acoustic": True},
    "Deep Intense Rock": {"genre": "rock", "mood": "intense", "energy": 0.85, "likes_acoustic": False},
    "Adversarial: High-Energy Melancholy": {
        "genre": "classical",
        "mood": "melancholy",
        "energy": 0.9,
        "likes_acoustic": False,
    },
}


def print_recommendations(profile_name: str, user_prefs: dict, songs, k: int = 5) -> None:
    result = recommend_with_agent(user_prefs, songs, k=k)
    recommendations = result["recommendations"]

    print(f"\n=== {profile_name} ===")
    print(f"User profile: {user_prefs}")
    print(f"Confidence: {result['confidence_score']:.2f}")

    if not result["confident"]:
        last_issues = result["trace"][-1]["issues"]
        print(f"\n⚠️  Low confidence after {len(result['trace'])} attempt(s): {'; '.join(last_issues)}")

    print("\nTop recommendations:\n")
    for rank, (song, score, explanation) in enumerate(recommendations, start=1):
        print(f"{rank}. {song['title']} — {song['artist']} ({song['genre']}/{song['mood']})")
        print(f"   Score: {score:.2f}")
        print(f"   Because: {explanation}")
        print()


def main() -> None:
    configure_logging()
    logger = logging.getLogger(__name__)

    try:
        songs = load_songs("data/songs.csv")
    except FileNotFoundError:
        logger.error("Could not find data/songs.csv — run this script from the project root.")
        return

    for profile_name, user_prefs in PROFILES.items():
        try:
            print_recommendations(profile_name, user_prefs, songs, k=5)
        except ValueError as exc:
            logger.error("Skipping profile %r: %s", profile_name, exc)


if __name__ == "__main__":
    main()
