# Reel Crew — three-minute demo

Record at 1920×1080. Set browser zoom so the evidence columns, the role funnel, and the
SQL panel stay readable in the final cut. Fresh browser session, no bookmarks bar, no
notifications.

**Narration total: 478 words.** That is about 3:05 at a normal speaking pace, so you have no slack. Read it once
against a timer before recording; if you are running long, cut beat 6 (Replan) first.

**The one rule to keep saying:** Gemini parses and narrates, ClickHouse ranks. Judges on
the ClickHouse track are looking for real analytical work, not an LLM wrapper. Every beat
below is built to show a query doing something a model cannot.

---

## Setup before you hit record

Open the app and leave it on **Production plan**. The form already carries the demo:
title `Night Run`, budget `500000`, `3` shoot days, and a three-scene screenplay. You will
not type anything on this side, which buys you about fifteen seconds.

Confirm the header corpus counters have loaded (they come from `/api/stats` live — a blank
header is the most likely way this recording goes wrong).

---

## 1 — The problem · 0:00–0:18

Hold on the empty workspace.

> A line producer staffing a horror feature calls the four cinematographers they already
> know. The other three hundred qualified people are invisible, because film credits have
> never been searchable as production requirements. IMDb tells you what one person worked
> on. It cannot tell you who has actually done this kind of work.

## 2 — The architecture rule · 0:18–0:30

Point at the corpus counters in the header.

> A hundred and one million raw credits, denormalized into one-point-three million
> rankable rows. Gemini parses the brief and narrates the result. ClickHouse does the
> ranking. No candidate reaches this screen that did not come out of a SQL result set.

## 3 — Script in · 0:30–1:05

Click **Build production plan**. Let the six agent steps land, then stay on **Overview**.

> This is a screenplay excerpt, a budget, and a shoot-day target. Six deterministic
> agents run over it. The script agent breaks out the scenes. The crew agent reads what
> those scenes demand. Schedule, finance and risk build a stripboard, a balanced top
> sheet, and a risk register.

- Point at the scene count, planned shoot days, and the top-sheet total.
- The brief reads **Thriller**, inferred from scene composition — say "thriller", not "horror", or the screen will contradict you.
- Say the honest line: **"Every number here is a planning allowance, not a bid."**

## 4 — The mechanism, live · 1:05–1:45

Open the **Crew** page inside the plan. **This is the beat the demo is for — do not rush it.**

> The scenes carried requirements: a dog, night lighting, a vehicle, rain, a crowd, a
> fire, a fight. Nineteen crew positions came off those requirements, with the scene
> numbers that justify each one. Not a template — the script asked for them.

Point at the split between the staffed slates and the reported roles.

> Seven of those we can staff, because IMDb's principal-crew data covers the craft.
> Twelve we cannot — the gaffer, the stunt coordinator, the animal wrangler. Those are
> reported with the reason and the scene, not quietly dropped. We would rather show a
> producer the gap than pretend we filled it.

Open the **Director of Photography** slate and its funnel.

> And here is the part that is not a language model. ClickHouse narrows the corpus stage
> by stage — everyone in the craft, then the genre, then the rating, credit and vote
> floors, then the scored pool, then the shortlist you see. The match score is arithmetic
> over the columns in that row, and every component names the column it came from.

- Show the executed SQL and the row count.

## 5 — Hiring a unit, not a name · 1:45–2:10

Open a candidate profile from the slate, then the collaborator panel.

> Productions hire in packs. A cinematographer brings the people they keep shooting with.
> This is a self-join on shared credits, so it is the team that has actually delivered
> together, reconstructed from credits alone.

Scroll to **Works like this person** and switch on the reach cap.

> Every person is a twenty-eight dimensional genre vector, compared by cosine distance
> inside the same craft. Cosine normalizes away career length, so a six-credit DP can
> match a thirty-credit one on the shape of the work. Cap the reach and you get the
> working cinematographer a production can actually book.

## 6 — The producer stays in control · 2:10–2:35

Go to **Replan**. Kind `Budget`, value `400000`, reason `Financing reduced`. Hit
**Compare plans**.

> Financing drops by a hundred thousand. The agent does not touch the approved baseline.
> It produces a before-and-after proposal — the budget delta, the shoot-day delta, and
> what it would have to change.

Click **Approve**.

> The plan only moves when a producer says so.

## 7 — Shared and auditable · 2:35–2:50

Save the shared project, then open **Handoff** and export.

> The project is a real record, not browser storage. Firestore in the cloud, and every
> save writes an audit event. The handoff exports the plan, roster, finance, approvals
> and the evidence behind every recommendation.

## 8 — Close honestly · 2:50–3:00

End on the Overview.

> Credits are real, under IMDb's non-commercial dataset license. Availability, rates and
> location are not modelled, because no public source has them. We would rather show you
> the query than guess.

---

## The 2:00 cut

If the hard cap is two minutes, drop beats 6 and 7 and tighten beat 3. Keep 1, 2, 4, 5
and 8 intact. Beat 4 is the submission — everything else is context around it.

## Beats most likely to break on camera

| Risk | Fix before recording |
|---|---|
| Header counters blank | Load `/api/health` first; confirm ClickHouse is connected |
| Cold Cloud Run start makes beat 3 hang | Build the plan once before recording to warm the container |
| A role slate comes back thin | DP and Editor are the reliable ones — rehearse on those, not Casting Director |
| Funnel text too small | Zoom to 110–125% before the take, not during |
| Gemini quota drops mid-take | The deterministic parser still runs; if the badge flips, say so rather than reshooting |

## Recording checklist

- [x] Hosted URL is live: https://reel-crew-10453428907.us-central1.run.app
- [ ] `/api/health` reports ClickHouse connected and the intended Gemini backend
- [ ] Plan built once to warm the container, then browser refreshed
- [ ] The rehearsed role slate returns good candidates
- [ ] Notifications and bookmarks hidden
- [ ] Final cut is at most three minutes, clear audio or subtitles
- [ ] Public or unlisted on YouTube/Vimeo, English audio
- [ ] Repository and hosted URLs in the video description
