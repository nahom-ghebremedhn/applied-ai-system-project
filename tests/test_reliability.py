import subprocess
import sys
from pathlib import Path

import pytest

from src.main import PROFILES
from src.recommender import MAX_SCORE, load_songs, recommend_songs, score_song
from src.reliability import (
    ERROR,
    WARNING,
    Issue,
    check_recommendations,
    check_score,
    evaluate_recommendations,
    has_errors,
    is_relevant,
    load_songs_safely,
    preference_matches,
    validate_catalog,
    validate_song,
    validate_user_prefs,
)

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "data" / "songs.csv"
CSV_HEADER = "id,title,artist,genre,mood,energy,tempo_bpm,valence,danceability,acousticness\n"

GOOD_PREFS = {
    "favorite_genre": "pop",
    "favorite_mood": "happy",
    "target_energy": 0.8,
    "likes_acoustic": False,
}


def make_song(**overrides) -> dict:
    song = {
        "id": 1, "title": "Test Song", "artist": "Test Artist", "genre": "pop", "mood": "happy",
        "energy": 0.8, "tempo_bpm": 120.0, "valence": 0.9, "danceability": 0.8, "acousticness": 0.2,
    }
    song.update(overrides)
    return song


def messages(issues, level=None) -> str:
    """All issue messages joined together, so tests can search them for a keyword."""
    return " | ".join(i.message for i in issues if level is None or i.level == level)


@pytest.fixture
def catalog():
    return load_songs(str(CSV_PATH))


# ---------------------------------------------------------------------------
# Validation: user preferences
# ---------------------------------------------------------------------------

def test_valid_prefs_have_no_issues(catalog):
    assert validate_user_prefs(GOOD_PREFS, catalog) == []


def test_missing_preference_is_an_error():
    prefs = {k: v for k, v in GOOD_PREFS.items() if k != "favorite_mood"}
    issues = validate_user_prefs(prefs)
    assert has_errors(issues)
    assert "favorite_mood" in messages(issues, ERROR)


@pytest.mark.parametrize("energy", [1.5, -0.1, float("nan"), "high", None, True])
def test_bad_target_energy_is_an_error(energy):
    issues = validate_user_prefs({**GOOD_PREFS, "target_energy": energy})
    assert has_errors(issues)
    assert "target_energy" in messages(issues, ERROR)


@pytest.mark.parametrize("energy", [0.0, 1.0, 0, 1])
def test_boundary_target_energy_is_allowed(energy):
    assert not has_errors(validate_user_prefs({**GOOD_PREFS, "target_energy": energy}))


@pytest.mark.parametrize("value", ["yes", "False", 1, None])
def test_non_bool_likes_acoustic_is_an_error(value):
    issues = validate_user_prefs({**GOOD_PREFS, "likes_acoustic": value})
    assert "likes_acoustic" in messages(issues, ERROR)


def test_non_text_genre_is_an_error():
    issues = validate_user_prefs({**GOOD_PREFS, "favorite_genre": 42})
    assert "favorite_genre" in messages(issues, ERROR)


def test_non_dict_prefs_is_an_error():
    assert has_errors(validate_user_prefs(["pop", "happy"]))


def test_extra_spaces_are_flagged_but_not_an_error(catalog):
    issues = validate_user_prefs({**GOOD_PREFS, "favorite_genre": " pop "}, catalog)
    assert not has_errors(issues)
    assert "extra spaces" in messages(issues, WARNING)


def test_unusual_capitalization_is_flagged_but_not_an_error(catalog):
    issues = validate_user_prefs({**GOOD_PREFS, "favorite_mood": "HAPPY"}, catalog)
    assert not has_errors(issues)
    assert "capitalization" in messages(issues, WARNING)


def test_empty_genre_is_flagged():
    issues = validate_user_prefs({**GOOD_PREFS, "favorite_genre": ""})
    assert not has_errors(issues)
    assert "empty" in messages(issues, WARNING)


def test_mood_missing_from_catalog_is_flagged(catalog):
    issues = validate_user_prefs({**GOOD_PREFS, "favorite_mood": "sad"}, catalog)
    assert "does not appear in the catalog" in messages(issues, WARNING)


def test_catalog_check_is_skipped_without_songs():
    assert validate_user_prefs({**GOOD_PREFS, "favorite_mood": "sad"}) == []


def test_unknown_preference_key_is_flagged():
    issues = validate_user_prefs({**GOOD_PREFS, "favorite_artist": "Neon Echo"})
    assert not has_errors(issues)
    assert "favorite_artist" in messages(issues, WARNING)


def test_validation_does_not_change_the_prefs():
    prefs = {**GOOD_PREFS, "favorite_genre": " Pop "}
    before = dict(prefs)
    validate_user_prefs(prefs)
    assert prefs == before


def test_cli_profiles_get_the_expected_validation_result(catalog):
    """The CLI's edge-case profiles are flagged; the standard ones are clean."""
    for name in ("High-Energy Pop", "Chill Lofi", "Deep Intense Rock"):
        assert validate_user_prefs(PROFILES[name], catalog) == [], name
    assert has_errors(validate_user_prefs(PROFILES["Overdrive"], catalog))
    for name in ("Whitespace Pop", "Sad Gym Rat", "No Preferences"):
        issues = validate_user_prefs(PROFILES[name], catalog)
        assert issues and not has_errors(issues), name


# ---------------------------------------------------------------------------
# Validation: songs and catalog
# ---------------------------------------------------------------------------

def test_valid_song_has_no_issues():
    assert validate_song(make_song()) == []


def test_real_catalog_is_valid(catalog):
    assert validate_catalog(catalog) == []


def test_song_missing_field_is_an_error():
    song = make_song()
    del song["mood"]
    assert "mood" in messages(validate_song(song), ERROR)


@pytest.mark.parametrize("field,value", [
    ("energy", 1.2), ("valence", -0.5), ("danceability", "lots"),
    ("acousticness", float("nan")), ("tempo_bpm", 0), ("tempo_bpm", -90.0),
    ("title", ""), ("artist", "   "), ("id", "seven"), ("id", 1.5),
])
def test_bad_song_values_are_errors(field, value):
    issues = validate_song(make_song(**{field: value}))
    assert field in messages(issues, ERROR)


def test_song_genre_with_spaces_is_a_warning():
    issues = validate_song(make_song(genre="pop "))
    assert not has_errors(issues)
    assert "genre" in messages(issues, WARNING)


def test_duplicate_song_ids_are_an_error():
    issues = validate_catalog([make_song(id=1), make_song(id=1, title="Copy")])
    assert "duplicate id" in messages(issues, ERROR)


def test_empty_catalog_is_an_error():
    assert has_errors(validate_catalog([]))


# ---------------------------------------------------------------------------
# Safe CSV loading
# ---------------------------------------------------------------------------

def test_load_songs_safely_matches_load_songs_on_real_catalog(catalog):
    songs, issues = load_songs_safely(str(CSV_PATH))
    assert issues == []
    assert songs == catalog


def test_load_songs_safely_skips_bad_rows_and_keeps_good_ones(tmp_path):
    csv_file = tmp_path / "songs.csv"
    csv_file.write_text(
        CSV_HEADER
        + "1,Good Song,A,pop,happy,0.8,120,0.9,0.8,0.2\n"
        + "2,Bad Number,B,pop,happy,loud,120,0.9,0.8,0.2\n"   # energy is not a number
        + "3,Too Loud,C,rock,intense,1.7,150,0.5,0.6,0.1\n"   # energy out of range
        + "4,,D,lofi,chill,0.4,80,0.6,0.6,0.8\n"              # blank title
        + "1,Same Id,E,jazz,relaxed,0.4,90,0.7,0.5,0.9\n"     # duplicate id
        + "5,Short Row,F,pop\n",                               # missing values
        encoding="utf-8",
    )
    songs, issues = load_songs_safely(str(csv_file))

    assert [s["title"] for s in songs] == ["Good Song"]
    text = messages(issues, ERROR)
    for expected in ("line 3", "not a number", "line 4", "outside 0.0-1.0",
                     "line 5", "title", "line 6", "duplicate id", "line 7", "missing field"):
        assert expected in text
    assert sum(1 for i in issues if i.message.endswith("row skipped.")) == 5


def test_load_songs_safely_reports_missing_columns(tmp_path):
    csv_file = tmp_path / "songs.csv"
    csv_file.write_text("id,title,artist,genre,mood\n1,Song,A,pop,happy\n", encoding="utf-8")
    songs, issues = load_songs_safely(str(csv_file))
    assert songs == []
    assert "missing column" in messages(issues, ERROR)


def test_load_songs_safely_raises_for_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_songs_safely(str(tmp_path / "nope.csv"))


# ---------------------------------------------------------------------------
# Verification: scores and rankings
# ---------------------------------------------------------------------------

def test_every_profile_and_song_passes_check_score(catalog):
    """Every score the engine produces is in range and agrees with its reasons."""
    for name, prefs in PROFILES.items():
        for song in catalog:
            score, reasons = score_song(prefs, song)
            assert check_score(prefs, song, score, reasons) == [], (name, song["title"])


def test_score_never_exceeds_max(catalog):
    perfect = {"favorite_genre": "pop", "favorite_mood": "happy", "target_energy": 0.82, "likes_acoustic": False}
    best = max(score_song(perfect, song)[0] for song in catalog)
    assert best <= MAX_SCORE
    assert best == pytest.approx(MAX_SCORE)  # Sunrise City matches all four exactly


def test_check_score_catches_a_wrong_score():
    song = make_song()
    score, reasons = score_song(GOOD_PREFS, song)
    assert "add up to" in messages(check_score(GOOD_PREFS, song, score + 1.0, reasons))


def test_check_score_catches_out_of_range_score():
    assert "outside" in messages(check_score(GOOD_PREFS, make_song(), 6.0, ["genre match (+6.0)"]))


def test_check_score_catches_a_false_genre_reason():
    song = make_song(genre="rock")
    _, reasons = score_song(GOOD_PREFS, song)
    fake_reasons = ["genre match (+1.5)"] + reasons
    issues = check_score(GOOD_PREFS, song, sum_points(fake_reasons), fake_reasons)
    assert "genre match" in messages(issues)


def sum_points(reasons):
    return sum(float(r.rsplit("(+", 1)[1].rstrip(")")) for r in reasons)


def test_real_recommendations_pass_all_checks(catalog):
    for name, prefs in PROFILES.items():
        if has_errors(validate_user_prefs(prefs, catalog)):
            continue
        for k in (1, 5, len(catalog), len(catalog) + 3):
            results = recommend_songs(prefs, catalog, k=k)
            assert check_recommendations(prefs, catalog, results, k) == [], (name, k)


def test_check_recommendations_catches_unsorted_results(catalog):
    results = recommend_songs(GOOD_PREFS, catalog, k=5)
    shuffled = list(reversed(results))
    assert "not sorted" in messages(check_recommendations(GOOD_PREFS, catalog, shuffled, 5))


def test_check_recommendations_catches_duplicates(catalog):
    results = recommend_songs(GOOD_PREFS, catalog, k=5)
    duplicated = results[:4] + [results[0]]
    issues = check_recommendations(GOOD_PREFS, catalog, duplicated, 5)
    assert "more than once" in messages(issues)


def test_check_recommendations_catches_a_missed_better_song(catalog):
    results = recommend_songs(GOOD_PREFS, catalog, k=6)
    without_best = results[1:]  # drop #1 and keep 5: the best song is now "left out"
    issues = check_recommendations(GOOD_PREFS, catalog, without_best, 5)
    assert "left out" in messages(issues)


def test_check_recommendations_catches_wrong_count(catalog):
    results = recommend_songs(GOOD_PREFS, catalog, k=3)
    assert "expected 5" in messages(check_recommendations(GOOD_PREFS, catalog, results, 5))


def test_check_recommendations_catches_tampered_score(catalog):
    song, score, explanation = recommend_songs(GOOD_PREFS, catalog, k=1)[0]
    issues = check_recommendations(GOOD_PREFS, catalog, [(song, score + 0.5, explanation)], 1)
    assert "score_song() gives" in messages(issues)


# ---------------------------------------------------------------------------
# Evaluation metrics (hand-checked on a tiny catalog)
# ---------------------------------------------------------------------------

# For GOOD_PREFS (pop, happy, energy 0.8, produced) each song matches:
TINY_CATALOG = [
    #                                                       genre mood energy acoustic -> matches
    make_song(id=1, title="A", artist="X", genre="pop", mood="happy", energy=0.8, acousticness=0.1),   # Y Y Y Y -> 4
    make_song(id=2, title="B", artist="X", genre="pop", mood="sad", energy=0.6, acousticness=0.1),     # Y N Y Y -> 3 (gap exactly 0.2)
    make_song(id=3, title="C", artist="Y", genre="rock", mood="happy", energy=0.3, acousticness=0.1),  # N Y N Y -> 2
    make_song(id=4, title="D", artist="Z", genre="lofi", mood="chill", energy=0.2, acousticness=0.9),  # N N N N -> 0
]


def test_preference_matches_on_hand_built_songs():
    assert preference_matches(GOOD_PREFS, TINY_CATALOG[0]) == {"genre": True, "mood": True, "energy": True, "acoustic": True}
    assert preference_matches(GOOD_PREFS, TINY_CATALOG[1]) == {"genre": True, "mood": False, "energy": True, "acoustic": True}
    assert preference_matches(GOOD_PREFS, TINY_CATALOG[3]) == {"genre": False, "mood": False, "energy": False, "acoustic": False}


def test_relevance_needs_three_of_four_matches():
    assert [is_relevant(GOOD_PREFS, s) for s in TINY_CATALOG] == [True, True, False, False]


def test_metrics_on_hand_built_catalog():
    results = recommend_songs(GOOD_PREFS, TINY_CATALOG, k=4)
    assert [s["title"] for s, _, _ in results] == ["A", "B", "C", "D"]

    m = evaluate_recommendations(GOOD_PREFS, results, TINY_CATALOG)

    assert m["k"] == 4
    assert m["precision_at_k"] == pytest.approx(2 / 4)       # A and B are relevant
    assert m["genre_match_rate"] == pytest.approx(2 / 4)     # A, B
    assert m["mood_match_rate"] == pytest.approx(2 / 4)      # A, C
    assert m["energy_match_rate"] == pytest.approx(2 / 4)    # A, B
    assert m["acoustic_fit_rate"] == pytest.approx(3 / 4)    # A, B, C
    assert m["avg_energy_gap"] == pytest.approx((0.0 + 0.2 + 0.5 + 0.6) / 4)
    total = sum(score for _, score, _ in results)
    assert m["avg_score_pct"] == pytest.approx(100 * total / (4 * MAX_SCORE))
    assert m["unique_artists"] == 3
    assert m["unique_genres"] == 3
    assert m["relevant_in_catalog"] == 2
    assert m["best_possible_precision"] == pytest.approx(2 / 4)


def test_precision_at_k_for_top_two():
    results = recommend_songs(GOOD_PREFS, TINY_CATALOG, k=2)
    m = evaluate_recommendations(GOOD_PREFS, results, TINY_CATALOG)
    assert m["precision_at_k"] == 1.0
    assert m["best_possible_precision"] == 1.0  # min(2 relevant, k=2) / 2


def test_metrics_are_none_for_empty_results():
    m = evaluate_recommendations(GOOD_PREFS, [], TINY_CATALOG)
    assert m["k"] == 0
    assert m["precision_at_k"] is None
    assert m["avg_energy_gap"] is None


def test_catalog_metrics_are_none_without_catalog():
    results = recommend_songs(GOOD_PREFS, TINY_CATALOG, k=2)
    m = evaluate_recommendations(GOOD_PREFS, results)
    assert m["relevant_in_catalog"] is None
    assert m["best_possible_precision"] is None


def test_precision_never_beats_best_possible(catalog):
    for prefs in PROFILES.values():
        if has_errors(validate_user_prefs(prefs, catalog)):
            continue
        m = evaluate_recommendations(prefs, recommend_songs(prefs, catalog, k=5), catalog)
        for key in ("precision_at_k", "genre_match_rate", "mood_match_rate",
                    "energy_match_rate", "acoustic_fit_rate", "best_possible_precision"):
            assert 0.0 <= m[key] <= 1.0
        assert m["precision_at_k"] <= m["best_possible_precision"]


def test_issue_prints_its_level():
    assert str(Issue(ERROR, "bad")) == "ERROR: bad"


# ---------------------------------------------------------------------------
# The app runs with both commands
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("command", [
    [sys.executable, "src/main.py"],
    [sys.executable, "-m", "src.main"],
])
def test_app_runs_with_both_commands(command):
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    assert "Catalog check: 17 valid songs, 0 errors" in result.stdout
    assert "NO RECOMMENDATIONS" in result.stdout          # Overdrive is withheld
    assert "EVALUATION SUMMARY" in result.stdout
    assert "FAIL" not in result.stdout
