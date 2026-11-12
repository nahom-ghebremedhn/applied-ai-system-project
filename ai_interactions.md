# AI Interactions Log

> **Stretch features only.** Only fill in the sections that apply to stretch features you attempted. If you did not attempt a stretch feature, leave its section blank or delete it. This file is not required for the core project.

---

## Agentic Workflow (SF8)

> Document your experience using an AI agent (e.g., Cursor Agent, Claude, Copilot) to make multi-step changes autonomously.

**What task did you give the agent?**

I asked Claude Code (Claude Opus 5.5) to review my README against the Applied AI System requirements,
including a Testing Summary that covers an intentional sorting-bug experiment. The experiment wasn't
recorded anywhere in the repository, so Claude ran it again to get real results instead of inventing
them. I did not perform this experiment myself. The agent ran it, and I reviewed the reported results.

**Prompts used:**

- "Please review my current README.md against the following Applied AI System assignment requirements
  ... Testing Summary: Explain the 72 passing tests, what they verify, the intentional sorting bug
  experiment, what worked, and what was learned ... Do not invent features, test results, or sample
  outputs."
- "Update ai_interactions.md to document the AI-assisted sorting-bug experiment accurately ... Do not
  claim that I personally performed the experiment."

**What did the agent generate or change?**

The sorting-bug experiment, step by step:

1. **Baseline:** ran `python -m pytest` and got 72 passed.
2. **Temporarily changed the sorting direction:** backed up `src/recommender.py`, then changed line
   124 of `recommend_songs()` from `reverse=True` (highest score first) to `reverse=False` (lowest
   first).
3. **Ran the tests:** 7 failed and 65 passed. The failing tests were:
   - `test_recommender.py::test_recommend_matches_recommend_songs_on_real_catalog`
   - `test_reliability.py::test_real_recommendations_pass_all_checks`
   - `test_reliability.py::test_check_recommendations_catches_unsorted_results`
   - `test_reliability.py::test_metrics_on_hand_built_catalog`
   - `test_reliability.py::test_precision_at_k_for_top_two`
   - `test_reliability.py::test_app_runs_with_both_commands[command0]`
   - `test_reliability.py::test_app_runs_with_both_commands[command1]`
4. **Ran the app:** `python src/main.py` caught the invalid rankings and **exited with code 1**.
   Every valid profile showed `FAIL` in the Checks column, with messages such as
   `CHECK FAILED: Velvet Hours scores 2.50 but was left out of the top 5, which includes a song scoring 1.44.`
   Precision@5 dropped to 0.00 while the "Best" column stayed the same, which pointed to the ranking
   rather than the catalog.
5. **Restored the original sorting logic:** copied the backup back, confirmed line 124 reads
   `reverse=True` again, and reran the tests: 72 passed.

The agent then documented the results in the README's Testing Summary and in this file. No application
code, scoring rules, dependencies, or tests were changed permanently.

**What did you verify or fix manually?**

I reviewed the reported results and the documentation the agent wrote. The agent's first README draft
said "I flipped the sort," which implied I had run the experiment myself. I had the wording changed so
it describes the experiment as AI-assisted.

---

## Design Pattern (SF10)

> Document how AI helped you choose or implement a design pattern.

**Which design pattern did you use?**

<!-- e.g., Strategy, Factory, Observer, etc. -->

**How did AI help you brainstorm or implement it?**

<!-- Describe the conversation or suggestions that led to your decision -->

**How does the pattern appear in your final code?**

<!-- Point to the relevant class or method -->
