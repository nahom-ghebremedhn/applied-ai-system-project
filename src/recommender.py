import csv
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict

# Highest score score_song() can give: genre 1.5 + mood 1.0 + energy 2.0 + acoustic 0.5
MAX_SCORE = 5.0

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

    def recommend(self, user: UserProfile, k: int = 5) -> List[Song]:
        """Returns the top k Song objects, ranked by the same score_song() rules the CLI uses."""
        # asdict() turns the dataclasses into the plain dicts score_song() expects.
        # The UserProfile field names match the user_prefs keys exactly.
        user_prefs = asdict(user)
        ranked = sorted(
            self.songs,
            key=lambda song: score_song(user_prefs, asdict(song))[0],
            reverse=True,
        )
        return ranked[:k]

    def explain_recommendation(self, user: UserProfile, song: Song) -> str:
        """Explains a song's score using the reasons produced by score_song()."""
        score, reasons = score_song(asdict(user), asdict(song))
        return f"Score {score:.2f} / {MAX_SCORE:.2f}: " + ", ".join(reasons)

def load_songs(csv_path: str) -> List[Dict]:
    """Reads the songs CSV into a list of dicts, converting numeric columns to int/float."""
    int_fields = {"id"}
    float_fields = {"energy", "tempo_bpm", "valence", "danceability", "acousticness"}

    songs: List[Dict] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            song: Dict = {}
            for key, value in row.items():
                key = key.strip()
                value = value.strip() if value is not None else value
                if key in int_fields:
                    song[key] = int(value)
                elif key in float_fields:
                    song[key] = float(value)
                else:
                    song[key] = value
            songs.append(song)

    return songs

def score_song(user_prefs: Dict, song: Dict) -> Tuple[float, List[str]]:
    """Scores one song against the user's preferences and returns (score, reasons)."""
    score = 0.0
    reasons: List[str] = []

    # Genre match: +1.5 (long-term, stable taste; lowered from 2.0 so it can't override everything else)
    if song["genre"].lower() == user_prefs["favorite_genre"].lower():
        score += 1.5
        reasons.append("genre match (+1.5)")

    # Mood match: +1.0 (situational, weighted below genre)
    if song["mood"].lower() == user_prefs["favorite_mood"].lower():
        score += 1.0
        reasons.append("mood match (+1.0)")

    # Energy closeness: up to +2.0, scaled by how close the song is to the target.
    # Floored at 0 so an out-of-range target (e.g. 1.5) can't subtract points.
    # Max total stays 1.5 + 1.0 + 2.0 + 0.5 = 5.0.
    energy_points = max(0.0, 2.0 * (1 - abs(song["energy"] - user_prefs["target_energy"])))
    score += energy_points
    reasons.append(f"energy close to target (+{energy_points:.2f})")

    # Acoustic fit: +0.5 tiebreaker for the user's sound preference
    is_acoustic = song["acousticness"] > 0.6
    if is_acoustic == user_prefs["likes_acoustic"]:
        score += 0.5
        label = "acoustic" if is_acoustic else "produced (non-acoustic)"
        reasons.append(f"{label} sound fits preference (+0.5)")

    return score, reasons

def recommend_songs(user_prefs: Dict, songs: List[Dict], k: int = 5) -> List[Tuple[Dict, float, str]]:
    """Scores every song, sorts highest first, and returns the top k as (song, score, explanation)."""
    # Judge every song with score_song, rank highest first, keep the top k.
    # sorted() builds a new list, so the caller's catalog is never reordered.
    scored = (
        (song, score, ", ".join(reasons))
        for song in songs
        for score, reasons in [score_song(user_prefs, song)]
    )
    return sorted(scored, key=lambda item: item[1], reverse=True)[:k]
