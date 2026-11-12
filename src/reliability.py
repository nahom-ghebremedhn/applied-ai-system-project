"""
Reliability and evaluation layer for the Music Recommender Simulation.

The recommender itself is rule-based (see score_song() in recommender.py).
This module never changes how songs are scored. It adds three kinds of checks
around the existing scoring engine:

1. Validation  - are the user preferences and song data usable?
2. Verification - are the scores and the ranking calculated correctly?
3. Evaluation  - how well do the recommended songs match the user's preferences?

Every check returns a list of Issue objects. An "error" means the input or
result can't be trusted. A "warning" means it works but may surprise the user.
"""

import csv
import math
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# Works both as part of the "src" package (pytest, python -m src.main)
# and as a plain module next to main.py (python src/main.py).
try:
    from .recommender import MAX_SCORE, score_song
except ImportError:
    from recommender import MAX_SCORE, score_song


# ---------------------------------------------------------------------------
# Issues
# ---------------------------------------------------------------------------

ERROR = "error"
WARNING = "warning"


@dataclass
class Issue:
    """One problem found by a check. level is ERROR or WARNING."""
    level: str
    message: str

    def __str__(self) -> str:
        return f"{self.level.upper()}: {self.message}"


def has_errors(issues: List[Issue]) -> bool:
    """True if any issue in the list is an error."""
    return any(issue.level == ERROR for issue in issues)


def count_level(issues: List[Issue], level: str) -> int:
    """Counts how many issues have the given level."""
    return sum(1 for issue in issues if issue.level == level)


def _is_number(value) -> bool:
    """True for int/float values. bool is excluded even though Python treats it as an int."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


# ---------------------------------------------------------------------------
# 1. Validation: user preferences
# ---------------------------------------------------------------------------

TEXT_PREF_KEYS = ("favorite_genre", "favorite_mood")
REQUIRED_PREF_KEYS = ("favorite_genre", "favorite_mood", "target_energy", "likes_acoustic")


def _check_text_pref(key: str, value: str, catalog_values: Optional[set]) -> List[Issue]:
    """Checks one text preference (genre or mood). Only ever returns warnings."""
    label = key.replace("favorite_", "")
    issues: List[Issue] = []

    if value.strip() == "":
        issues.append(Issue(WARNING, f"{key} is empty, so no song can earn the {label} bonus."))
        return issues

    if value != value.strip():
        issues.append(Issue(
            WARNING,
            f"{key} {value!r} has extra spaces. Scoring compares the text exactly "
            f"(ignoring case), so it will NOT match {value.strip().lower()!r} songs.",
        ))

    cleaned = value.strip()
    if cleaned != cleaned.lower():
        issues.append(Issue(
            WARNING,
            f"{key} {value!r} has unusual capitalization. Scoring ignores case, "
            f"so it is treated as {cleaned.lower()!r}.",
        ))

    if catalog_values is not None and cleaned.lower() not in catalog_values:
        issues.append(Issue(
            WARNING,
            f"{key} {cleaned!r} does not appear in the catalog, "
            f"so no song can earn the {label} bonus.",
        ))

    return issues


def validate_user_prefs(user_prefs: Dict, songs: Optional[List[Dict]] = None) -> List[Issue]:
    """
    Checks a user_prefs dict before it is scored.

    Errors (recommendations would be misleading or crash):
      - a required key is missing, or a value has the wrong type
      - target_energy is outside 0.0-1.0 (song energy is always 0.0-1.0)
    Warnings (recommendations still work but may surprise the user):
      - empty genre/mood, extra spaces, unusual capitalization
      - genre/mood not found in the catalog (only checked when songs are given)
      - unknown extra keys, which the recommender ignores
    """
    if not isinstance(user_prefs, dict):
        return [Issue(ERROR, f"user preferences must be a dict, got {type(user_prefs).__name__}.")]

    issues: List[Issue] = []

    for key in REQUIRED_PREF_KEYS:
        if key not in user_prefs:
            issues.append(Issue(ERROR, f"missing required preference {key!r}."))

    for key in sorted(set(user_prefs) - set(REQUIRED_PREF_KEYS)):
        issues.append(Issue(WARNING, f"unknown preference {key!r} is ignored by the recommender."))

    # Genre and mood
    for key in TEXT_PREF_KEYS:
        if key not in user_prefs:
            continue
        value = user_prefs[key]
        if not isinstance(value, str):
            issues.append(Issue(ERROR, f"{key} must be text, got {value!r}."))
            continue
        catalog_values = None
        if songs is not None:
            field = key.replace("favorite_", "")
            catalog_values = {str(song.get(field, "")).strip().lower() for song in songs}
        issues.extend(_check_text_pref(key, value, catalog_values))

    # Target energy
    if "target_energy" in user_prefs:
        energy = user_prefs["target_energy"]
        if not _is_number(energy) or math.isnan(energy):
            issues.append(Issue(ERROR, f"target_energy must be a number, got {energy!r}."))
        elif not 0.0 <= energy <= 1.0:
            issues.append(Issue(
                ERROR,
                f"target_energy {energy} is outside 0.0-1.0. Every song's energy is in that "
                f"range, so the loudest or quietest songs would look 'closest' by mistake.",
            ))

    # Acoustic preference
    if "likes_acoustic" in user_prefs and not isinstance(user_prefs["likes_acoustic"], bool):
        issues.append(Issue(
            ERROR,
            f"likes_acoustic must be True or False, got {user_prefs['likes_acoustic']!r}.",
        ))

    return issues


# ---------------------------------------------------------------------------
# 1. Validation: song data
# ---------------------------------------------------------------------------

SONG_TEXT_FIELDS = ("title", "artist", "genre", "mood")
SONG_UNIT_FIELDS = ("energy", "valence", "danceability", "acousticness")  # must be 0.0-1.0
SONG_FIELDS = ("id",) + SONG_TEXT_FIELDS + ("energy", "tempo_bpm", "valence", "danceability", "acousticness")


def validate_song(song: Dict, label: str = "song") -> List[Issue]:
    """
    Checks one song dict (already converted to numbers, like load_songs() returns).

    Errors: missing or blank fields, wrong types, values outside their valid range.
    Warnings: extra spaces in genre/mood, which would stop them from matching.
    """
    issues: List[Issue] = []

    for field in SONG_FIELDS:
        if field not in song or song[field] is None:
            issues.append(Issue(ERROR, f"{label}: missing field {field!r}."))

    if "id" in song and song["id"] is not None:
        if not isinstance(song["id"], int) or isinstance(song["id"], bool):
            issues.append(Issue(ERROR, f"{label}: id must be a whole number, got {song['id']!r}."))

    for field in SONG_TEXT_FIELDS:
        value = song.get(field)
        if value is None:
            continue
        if not isinstance(value, str) or value.strip() == "":
            issues.append(Issue(ERROR, f"{label}: {field} must be non-empty text, got {value!r}."))
        elif field in ("genre", "mood") and value != value.strip():
            issues.append(Issue(WARNING, f"{label}: {field} {value!r} has extra spaces and will not match user preferences."))

    for field in SONG_UNIT_FIELDS:
        value = song.get(field)
        if value is None:
            continue
        if not _is_number(value) or math.isnan(value):
            issues.append(Issue(ERROR, f"{label}: {field} must be a number, got {value!r}."))
        elif not 0.0 <= value <= 1.0:
            issues.append(Issue(ERROR, f"{label}: {field} {value} is outside 0.0-1.0."))

    tempo = song.get("tempo_bpm")
    if tempo is not None:
        if not _is_number(tempo) or math.isnan(tempo):
            issues.append(Issue(ERROR, f"{label}: tempo_bpm must be a number, got {tempo!r}."))
        elif not 0 < tempo < math.inf:
            issues.append(Issue(ERROR, f"{label}: tempo_bpm {tempo} must be a positive number."))

    return issues


def validate_catalog(songs: List[Dict]) -> List[Issue]:
    """Checks every song in the catalog, plus catalog-wide rules (not empty, unique ids)."""
    if not songs:
        return [Issue(ERROR, "the song catalog is empty.")]

    issues: List[Issue] = []
    seen_ids = set()
    for position, song in enumerate(songs, start=1):
        label = f"song #{position} ({song.get('title', 'untitled')})"
        issues.extend(validate_song(song, label))
        song_id = song.get("id")
        if song_id in seen_ids:
            issues.append(Issue(ERROR, f"{label}: duplicate id {song_id}."))
        seen_ids.add(song_id)
    return issues


def load_songs_safely(csv_path: str) -> Tuple[List[Dict], List[Issue]]:
    """
    Loads the songs CSV like load_songs(), but never crashes on a bad row.

    Each bad row is skipped and reported as an error. Good rows come back exactly
    as load_songs() would return them. Returns (valid_songs, issues).
    A missing file still raises FileNotFoundError, because there is nothing to recover.
    """
    songs: List[Dict] = []
    issues: List[Issue] = []
    seen_ids = set()

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        header = [name.strip() for name in (reader.fieldnames or [])]
        missing_columns = [field for field in SONG_FIELDS if field not in header]
        if missing_columns:
            issues.append(Issue(ERROR, f"CSV is missing column(s): {', '.join(missing_columns)}."))

        for row in reader:
            label = f"line {reader.line_num}"
            song, row_issues = _convert_row(row, label)
            if song is not None:
                row_issues.extend(validate_song(song, label))
                if song.get("id") in seen_ids:
                    row_issues.append(Issue(ERROR, f"{label}: duplicate id {song['id']}."))

            issues.extend(row_issues)
            if song is None or has_errors(row_issues):
                issues.append(Issue(ERROR, f"{label}: row skipped."))
                continue

            seen_ids.add(song["id"])
            songs.append(song)

    return songs, issues


def _convert_row(row: Dict, label: str) -> Tuple[Optional[Dict], List[Issue]]:
    """Turns one raw CSV row into a song dict. Returns (None, issues) if a number can't be read."""
    song: Dict = {}
    issues: List[Issue] = []
    for key, value in row.items():
        if key is None:  # the row has more values than the header has columns
            issues.append(Issue(ERROR, f"{label}: has more values than there are columns."))
            continue
        key = key.strip()
        value = value.strip() if value is not None else None
        if value is None or value == "":
            song[key] = None  # reported as a missing field by validate_song()
        elif key == "id":
            try:
                song[key] = int(value)
            except ValueError:
                issues.append(Issue(ERROR, f"{label}: id {value!r} is not a whole number."))
        elif key in ("energy", "tempo_bpm", "valence", "danceability", "acousticness"):
            try:
                song[key] = float(value)
            except ValueError:
                issues.append(Issue(ERROR, f"{label}: {key} {value!r} is not a number."))
        else:
            song[key] = value

    if has_errors(issues):
        return None, issues
    return song, issues


# ---------------------------------------------------------------------------
# 2. Verification: scores and rankings
# ---------------------------------------------------------------------------

# Every reason from score_song() ends with its points, e.g. "mood match (+1.0)".
REASON_POINTS = re.compile(r"\(\+(\d+(?:\.\d+)?)\)$")

# The energy reason is printed with 2 decimals, so the sum of the printed points
# can differ from the real score by up to 0.005. 0.01 leaves a safe margin.
REASON_SUM_TOLERANCE = 0.01


def check_score(user_prefs: Dict, song: Dict, score: float, reasons: List[str]) -> List[Issue]:
    """
    Sanity-checks one (score, reasons) pair produced by score_song().

    - the score is between 0 and MAX_SCORE
    - the points listed in the reasons add up to the score
    - "genre match" / "mood match" appear exactly when the labels really match
      (an independent cross-check of the scoring rules)
    """
    title = song.get("title", "song")
    issues: List[Issue] = []

    if not 0.0 <= score <= MAX_SCORE:
        issues.append(Issue(ERROR, f"{title}: score {score} is outside 0-{MAX_SCORE}."))

    listed_points = 0.0
    for reason in reasons:
        match = REASON_POINTS.search(reason)
        if match is None:
            issues.append(Issue(ERROR, f"{title}: reason {reason!r} does not list its points."))
        else:
            listed_points += float(match.group(1))
    if abs(listed_points - score) > REASON_SUM_TOLERANCE:
        issues.append(Issue(
            ERROR,
            f"{title}: reasons add up to {listed_points:.2f} but the score is {score:.2f}.",
        ))

    for field, reason_start in (("genre", "genre match"), ("mood", "mood match")):
        labels_match = song[field].lower() == user_prefs[f"favorite_{field}"].lower()
        reason_given = any(reason.startswith(reason_start) for reason in reasons)
        if labels_match != reason_given:
            issues.append(Issue(
                ERROR,
                f"{title}: {field} match is {labels_match} but the reasons say {reason_given}.",
            ))

    return issues


def check_recommendations(
    user_prefs: Dict, songs: List[Dict], results: List[Tuple[Dict, float, str]], k: int
) -> List[Issue]:
    """
    Verifies the output of recommend_songs(user_prefs, songs, k).

    - the right number of results: min(k, catalog size)
    - each score and explanation is exactly what score_song() gives
    - each score passes check_score()
    - results are sorted from highest to lowest score, with no repeated song
    - nothing left out of the top k scores higher than something kept in it
    """
    issues: List[Issue] = []

    expected_count = min(k, len(songs))
    if len(results) != expected_count:
        issues.append(Issue(ERROR, f"expected {expected_count} recommendations, got {len(results)}."))

    for song, score, explanation in results:
        expected_score, reasons = score_song(user_prefs, song)
        if score != expected_score:
            issues.append(Issue(
                ERROR,
                f"{song['title']}: reported score {score} but score_song() gives {expected_score}.",
            ))
        if explanation != ", ".join(reasons):
            issues.append(Issue(ERROR, f"{song['title']}: explanation does not match score_song() reasons."))
        issues.extend(check_score(user_prefs, song, expected_score, reasons))

    scores = [score for _, score, _ in results]
    if any(scores[i] < scores[i + 1] for i in range(len(scores) - 1)):
        issues.append(Issue(ERROR, f"results are not sorted from highest to lowest score: {scores}."))

    result_ids = [song["id"] for song, _, _ in results]
    if len(result_ids) != len(set(result_ids)):
        issues.append(Issue(ERROR, "the same song appears more than once in the results."))

    if scores:
        left_out = [song for song in songs if song["id"] not in set(result_ids)]
        lowest_kept = min(scores)
        for song in left_out:
            left_out_score, _ = score_song(user_prefs, song)
            if left_out_score > lowest_kept:
                issues.append(Issue(
                    ERROR,
                    f"{song['title']} scores {left_out_score:.2f} but was left out of the top {k}, "
                    f"which includes a song scoring {lowest_kept:.2f}.",
                ))

    return issues


# ---------------------------------------------------------------------------
# 3. Evaluation: how well do the recommendations match the preferences?
# ---------------------------------------------------------------------------

# A song's energy "matches" when it is within this distance of target_energy.
ENERGY_TOLERANCE = 0.2
# Tiny allowance so 0.8 - 0.6 (= 0.20000000000000007 in floating point) still counts.
_FLOAT_EPSILON = 1e-9
# A song is "relevant" when it matches at least this many of the 4 preferences.
# 3 is used instead of 2 because energy and acoustic fit usually match together
# in this catalog (quiet songs are acoustic, loud songs are produced). With 2,
# almost every top-5 list scored a perfect 1.00, so the metric told us nothing.
RELEVANCE_THRESHOLD = 3


def preference_matches(user_prefs: Dict, song: Dict) -> Dict[str, bool]:
    """
    Which of the user's 4 preferences does this song satisfy?

    genre, mood and acoustic are read from the reasons score_song() gives,
    so this always agrees with the scoring rules without repeating them.
    energy counts as a match when |song energy - target_energy| <= ENERGY_TOLERANCE.
    """
    _, reasons = score_song(user_prefs, song)
    return {
        "genre": any(reason.startswith("genre match") for reason in reasons),
        "mood": any(reason.startswith("mood match") for reason in reasons),
        "energy": abs(song["energy"] - user_prefs["target_energy"]) <= ENERGY_TOLERANCE + _FLOAT_EPSILON,
        "acoustic": any("sound fits preference" in reason for reason in reasons),
    }


def is_relevant(user_prefs: Dict, song: Dict) -> bool:
    """A song is relevant when it matches at least RELEVANCE_THRESHOLD of the 4 preferences."""
    return sum(preference_matches(user_prefs, song).values()) >= RELEVANCE_THRESHOLD


def evaluate_recommendations(
    user_prefs: Dict, results: List[Tuple[Dict, float, str]], songs: Optional[List[Dict]] = None
) -> Dict:
    """
    Measures how well a list of recommendations matches the user's preferences.

    k is the number of recommendations actually returned. All rates are 0.0-1.0.
      precision_at_k   = (relevant songs in the results) / k
      genre_match_rate = (results whose genre matches) / k      (same idea for mood,
      energy_match_rate, acoustic_fit_rate)
      avg_energy_gap   = average |song energy - target_energy| (lower is better)
      avg_score_pct    = average score as a percentage of MAX_SCORE
      unique_artists / unique_genres = variety in the results
    When the full catalog is given, also:
      relevant_in_catalog    = relevant songs available in the whole catalog
      best_possible_precision = min(relevant_in_catalog, k) / k, the highest
                               precision any top-k list could reach with this catalog

    Returns None for every metric when there are no results (dividing by k = 0
    is undefined).
    """
    k = len(results)
    metric_names = (
        "precision_at_k", "genre_match_rate", "mood_match_rate", "energy_match_rate",
        "acoustic_fit_rate", "avg_energy_gap", "avg_score_pct", "unique_artists",
        "unique_genres", "relevant_in_catalog", "best_possible_precision",
    )
    if k == 0:
        return {"k": 0, **{name: None for name in metric_names}}

    recommended = [song for song, _, _ in results]
    matches = [preference_matches(user_prefs, song) for song in recommended]

    def rate(key: str) -> float:
        return sum(1 for m in matches if m[key]) / k

    relevant_count = sum(1 for m in matches if sum(m.values()) >= RELEVANCE_THRESHOLD)
    metrics = {
        "k": k,
        "precision_at_k": relevant_count / k,
        "genre_match_rate": rate("genre"),
        "mood_match_rate": rate("mood"),
        "energy_match_rate": rate("energy"),
        "acoustic_fit_rate": rate("acoustic"),
        "avg_energy_gap": sum(abs(s["energy"] - user_prefs["target_energy"]) for s in recommended) / k,
        "avg_score_pct": 100 * sum(score for _, score, _ in results) / (k * MAX_SCORE),
        "unique_artists": len({s["artist"] for s in recommended}),
        "unique_genres": len({s["genre"] for s in recommended}),
        "relevant_in_catalog": None,
        "best_possible_precision": None,
    }

    if songs is not None:
        relevant_in_catalog = sum(1 for song in songs if is_relevant(user_prefs, song))
        metrics["relevant_in_catalog"] = relevant_in_catalog
        metrics["best_possible_precision"] = min(relevant_in_catalog, k) / k

    return metrics
