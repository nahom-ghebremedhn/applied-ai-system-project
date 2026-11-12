# 🎧 Model Card: Music Recommender Simulation

## 1. Model Name

**VibeMatch 1.0**

---

## 2. Goal / Task

VibeMatch suggests 5 songs from a small catalog that fit what a listener says they like. It doesn't learn from listening history. It only compares songs to four stated preferences.

---

## 3. Data Used

The catalog has 17 songs across 14 genres and 13 moods. Each song has a genre, mood, energy, tempo, valence, danceability and acousticness. Most genres have just one song, nothing is below 0.22 energy, and no song is tagged "sad."

---

## 4. Algorithm Summary

Each song gets points: 1.5 for the right genre, 1 for the right mood, and up to 2 for energy close to what you want. It gets 0.5 more if it's acoustic or produced, matching your taste. The 5 highest-scoring songs win, and a perfect song scores 5.

---

## 5. Observed Behavior / Biases

Acoustic songs in the catalog are all quiet and produced songs are all loud, so energy and sound end up meaning the same thing. Energy is worth more points, so a fan of loud acoustic music gets acoustic songs only 36% of the time. Exact labels also matter too much: "indie pop" isn't counted as "pop," and an extra space breaks the match.

---

## 6. Evaluation Process

I tested 3 normal profiles and 7 tricky ones, like a "sad" mood, impossible energy, and conflicting preferences. I tried moving weight from genre to energy, and it changed only 2 of 10 rankings. I also scored every combination of preferences (4,004 profiles) to find who gets poor results.

**Profile comparisons:**

- **High-Energy Pop vs. Chill Lofi:** No overlap at all. That makes sense, since they disagree on every preference.
- **High-Energy Pop vs. Deep Intense Rock:** Both get Gym Hero at #2. It's pop for one and "intense" for the other.
- **Chill Lofi vs. Deep Intense Rock:** Lofi stays under 0.45 energy and rock stays above 0.75. Energy is doing its job.
- **High-Energy Pop vs. Whitespace Pop:** Same request, but extra spaces drop Sunrise City from 4.96 to 3.46. A typo shouldn't change results.
- **High-Energy Pop vs. Sad Gym Rat:** Both start with the same upbeat pop songs. "Sad" isn't in the catalog, so it's quietly ignored.
- **Chill Lofi vs. Overdrive:** Same lofi songs on top, but a metal song sneaks in at #5. Energy 1.5 is impossible, so the loudest song looks "closest."
- **Deep Intense Rock vs. Acoustic Metal:** Both get the same loud, produced songs after #1. There are no loud acoustic songs to give.
- **High-Energy Pop vs. Indie Pop Fan:** Sunrise City and Rooftop Lights swap places at #1. The system treats "indie pop" and "pop" as unrelated.

**Why "Gym Hero" keeps showing up for happy-pop fans:** It's pop, loud and polished, so it matches three of the four preferences. The system can't tell that a workout song feels different from a happy one, because mood is worth only 1 point.

**Automated reliability checks (`src/reliability.py`):** Every run now checks the input, verifies the results, and scores them. Input problems are flagged and nothing is fixed automatically. Overdrive's impossible energy now counts as an error, so it gets no recommendations (the comparison above is from before this change). Each ranking is checked against `score_song()`, and every profile passes. Precision@5 counts a song as relevant when it matches at least 3 of the 4 preferences (genre, mood, energy within 0.2, acoustic fit). For every valid profile, Precision@5 equals the best the catalog allows, so low scores like Acoustic Metal's 0.20 come from the small catalog, not the ranking. This relevance is based on stated preferences, not real listener feedback.

---

## 7. Intended Use and Non-Intended Use

**Intended:** A classroom project for seeing how a simple scoring system turns preferences into recommendations. **Not intended:** Real users or real music apps. The catalog is too small and the labels are too rigid to serve real taste.

---

## 8. Ideas for Improvement

- Score acousticness by how close a song is, like energy, instead of a yes/no cutoff.
- Clean up inputs (trim spaces, keep energy between 0 and 1) and give partial credit for similar genres and moods.
- Add more songs, especially loud acoustic, quiet produced, and sad ones.

---

## 9. Personal Reflection

**Biggest learning moment:** Changing the weights barely changed the results. The real problems came from the data, like having no loud acoustic songs.

**Using AI tools:** AI helped me write the scoring code and quickly test thousands of profiles. I still had to check its claims against the actual output, because a few of its summaries overstated what happened.

**What surprised me:** Four simple rules were enough to make the top picks feel right. Adding a "why" next to each song made it feel even more like a real app.

**What I'd try next:** I'd use the unused columns, like valence for sad listeners, and add more songs per genre.

---

## 10. Reflection and Ethics: Thinking Critically About My AI

### 10.1 What are the limitations or biases in the system?

- **It only knows four stated preferences.** VibeMatch is a rule-based scoring system, not a machine
  learning model. It doesn't learn from listening history or feedback. Each song is scored on genre,
  mood, energy, and acoustic fit, and nothing else. Valence, tempo, and danceability are in the CSV but
  are never used.
- **The catalog is tiny and uneven.** There are 17 songs across 14 genres, so most genres have only one
  song. There are no "sad" songs, no loud acoustic songs, and no quiet produced songs. Some listeners
  can't be served well no matter how good the ranking is. Acoustic Metal gets a Precision@5 of 0.20, and
  Contradictory Classical (classical, chill, energy 0.95, produced) gets 0.00.
- **Energy and sound are tangled together.** In this catalog the acoustic songs are all quiet and the
  produced songs are all loud. Energy is worth up to 2 points and acoustic fit only 0.5, so a fan of loud
  acoustic music mostly gets loud produced songs. Acoustic Metal's acoustic fit rate is 0.00.
- **Labels are matched exactly.** "indie pop" gets no credit from a "pop" fan, and `' Pop '` with extra
  spaces doesn't match `pop` at all. The system now warns about this, but it doesn't fix it.
- **Mood is easy to outvote.** Gym Hero (pop, intense) lands at #2 for a happy-pop fan because genre,
  energy, and sound outweigh the 1-point mood bonus. The system can't tell a workout song from a happy one.
- **Filter bubble.** It only rewards similarity to what the user already said they like, so it never
  suggests anything new or surprising.
- **The metric has limits too.** Precision@5 counts a song as "relevant" when it matches at least 3 of
  the 4 preferences. That measures how closely the ranking follows the profile, not whether a real person
  would enjoy the songs. No real listeners evaluated the system.

### 10.2 Could the AI be misused, and how would you prevent that?

This is a classroom simulation with made-up songs, so the direct risk is low. Still, the same design
could be misused if someone built on it:

- **Presenting it as a real recommender.** Someone could point to the scores ("4.96 / 5.00") and the
  Precision@5 numbers as proof that it understands listeners. It doesn't. To prevent this, the README and
  this model card say it is not intended for real users, and I describe Precision@5 as agreement with
  stated preferences, not listener satisfaction.
- **Quietly promoting certain songs.** The score is just a few weights, so someone could tweak the
  weights or the catalog labels to push certain artists to the top while the results still look
  objective. The main protection here is transparency. Every recommendation lists its "Why" reasons with
  exact points, and `src/reliability.py` checks that the points add up to the score and that the ranking
  matches `score_song()`. That can't stop someone from changing the weights on purpose, but it makes the
  change visible. In a real product, I would publish the weights and log any changes to them.
- **Bad input producing misleading results.** Before I added validation, an impossible profile like
  Overdrive (energy 1.5) still got five normal-looking recommendations. Now invalid input is an error and
  the profile gets no recommendations. Softer problems, like a mood that isn't in the catalog, produce a
  warning so the user knows why the results might look off.
- **Privacy.** The system only uses four preferences written into a profile and doesn't collect or store
  personal data. If it were extended with real listening history, I would want user consent and a clear
  explanation of what gets stored.

### 10.3 What surprised me while testing the AI's reliability?

- **The worst failures were silent, not crashes.** The Overdrive profile (target energy 1.5) never caused
  an error at first. It returned five songs, and a metal song snuck in at #5 because the loudest song
  looked "closest" to an impossible target. The "sad" mood in Sad Gym Rat was also ignored without any
  message. That's why I added `src/reliability.py`. Now Overdrive is rejected with an ERROR, and Sad Gym
  Rat gets a warning that "sad" isn't in the catalog.
- **Low scores came from the catalog, not the ranking.** I expected weak Precision@5 numbers to mean the
  ranking was wrong. But for every valid profile, Precision@5 equals the best value the 17-song catalog
  allows (for example, 0.20 for Acoustic Metal and 0.00 for Contradictory Classical). Moving weight from
  genre to energy changed only 2 of the 10 rankings. The real problem was missing songs, not the weights.
- **Tiny formatting differences mattered a lot.** Adding spaces around "Pop" dropped Sunrise City from
  4.96 to 3.46 and dropped Precision@5 from 0.60 to 0.40, even though the request meant the same thing.
- **The checks caught a real bug.** In the AI-assisted sorting-bug experiment, the sort was temporarily
  reversed to lowest-first. 7 of the 72 tests failed, the app marked every valid profile as FAIL and
  exited with code 1, and Precision@5 fell to 0.00 while the "Best" column stayed the same. That gap
  showed the checks can tell a broken ranking apart from a weak catalog. After the original line was
  restored, all 72 tests passed again.

### 10.4 Describe your collaboration with AI during this project

I used Claude Code as a coding and documentation assistant, but I stayed actively involved in building
the system. Claude helped write the scoring code and the reliability checks, ran the test suite and the
app, reviewed my README against the assignment requirements, and drafted documentation. My part went
beyond checking its output:

- **Testing:** I ran the app and the tests myself and designed the edge-case profiles, such as Sad Gym
  Rat, Whitespace Pop, Overdrive, Acoustic Metal, and Contradictory Classical, to find where the
  recommender breaks.
- **Debugging:** When Overdrive quietly returned a metal song for a chill lofi listener, I traced the
  cause to the impossible energy target (1.5). That finding is why the reliability layer now rejects
  energy outside 0.0–1.0 instead of producing misleading results.
- **Improving:** I tried moving weight from genre to energy, compared the rankings before and after, and
  rebalanced the scoring weights. I also used the evaluation results to decide that the catalog, not the
  weights, was the real bottleneck.
- **Correcting:** I set rules like "don't invent features, test results, or sample outputs," and I fixed
  wording when the AI's drafts didn't match what actually happened.

When the README needed results from the sorting-bug experiment, Claude ran the experiment again instead
of making up numbers, and I reviewed the results. That process is logged in
[ai_interactions.md](ai_interactions.md). Every sample output in the README comes from an actual run of
`python src/main.py`.

**A suggestion I accepted:** Claude pointed out that GitHub might not show the standalone
`diagrams/architecture.mmd` file as a diagram, and suggested also putting it in the README as a Mermaid
code block. I accepted because I wanted the architecture to be visible right on the repository page. The
README now shows the diagram and links to the original `.mmd` file, which stayed unchanged.

**A suggestion I changed:** Claude's first README draft described the sorting-bug experiment as "I
flipped the sort." That made it sound like I ran the experiment myself, but Claude actually ran it and I
reviewed the results. I had the wording changed so the README calls it an "AI-assisted" experiment and
the AI log states plainly that I did not run it myself. This project is about being honest about what an
AI system did, and that should include my own documentation. I also chose not to follow Claude's
suggestion to remove the unused `pandas` and `streamlit` packages from `requirements.txt`, and kept the
dependencies unchanged for this submission.

**What I learned from working with AI:** The AI was fast at writing code and running many profiles, but
it worked best when I treated its output as a first draft. A few of its summaries overstated what
happened, so I tested its claims against the real output, debugged the cases that looked wrong, and
improved the code and documentation from there.
