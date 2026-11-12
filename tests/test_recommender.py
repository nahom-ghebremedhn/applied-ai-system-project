from src.recommender import Song, UserProfile, Recommender

def make_small_recommender() -> Recommender:
    songs = [
        Song(
            id=1,
            title="Test Pop Track",
            artist="Test Artist",
            genre="pop",
            mood="happy",
            energy=0.8,
            tempo_bpm=120,
            valence=0.9,
            danceability=0.8,
            acousticness=0.2,
        ),
        Song(
            id=2,
            title="Chill Lofi Loop",
            artist="Test Artist",
            genre="lofi",
            mood="chill",
            energy=0.4,
            tempo_bpm=80,
            valence=0.6,
            danceability=0.5,
            acousticness=0.9,
        ),
    ]
    return Recommender(songs)


def test_recommend_returns_songs_sorted_by_score():
    user = UserProfile(
        favorite_genre="pop",
        favorite_mood="happy",
        target_energy=0.8,
        likes_acoustic=False,
    )
    rec = make_small_recommender()
    results = rec.recommend(user, k=2)

    assert len(results) == 2
    # Starter expectation: the pop, happy, high energy song should score higher
    assert results[0].genre == "pop"
    assert results[0].mood == "happy"


def test_explain_recommendation_returns_non_empty_string():
    user = UserProfile(
        favorite_genre="pop",
        favorite_mood="happy",
        target_energy=0.8,
        likes_acoustic=False,
    )
    rec = make_small_recommender()
    song = rec.songs[0]

    explanation = rec.explain_recommendation(user, song)
    assert isinstance(explanation, str)
    assert explanation.strip() != ""


def test_recommend_ranks_by_score_not_catalog_order():
    # The lofi song is second in the catalog but should come first for a lofi fan.
    user = UserProfile(
        favorite_genre="lofi",
        favorite_mood="chill",
        target_energy=0.4,
        likes_acoustic=True,
    )
    rec = make_small_recommender()
    results = rec.recommend(user, k=2)

    assert [song.title for song in results] == ["Chill Lofi Loop", "Test Pop Track"]
    assert rec.recommend(user, k=1)[0].genre == "lofi"


def test_recommend_matches_recommend_songs_on_real_catalog():
    from dataclasses import asdict
    from src.recommender import load_songs, recommend_songs

    song_dicts = load_songs("data/songs.csv")
    songs = [Song(**song) for song in song_dicts]
    user = UserProfile(
        favorite_genre="rock",
        favorite_mood="intense",
        target_energy=0.9,
        likes_acoustic=False,
    )

    oop_titles = [song.title for song in Recommender(songs).recommend(user, k=5)]
    functional_titles = [song["title"] for song, _, _ in recommend_songs(asdict(user), song_dicts, k=5)]
    assert oop_titles == functional_titles


def test_explain_recommendation_uses_scoring_reasons():
    user = UserProfile(
        favorite_genre="pop",
        favorite_mood="happy",
        target_energy=0.8,
        likes_acoustic=False,
    )
    rec = make_small_recommender()
    explanation = rec.explain_recommendation(user, rec.songs[0])

    assert "genre match (+1.5)" in explanation
    assert "mood match (+1.0)" in explanation
    assert explanation.startswith("Score 5.00 / 5.00")
    assert "placeholder" not in explanation.lower()
