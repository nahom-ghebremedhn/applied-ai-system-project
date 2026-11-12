"""
Command line runner for the Music Recommender Simulation.

This file helps you quickly run and test your recommender.

You will implement the functions in recommender.py:
- load_songs
- score_song
- recommend_songs
"""

import sys
import textwrap
from pathlib import Path

# Supports both run commands:
#   python -m src.main  -> "src" is a package, so use relative imports
#   python src/main.py  -> src/ is on the path, so import the modules directly
try:
    from .recommender import MAX_SCORE, recommend_songs
    from .reliability import (
        ERROR, RELEVANCE_THRESHOLD, WARNING, check_recommendations, count_level, evaluate_recommendations,
        has_errors, load_songs_safely, validate_user_prefs,
    )
except ImportError:
    from recommender import MAX_SCORE, recommend_songs
    from reliability import (
        ERROR, RELEVANCE_THRESHOLD, WARNING, check_recommendations, count_level, evaluate_recommendations,
        has_errors, load_songs_safely, validate_user_prefs,
    )

# Found relative to this file, so the app works from any folder.
DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "songs.csv"
K = 5


def main() -> int:
    """Runs every profile, then prints the evaluation summary. Returns the exit code."""
    try:
        songs, catalog_issues = load_songs_safely(str(DATA_PATH))
    except FileNotFoundError:
        print(f"ERROR: could not find the song catalog at {DATA_PATH}")
        return 1

    print(f"Loaded songs: {len(songs)}")
    print_catalog_check(songs, catalog_issues)
    if not songs:
        print("ERROR: no valid songs to recommend from. Fix the catalog and try again.")
        return 1

    rows = [run_profile(name, user_prefs, songs) for name, user_prefs in PROFILES.items()]
    print_evaluation_summary(rows)

    # A failed check means a bug in the scoring or ranking code, not bad input.
    return 1 if any(row["checks"] == "FAIL" for row in rows) else 0


def run_profile(name: str, user_prefs: dict, songs: list) -> dict:
    """Validates, recommends, verifies and evaluates one profile. Returns its summary row."""
    input_issues = validate_user_prefs(user_prefs, songs)
    row = {"name": name, "input": "OK", "checks": "-", "metrics": None}

    if has_errors(input_issues):
        # Don't show recommendations that would be misleading.
        print_skipped_profile(name, user_prefs, input_issues)
        row["input"] = "ERROR"
        return row

    warning_count = count_level(input_issues, WARNING)
    if warning_count:
        row["input"] = f"WARN({warning_count})"

    recommendations = recommend_songs(user_prefs, songs, k=K)
    print_recommendations(name, user_prefs, recommendations, input_issues)

    check_issues = check_recommendations(user_prefs, songs, recommendations, K)
    row["checks"] = "FAIL" if check_issues else "PASS"
    for issue in check_issues:
        print(f" CHECK FAILED: {issue.message}")

    row["metrics"] = evaluate_recommendations(user_prefs, recommendations, songs)
    return row


# Distinct taste profiles used to test the recommender
PROFILES = {
    # Upbeat pop listener who prefers produced (non-acoustic) songs
    "High-Energy Pop": {
        "favorite_genre": "pop",
        "favorite_mood": "happy",
        "target_energy": 0.8,
        "likes_acoustic": False,
    },
    # Low-key study music: mellow, acoustic-leaning lofi
    "Chill Lofi": {
        "favorite_genre": "lofi",
        "favorite_mood": "chill",
        "target_energy": 0.35,
        "likes_acoustic": True,
    },
    # Loud, driving rock with heavy production
    "Deep Intense Rock": {
        "favorite_genre": "rock",
        "favorite_mood": "intense",
        "target_energy": 0.9,
        "likes_acoustic": False,
    },
    # --- Adversarial / edge-case profiles (system evaluation) ---
    # Mood that no song in the catalog has, paired with high energy
    "Sad Gym Rat": {
        "favorite_genre": "pop",
        "favorite_mood": "sad",
        "target_energy": 0.9,
        "likes_acoustic": False,
    },
    # Extra whitespace / casing in preferences
    "Whitespace Pop": {
        "favorite_genre": " Pop ",
        "favorite_mood": "HAPPY",
        "target_energy": 0.8,
        "likes_acoustic": False,
    },
    # Energy outside the 0-1 range
    "Overdrive": {
        "favorite_genre": "lofi",
        "favorite_mood": "chill",
        "target_energy": 1.5,
        "likes_acoustic": True,
    },
    # Genre whose only song contradicts every other preference
    "Contradictory Classical": {
        "favorite_genre": "classical",
        "favorite_mood": "chill",
        "target_energy": 0.95,
        "likes_acoustic": False,
    },
    # Genre with a single song in the catalog
    "Acoustic Metal": {
        "favorite_genre": "metal",
        "favorite_mood": "angry",
        "target_energy": 0.97,
        "likes_acoustic": True,
    },
    # Close cousin of "pop" that only matches exactly
    "Indie Pop Fan": {
        "favorite_genre": "indie pop",
        "favorite_mood": "happy",
        "target_energy": 0.76,
        "likes_acoustic": False,
    },
    # No genre or mood given
    "No Preferences": {
        "favorite_genre": "",
        "favorite_mood": "",
        "target_energy": 0.5,
        "likes_acoustic": False,
    },
}


WIDTH = 60


def print_issue_list(issues: list, indent: str = "   ") -> None:
    """Prints issues wrapped to the report width, e.g. "   ! WARNING: ..." """
    for issue in issues:
        print(textwrap.fill(
            str(issue), width=WIDTH, initial_indent=f"{indent}! ", subsequent_indent=f"{indent}  "
        ))


def print_catalog_check(songs: list, issues: list) -> None:
    """Reports the result of validating songs.csv."""
    errors = count_level(issues, ERROR)
    warnings = count_level(issues, WARNING)
    print(f"Catalog check: {len(songs)} valid songs, {errors} errors, {warnings} warnings")
    print_issue_list(issues)


def print_skipped_profile(name: str, user_prefs: dict, issues: list) -> None:
    """Explains why a profile got no recommendations."""
    print()
    print("=" * WIDTH)
    print(f" TOP RECOMMENDATIONS: {name}".center(WIDTH))
    print("=" * WIDTH)
    print(f" Profile: {user_prefs}")
    print(" NO RECOMMENDATIONS: the profile has invalid input.")
    print_issue_list(issues)
    print("-" * WIDTH)


def print_recommendations(name: str, user_prefs: dict, recommendations: list, issues: list = ()) -> None:
    """Prints the ranked recommendations as a readable terminal report."""
    acoustic = "acoustic" if user_prefs["likes_acoustic"] else "produced"
    print()
    print("=" * WIDTH)
    print(f" TOP RECOMMENDATIONS: {name}".center(WIDTH))
    print("=" * WIDTH)
    print(
        f" Profile: {user_prefs['favorite_genre']} | {user_prefs['favorite_mood']} | "
        f"energy {user_prefs['target_energy']:.2f} | {acoustic}"
    )
    if issues:
        print(" Input warnings:")
        print_issue_list(issues)
    print("-" * WIDTH)

    for rank, (song, score, explanation) in enumerate(recommendations, start=1):
        print(f" #{rank}  {song['title']}  by {song['artist']}")
        print(f"     Score: {score:.2f} / {MAX_SCORE:.2f}")
        print("     Why:")
        for reason in explanation.split(", "):
            print(f"       - {reason}")
        print("-" * WIDTH)


def _fmt(value, pattern: str) -> str:
    """Formats a metric, or shows "-" when it doesn't exist (skipped profile)."""
    return "-" if value is None else format(value, pattern)


def print_evaluation_summary(rows: list) -> None:
    """Prints one compact line of metrics per profile, plus a short legend."""
    columns = f"{'Profile':<24}{'Input':<9}{'P@' + str(K):>5}{'Best':>6}{'Genre':>6}{'Mood':>6}{'Enrg':>6}{'Acou':>6}{'Gap':>6}{'Score':>7}  Checks"
    print()
    print("=" * len(columns))
    print(" EVALUATION SUMMARY".center(len(columns)))
    print("=" * len(columns))
    print(columns)
    print("-" * len(columns))
    for row in rows:
        m = row["metrics"] or {}
        print(
            f"{row['name']:<24}{row['input']:<9}"
            f"{_fmt(m.get('precision_at_k'), '.2f'):>5}"
            f"{_fmt(m.get('best_possible_precision'), '.2f'):>6}"
            f"{_fmt(m.get('genre_match_rate'), '.2f'):>6}"
            f"{_fmt(m.get('mood_match_rate'), '.2f'):>6}"
            f"{_fmt(m.get('energy_match_rate'), '.2f'):>6}"
            f"{_fmt(m.get('acoustic_fit_rate'), '.2f'):>6}"
            f"{_fmt(m.get('avg_energy_gap'), '.2f'):>6}"
            f"{_fmt(m.get('avg_score_pct'), '.0f') + ('%' if m else ''):>7}"
            f"  {row['checks']}"
        )
    print("-" * len(columns))
    print(f" P@{K}: share of the top {K} matching at least {RELEVANCE_THRESHOLD} of the 4 preferences")
    print("       (genre, mood, energy within 0.2, acoustic fit).")
    print(f" Best: highest P@{K} this catalog allows. Genre/Mood/Enrg/Acou: match rates.")
    print(" Gap: average |energy - target|. Score: average score as % of the max.")
    print(" Input: OK, WARN(n) warnings, or ERROR (profile skipped).")
    print(" Checks: PASS if scores, explanations and ranking were verified.")


if __name__ == "__main__":
    sys.exit(main())
