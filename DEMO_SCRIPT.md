# Reel Crew — three-minute demo

Record at 1920×1080 with browser zoom set so the parsed query, evidence columns,
workflow trace, and SQL are readable. Use a fresh browser session and rehearse the
exact brief before recording.

## 0:00–0:20 — the problem

“A line producer staffing a horror feature calls the cinematographers they already
know. Hundreds of qualified crew members are invisible because film credits are not
searchable as production requirements. Reel Crew turns those requirements into an
evidence-ranked shortlist.”

Show the empty product screen and the corpus totals in the header.

## 0:20–0:35 — the architecture promise

“Gemini parses and narrates. ClickHouse ranks. The model never invents a candidate;
every person on screen came from parameterized SQL over real IMDb credits.”

Keep the workflow trace area ready to point out after the search.

## 0:35–1:20 — run the brief

Enter:

> I need a DP who has shot three or more horror features rated above 6.5 since 2018

Run the search. Point out:

1. The brief became typed filters.
2. The runtime badges show Gemini, ClickHouse, and the ADK workflow.
3. Candidates are ranked with matching credits, rating, audience reach, and recency.
4. Open “Show the SQL” and briefly show the query and returned row count.
5. Open one IMDb link to verify a candidate, then return to Reel Crew.

## 1:20–2:05 — hire a unit

Open the top candidate's profile. Show career span, genre mix, rating history, and
collaborators.

“Productions hire in packs. These are people this cinematographer repeatedly shares
credits with. You are not only finding a DP—you are finding a camera department that
already knows how to work together.”

Select one collaborator to demonstrate that the graph is navigable.

## 2:05–2:30 — discover beyond the usual network

In the profile, show “Works like this person.” Explain that ClickHouse builds a
28-genre career vector and uses cosine distance to find same-craft crew with similar
work, while the reach cap can surface less-famous alternatives. Add one candidate to
the shortlist and export the CSV.

## 2:30–2:48 — prove the implementation

“The Google ADK graph has four deterministic steps: parse, search, collaborate, and
narrate. ClickHouse is called at runtime for ranking, graph joins, profile statistics,
and vector similarity across 1.3 million rankable credits derived from 101.6 million
raw rows.”

Show the trace and engine badges, not an architecture slide.

## 2:48–3:00 — close honestly

“The IMDb data is used under its personal and non-commercial dataset license. Reel
Crew does not guess availability, rates, or location. Next, Script to Screen will
derive every department from a screenplay and assemble a verifiable production crew.”

End on the populated shortlist.

## Recording checklist

- [ ] Hosted URL is open; do not record localhost.
- [ ] `/api/health` reports ClickHouse connected, Gemini enabled, and the intended backend.
- [ ] The exact demo brief returns good candidates before recording.
- [ ] Browser notifications and personal bookmarks are hidden.
- [ ] Microphone is clear and the final cut is at most three minutes.
- [ ] Video is public or unlisted on YouTube/Vimeo and has English audio or subtitles.
- [ ] Repository and hosted-project URLs are visible in the video description.
