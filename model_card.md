# 🎧 Model Card: Music Recommender Simulation

## 1. Model Name

**VibeMatch 1.0**

---

## 2. Intended Use

VibeMatch is a classroom simulation of a content-based music recommender. Given a single
user's stated taste profile (favorite genre, favorite mood, target energy level, and whether
they like acoustic music), it scores every song in a fixed 18-song catalog and returns the
top `k` matches with an explanation for each.

It assumes the user's taste can be summarized by one favorite genre and one favorite mood —
it does not model users with mixed or evolving tastes, and it has no concept of listening
history. This is built for learning how recommenders turn data into rankings, not for
recommending music to real listeners.

---

## 3. How the Model Works

Every song has a genre, a mood, and some numeric attributes (energy, tempo, valence,
danceability, acousticness). Every user has a favorite genre, a favorite mood, a target
energy level, and a yes/no acoustic preference.

To score a song, the system hands out points: +2.0 if the genre matches exactly, +1.0 if the
mood matches exactly, up to +1.0 more the closer the song's energy is to the user's target
energy (not just "higher energy is better" — a song that's too energetic loses points just
like one that's not energetic enough), and +0.5 if the user likes acoustic music and the song
is acoustic enough. Every song in the catalog gets scored this way, then the list is sorted
highest to lowest and the top few are shown, each with a plain-language breakdown of which
bonuses it earned.

Beyond the starter version, the scoring rule and CLI were made to run over four contrasting
profiles in one pass (instead of just one hardcoded profile) and to print an explanation
string alongside every score, so the "why" is visible for every recommendation, not just the
top one.

**Agentic self-check layer (`src/agent.py`):** rather than call the scorer once and trust the
result, the CLI now runs a plan → act → check loop for every profile. It plans a set of
scoring weights (starting at the defaults), acts by scoring and ranking the catalog, and
checks the #1 pick against two guardrails — is its energy within 0.35 of the requested
target, and is its score above a confidence floor of 1.0? If a check fails and the failure is
one weight-tuning can plausibly fix (an energy gap), it raises the energy weight and retries,
up to 3 attempts. If the failure can't be fixed that way — e.g. no genre/mood match exists in
the catalog at all — it stops immediately rather than retrying blindly. Every attempt is
logged to `logs/app.log`. This directly targets the "silent failure" bias described in
Section 6: it can't fix a data-level gap, but it will name the gap instead of hiding it.

---

## 4. Data

- **18 songs total**, each with: title, artist, genre, mood, energy, tempo_bpm, valence,
  danceability, acousticness.
- **15 distinct genres** are represented (pop, lofi, rock, ambient, jazz, synthwave, indie
  pop, metal, folk, r&b, hip hop, classical, house, country, reggae), but most genres appear
  only once — only lofi (3 songs) and pop (2 songs) have more than one entry.
- **12 distinct moods**, with "chill" the most common (3 songs).
- Missing from the dataset entirely: lyrics/language, release year, popularity or play-count
  signals, and any notion of *who else* listened to a song — this is why the system has to be
  content-based rather than collaborative.

---

## 5. Strengths

- For profiles whose genre/mood pairing actually exists in the catalog (e.g. "Chill Lofi" →
  genre=lofi, mood=chill), the system produces a confident, sensibly-ordered top 5 where the
  #1 and #2 picks are genuinely close matches (see Evaluation below).
- The explanation strings make the ranking auditable — you can see exactly why a song beat
  another, which is a real strength over a black-box score.
- The energy-closeness formula correctly rewards *proximity* rather than just "more energy is
  better," so it distinguishes a mellow-energy request from a high-energy one instead of
  always surfacing the most energetic songs.

---

## 6. Limitations and Bias

- **Exact-match bias:** genre and mood matching is all-or-nothing string equality. "pop" and
  "indie pop" score identically to "pop" and "classical" (both zero) even though the former
  pair is musically close. This likely under-serves users whose favorite genre is a
  subgenre or blend.
- **Genre/mood dominate energy:** because a genre+mood match (+3.0 combined) is worth more
  than the entire energy term (capped at +1.0), a song can win purely on genre/mood even when
  its energy is a poor fit. Tested directly with the adversarial profile
  `{genre: classical, mood: melancholy, energy: 0.9}` — "Rainlight Sonata" (the catalog's only
  classical/melancholy song) still ranks #1 even though its actual energy is 0.20, nowhere
  near the requested 0.9. **Update:** the plain scoring rule still reports this as a 3.30-score
  match with no signal anything is wrong — but as of the agentic self-check layer
  (`src/agent.py`, see Section 3), the *system* no longer does. The agent tries raising the
  energy weight up to twice, can't out-weight a data-level gap that large, and reports a
  `⚠️ Low confidence` warning naming the exact mismatch instead of presenting the 3.90-score
  result as confident. See Section 7 for the actual run.
- **Catalog-size bias:** with only 1-3 songs per genre, "diversity" in the top 5 usually just
  means "songs that happen to share the user's energy level," not real stylistic variety.
- **Single-facet user model:** `UserProfile` can't express "I like rock or jazz" or partial/
  fuzzy preferences, so any user with blended taste gets flattened into whichever single
  genre/mood they pick.

---

## 7. Evaluation

Tested four profiles end to end (see `src/main.py`'s `PROFILES` dict and full terminal
output below):

```
=== High-Energy Pop === {genre: pop, mood: happy, energy: 0.9}
1. Sunrise City (pop/happy) — 3.92 — genre match (+2.0), mood match (+1.0), energy closeness (+0.92)
2. Gym Hero (pop/intense) — 2.97 — genre match (+2.0), energy closeness (+0.97)
3. Rooftop Lights (indie pop/happy) — 1.86 — mood match (+1.0), energy closeness (+0.86)
4. Storm Runner (rock/intense) — 0.99 — energy closeness (+0.99)
5. Sunset Highway (house/euphoric) — 0.98 — energy closeness (+0.98)

=== Chill Lofi === {genre: lofi, mood: chill, energy: 0.3, likes_acoustic: true}
1. Library Rain (lofi/chill) — 4.45 — genre match (+2.0), mood match (+1.0), energy closeness (+0.95), acoustic bonus (+0.5)
2. Midnight Coding (lofi/chill) — 4.38 — genre match (+2.0), mood match (+1.0), energy closeness (+0.88), acoustic bonus (+0.5)
3. Focus Flow (lofi/focused) — 3.40 — genre match (+2.0), energy closeness (+0.90), acoustic bonus (+0.5)
4. Spacewalk Thoughts (ambient/chill) — 2.48 — mood match (+1.0), energy closeness (+0.98), acoustic bonus (+0.5)
5. Harvest Moon Waltz (folk/nostalgic) — 1.50 — energy closeness (+1.00), acoustic bonus (+0.5)

=== Deep Intense Rock === {genre: rock, mood: intense, energy: 0.85}
1. Storm Runner (rock/intense) — 3.94 — genre match (+2.0), mood match (+1.0), energy closeness (+0.94)
2. Gym Hero (pop/intense) — 1.92 — mood match (+1.0), energy closeness (+0.92)
3. Sunrise City (pop/happy) — 0.97 — energy closeness (+0.97)
4. Sunset Highway (house/euphoric) — 0.97 — energy closeness (+0.97)
5. Rooftop Lights (indie pop/happy) — 0.91 — energy closeness (+0.91)

=== Adversarial: High-Energy Melancholy === {genre: classical, mood: melancholy, energy: 0.9}
1. Rainlight Sonata (classical/melancholy) — 3.30 — genre match (+2.0), mood match (+1.0), energy closeness (+0.30)
2. Storm Runner (rock/intense) — 0.99 — energy closeness (+0.99)
3. Sunset Highway (house/euphoric) — 0.98 — energy closeness (+0.98)
4. Gym Hero (pop/intense) — 0.97 — energy closeness (+0.97)
5. Broken Compass (metal/angry) — 0.95 — energy closeness (+0.95)
```

**Comparing the profiles:** "High-Energy Pop" and "Deep Intense Rock" both land a #1 pick
that's an unambiguous genre+mood+energy match, and their #2-#5 picks make intuitive sense —
they trail off toward songs that only share one signal (mood or energy) with the profile,
which lines up with what a human would expect: partial matches should score lower than full
matches, and they do. "Chill Lofi" is the strongest run of all four, because the catalog has
three lofi songs to draw from, so the acoustic bonus and energy closeness meaningfully
separate the top 3 instead of everything tying near zero.

The **adversarial profile is where the system's real weakness shows up**: the plain scoring
rule confidently returns "Rainlight Sonata" as a 3.30-scoring top pick for a user who
explicitly wants high energy, purely because it's the only genre+mood match in the catalog.
In plain terms — imagine telling a friend "I want something classical and melancholy, but
really pumped up," and they hand you the slowest, saddest track in their library and call it
a perfect match. That's the system failing silently: nothing in the score or explanation
string flags that the energy request was almost completely ignored. This is the same dynamic
as the "Gym Hero keeps showing up for Happy Pop fans" pattern — the score rewards partial
matches without ever signaling *how* partial they are.

**Agent run on the same adversarial profile** (`src/agent.py`, actual output):

```
=== Adversarial: High-Energy Melancholy ===
User profile: {'genre': 'classical', 'mood': 'melancholy', 'energy': 0.9, 'likes_acoustic': False}

⚠️  Low confidence after 3 attempt(s): energy_mismatch: top pick's energy (0.20) is 0.70 away from the requested target (0.90)

1. Rainlight Sonata — Elena Cho (classical/melancholy)
   Score: 3.90
   Because: genre match (+2.00), mood match (+1.00), energy closeness (+0.90)
```

The agent's trace (`logs/app.log`) shows it raised the energy weight from 1.0 → 2.0 → 3.0
across three attempts, and "Rainlight Sonata" stayed the #1 pick every time — its 0.70 energy
gap is too large for any energy weight to out-score a genre+mood match in this catalog. The
score itself even changed (3.30 → 3.60 → 3.90 across attempts) while the actual match quality
didn't improve at all, which is a good illustration of why the guardrail checks the *gap*
directly rather than trusting the score to reflect it. The headline result: the top pick is
unchanged, but the system's behavior changed from confidently wrong to honestly uncertain.

Re-ran "High-Energy Pop" and "Deep Intense Rock" with genre-match weight halved (2.0 → 1.0)
and energy-closeness weight doubled (1.0 → 2.0). Full results are in the README's
"Experiments You Tried" section — the headline finding is that the top-5 *ordering* didn't
change at all for either profile, only the score gaps compressed. That was a genuine surprise
going in: doubling the energy weight felt like it should have let a strong energy-only match
overtake a genre match, but a genre+mood match's combined ceiling (2.0 either way) still beat
any single energy-only score in this catalog.

---

## 8. Future Work

- Replace exact-string genre matching with a similarity/hierarchy mapping (e.g. "indie pop"
  partially credits a "pop" preference) so related genres aren't scored as total mismatches.
- ~~Add a penalty (not just a missing bonus) when a strong genre/mood match comes with a badly
  mismatched energy level, so the adversarial-profile failure mode above surfaces in the score
  itself instead of only in a human reading the explanation.~~ **Done, via a different
  mechanism:** rather than change the score itself, the agentic layer (`src/agent.py`) checks
  the energy gap directly and surfaces a `⚠️ Low confidence` warning alongside the score. A
  true in-score penalty is still an open option if a future version wants the ranking itself
  (not just the confidence flag) to change.
- Let `UserProfile` express more than one favorite genre/mood, or weighted preferences, to
  better represent blended taste.
- Add a diversity/re-ranking pass so the top 5 don't cluster around one or two songs from the
  same artist or sub-genre when the catalog allows for more variety.

---

## 9. Personal Reflection

The biggest thing I took away from this project is that "recommendation" here is really just
weighted addition plus a sort — there's no hidden intelligence, just a formula a human
designed based on which signals they believed mattered most. Using AI tools to help design
and implement the scoring rule was useful for quickly trying different weightings, but I had
to manually verify the results against my own intuition each time (e.g. actually reading the
adversarial profile's output rather than trusting that a high score meant a good match) to
catch cases like the classical/melancholy failure mode. What surprised me most was how
confidently the system reported a bad recommendation as a good one — the score alone gave no
indication that the energy match was terrible, which is a useful, small-scale reminder of how
real recommender systems can be confidently wrong in ways that aren't visible from the score
or ranking alone.

### Working with AI on the agentic layer

I used Claude Code to design and implement the plan → act → check loop in `src/agent.py`,
rather than writing that logic from scratch. That collaboration was genuinely useful, but it
also produced one mistake worth being honest about — and both are more instructive than a
clean success story would be.

**A helpful suggestion:** when I asked for an "advanced AI feature," the assistant didn't just
pick one — it checked this repo's actual `requirements.txt` and environment first, found no
LLM API key or SDK configured, and used that to rule out RAG and fine-tuning before
recommending an agentic self-check loop as the feature that was both feasible *and* directly
useful, since it targeted a weakness (the adversarial-profile failure mode) I'd already
documented in this file. That grounded the recommendation in my actual project constraints
instead of offering a generic menu of AI buzzwords.

**A flawed suggestion — and how it was caught:** the first version of the retry logic raised
the agent's energy weight and retried whenever *any* guardrail check failed, not just when the
failure was an energy mismatch. That was wrong: for a profile with no genre or mood match
anywhere in the catalog, raising the energy weight doesn't fix the real problem, but it
*did* incidentally inflate that profile's score past the confidence floor — flipping the
result to "confident" for a reason that had nothing to do with the actual match quality. I
didn't catch this by reading the code; I caught it because `pytest` failed on
`test_no_match_profile_is_flagged_low_confidence` with `assert True is False`. That's the
concrete lesson: a plausible-sounding fix can pass a quick read and still be wrong in a way
that only shows up when you run it against a case designed to break it. The fix — only retry
when the specific issue flagged is one the available lever can plausibly address — is now
tested directly in `tests/test_agent.py`.

**Where this leaves the system's limitations:** the agentic layer only ever *reports* the
catalog-level limitations described in Section 6 above — the tiny catalog, exact-string
genre matching, the single-facet user model — it doesn't fix any of them. A weight change
can't manufacture a better-matching song that isn't in an 18-song CSV. That's a deliberate
scope decision, not an oversight: the goal was to stop the system from being *silently* wrong,
not to pretend a re-weighting loop can substitute for more or better data.
