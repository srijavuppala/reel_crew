# Reel Crew — Devpost submission

## One-line pitch

Reel Crew turns a producer's plain-English staffing brief into an evidence-ranked
crew shortlist and a proven collaboration network, using Gemini, Google ADK, and
ClickHouse over more than 100 million real IMDb credit rows.

## Inspiration

Film crews are hired through personal networks. A line producer staffing a horror
feature calls the cinematographers they already know, while hundreds of qualified
people remain effectively invisible. IMDb can show one person's credits, but it
cannot answer a production question such as: “Who has shot at least three well-rated
horror features recently, and who do they repeatedly work with?”

Reel Crew makes that question searchable. It does not create unofficial profiles or
guess at private facts such as availability and rates. It computes capability
summaries from public filmography evidence.

## What it does

A producer enters a brief in plain English. Gemini converts it into a typed query:
craft, genres, rating floor, year range, credit threshold, and vote threshold.
ClickHouse ranks matching crew members from real credits. A second ClickHouse query
finds the people who repeatedly worked with the leading candidate, exposing a
hireable production unit rather than an isolated name.

The producer can inspect the SQL and row counts, adjust the parsed filters, open a
candidate's evidence profile, walk their collaborator network, find less-visible
people with a similar genre career vector, build a shortlist, and export it as CSV.
Every candidate links to IMDb for verification.

## How we built it

- **Google ADK Workflow:** a deterministic `parse → search → collaborators → narrate`
  graph. The graph structure is fixed; the model does not choose the candidate set.
- **Gemini 2.5 Flash:** structured extraction of the production brief and grounded
  narration of rows already returned by ClickHouse. A deterministic fallback keeps
  the workflow usable without an API key.
- **ClickHouse Cloud:** 101,655,603 raw principal-credit rows loaded directly from
  IMDb's public gzipped TSV files, then denormalized into 1,295,494 rankable crew
  credits. Runtime queries perform ranked aggregation, collaboration self-joins,
  profile assembly, and cosine similarity over genre vectors.
- **FastAPI and a dependency-free web UI:** one container serves both the API and
  product interface and is prepared for deployment to Google Cloud Run.

The key architectural rule is: **Gemini parses and narrates; ClickHouse ranks.** No
candidate reaches the screen unless a parameterized SQL query returned them.

## Challenges

The raw IMDb files encode missing values as literal `\\N` strings, so staging every
ambiguous field as text and casting during denormalization was more reliable than
forcing types during ingestion. We also found that sharing one ClickHouse client
across FastAPI worker threads caused concurrent-session errors, so the application
creates one cached client per thread.

Gemini Enterprise Agent Platform and AI Studio keys can fail against the wrong
endpoint with the same permission error. The runtime therefore supports both
backends, reports the active one in its health endpoint, and attempts the alternate
backend once when appropriate.

For similarity search, aliasing an output column as `category` shadowed the table
column and silently weakened the craft filter. Renaming the alias restored the
intended same-craft comparison.

## What we learned

Agentic does not have to mean nondeterministic. A constrained model is effective at
translating human intent and explaining evidence, while a database remains the
authority for retrieval and ranking. Showing the executed SQL, result counts, and
per-step timings makes that boundary visible to users and judges.

We also learned that the most useful unit of crew discovery is often a working
relationship, not an individual. Repeated shared credits reveal the teams that
already know how to deliver together.

## What's next

The next step is **Script to Screen**: break down a screenplay into production needs,
derive the required departments and genre experience, then assemble an evidence-based
crew package. Current availability, location, union status, and rates would only be
added through authorized first-party or partner data; Reel Crew will not infer them.

## Built with

Google Cloud, Gemini 2.5 Flash, Google ADK, ClickHouse Cloud, FastAPI, Python,
JavaScript, HTML, CSS, Docker, IMDb public datasets.

## Links to complete before submission

- Hosted project: `TODO`
- Source: https://github.com/srijavuppala/reel_crew
- Demo video: `TODO`
- Partner track: **ClickHouse**

## Data and license

The code is released under the MIT License. Credit data comes from IMDb public
datasets under IMDb's personal and non-commercial dataset terms. The data itself is
not redistributed in the repository.
