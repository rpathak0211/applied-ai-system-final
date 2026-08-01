import csv
import logging
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Default point values for the weighted scoring recipe. Exposed as a module-level
# dict (rather than hardcoded literals) so the agentic layer (src/agent.py) can
# adjust individual weights between attempts without touching this file.
DEFAULT_WEIGHTS = {"genre": 2.0, "mood": 1.0, "energy": 1.0, "acoustic": 0.5}

@dataclass
class Song:
    """
    Represents a song and its attributes.
    Required by tests/test_recommender.py
    """
    id: int
    title: str
    artist: str
    genre: str
    mood: str
    energy: float
    tempo_bpm: float
    valence: float
    danceability: float
    acousticness: float

@dataclass
class UserProfile:
    """
    Represents a user's taste preferences.
    Required by tests/test_recommender.py
    """
    favorite_genre: str
    favorite_mood: str
    target_energy: float
    likes_acoustic: bool

class Recommender:
    """
    OOP implementation of the recommendation logic.
    Required by tests/test_recommender.py
    """
    def __init__(self, songs: List[Song]):
        self.songs = songs

    def _score(self, user: UserProfile, song: Song) -> Tuple[float, List[str]]:
        """Scores one Song against a UserProfile using the same weighted recipe as score_song."""
        score = 0.0
        reasons = []

        if user.favorite_genre == song.genre:
            score += 2.0
            reasons.append("genre match (+2.0)")

        if user.favorite_mood == song.mood:
            score += 1.0
            reasons.append("mood match (+1.0)")

        energy_points = 1.0 * (1 - abs(song.energy - user.target_energy))
        score += energy_points
        reasons.append(f"energy closeness (+{energy_points:.2f})")

        if user.likes_acoustic and song.acousticness > 0.6:
            score += 0.5
            reasons.append("acoustic bonus (+0.5)")

        return score, reasons

    def recommend(self, user: UserProfile, k: int = 5) -> List[Song]:
        """Scores every song against the user, then returns the top k highest-scoring songs."""
        ranked = sorted(self.songs, key=lambda song: self._score(user, song)[0], reverse=True)
        return ranked[:k]

    def explain_recommendation(self, user: UserProfile, song: Song) -> str:
        """Returns a human-readable, comma-separated list of the reasons this song scored what it did."""
        _, reasons = self._score(user, song)
        return ", ".join(reasons) if reasons else "no strong matches"

def load_songs(csv_path: str) -> List[Dict]:
    """Reads songs.csv into a list of dicts, converting numeric fields to float/int.

    Malformed rows (missing/non-numeric fields) are logged and skipped rather than
    crashing the whole load, so one bad row in the catalog doesn't take down the app.
    """
    logger.info("Loading songs from %s...", csv_path)
    numeric_fields = ("energy", "tempo_bpm", "valence", "danceability", "acousticness")

    songs = []
    skipped = 0
    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    row["id"] = int(row["id"])
                    for field in numeric_fields:
                        row[field] = float(row[field])
                    songs.append(row)
                except (KeyError, ValueError) as exc:
                    skipped += 1
                    logger.warning("Skipping malformed row %s: %s", row, exc)
    except FileNotFoundError:
        logger.error("Song catalog not found at %s", csv_path)
        raise

    logger.info("Loaded %d songs (%d skipped).", len(songs), skipped)
    return songs

def score_song(user_prefs: Dict, song: Dict, weights: Optional[Dict] = None) -> Tuple[float, List[str]]:
    """Scores one song against user_prefs using the weighted Algorithm Recipe
    (genre match, mood match, energy closeness, acoustic bonus).

    `weights` overrides the point value for each signal (see DEFAULT_WEIGHTS);
    this is what lets the agentic layer re-plan with different weights between
    attempts without duplicating the scoring logic.
    """
    w = weights or DEFAULT_WEIGHTS
    score = 0.0
    reasons = []

    if user_prefs.get("genre") == song["genre"]:
        score += w["genre"]
        reasons.append(f"genre match (+{w['genre']:.2f})")

    if user_prefs.get("mood") == song["mood"]:
        score += w["mood"]
        reasons.append(f"mood match (+{w['mood']:.2f})")

    target_energy = user_prefs.get("energy")
    if target_energy is not None:
        energy_points = w["energy"] * (1 - abs(song["energy"] - target_energy))
        score += energy_points
        reasons.append(f"energy closeness (+{energy_points:.2f})")

    if user_prefs.get("likes_acoustic") and song["acousticness"] > 0.6:
        score += w["acoustic"]
        reasons.append(f"acoustic bonus (+{w['acoustic']:.2f})")

    return score, reasons

def recommend_songs(
    user_prefs: Dict, songs: List[Dict], k: int = 5, weights: Optional[Dict] = None
) -> List[Tuple[Dict, float, str]]:
    """Scores every song, then returns the top k sorted highest-score-first."""
    if not songs:
        raise ValueError("Cannot recommend songs: the catalog is empty.")

    scored = []
    for song in songs:
        score, reasons = score_song(user_prefs, song, weights=weights)
        explanation = ", ".join(reasons) if reasons else "no strong matches"
        scored.append((song, score, explanation))

    ranked = sorted(scored, key=lambda entry: entry[1], reverse=True)
    return ranked[:k]
