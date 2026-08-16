# Decisions: what runs where, why, and how we know if it works

Warm Path has four places where something makes a judgment: the relationship scorer, the people index (Exa), the second-degree inference (bridge and relay), and the draft generator (scaffold, Claude, or a pasted prompt). This page says what each one is, what it was chosen over, what it costs, what "working" means for it, and what is instrumented today versus not. `docs/messaging.md` covers the writing rules; this covers the machinery. Reviewed August 2026.

## 1. Component choices

### 1.1 Relationship scorer: hand-tuned heuristics, not a model

**What it is.** `score.py`, 0 to 100 from the export alone. Two-way thread is the big cut (+30), then log-capped volume (up to +25), thread span, recency, written recommendation (+25), shared employer (+15), invitations, endorsements. Unanswered outreach is an explicit penalty and a `cold-unanswered` flag. Every point comes with a reason string. User overrides (`mark close|vouch|barely|hub`) beat every heuristic.

**Chosen over.** A trained model on the same features, or an LLM reading threads and rating closeness.

**Why.**
- Sample size. One export is roughly a thousand two-way threads and no labels. That is enough to rank with a rule you can read; it is not enough to fit anything without overfitting to one person's habits.
- Explainability is the product. The user has to trust "spend on this person, not that one." A reason string ("4+ yr thread, recommendation received, silent 3+ yrs") is checkable in a second. A weight vector is not.
- Overridability. Because the score is additive and visible, a one-click override is coherent: `close` floors it at 70 and the reason says so. Overrides on top of an opaque model would be arguing with it.
- Privacy. An LLM rating closeness would need to read message text. Warm Path never stores or transmits message content, only counts and dates. That is a red line, not a preference.

**Cost.** Zero. Runs offline in under a second on 4,600 connections.

**How it could be wrong.** It rewards people who message a lot on LinkedIn, and misses close friends who live in iMessage. The `close`/`vouch` overrides exist for exactly this. When outcome data reaches the point where it can be used (section 3), the first thing to test is whether `strong` and `warm` actually reply more than `cold-untested`; if not, the weights are wrong.

### 1.2 People index: Exa

**What it is.** `exa-py`, `category="people"`, used for three things: `discover` (who at the target is a recruiter, leader, or peer), `enrich` (dated work history for your top 150 strong/warm contacts, cached once), and `relay` (rosters for a hub company and a target). Optional; the tool works without it.

**Chosen over.** Scraping LinkedIn (bots or the voyager API), LinkedIn's official APIs, and B2B contact databases (Apollo, People Data Labs, Clay, Proxycurl-style wrappers).

**Why.**
- Compliance. Scraping LinkedIn is a terms violation and gets accounts banned. Not doing it is a stated red line. LinkedIn's official APIs do not expose other people's connections or work history to individuals.
- The one field that matters. The second-degree inference lives or dies on **dated** work history: company, title, from, to. Exa's people entities return that structure. Most contact databases sell current title and email; the dates are thin or paid extra.
- Cost shape. Pay per query, no seat, no minimum. Enriching 150 contacts is 150 queries once, then cached. A job seeker is not a sales team; seat-priced tools are the wrong shape.
- Search, not lookup. `discover` needs "recruiters at Wispr Flow (voice dictation)" answered as a search, not a filter over a fixed schema. Exa's neural search does that with an `about` hint for ambiguous company names.

**Cost.** Roughly a few cents per query at 2026 pricing; a full enrich plus a dozen discovers and two relays was under five dollars for the author's network. Exact numbers depend on plan; the tool prints how many queries it is about to run.

**How it could be wrong.** Coverage: Exa does not index everyone, and the "none" bucket in `enrich --status` is the visible measure. Identity: `lookup` matches on first and last name plus current company; a common name at a large company can hit the wrong person. Confidence is stored (`high` = name and company matched, `medium` = name only) and `bridge` prints "verify it is them" on medium.

**What we would swap it for.** Anything with the same dated-history structure and a compliant source. The interface is `enrich.lookup(name, company) -> Profile`; nothing else in the code knows it is Exa.

### 1.3 Second degree: inferred from career overlap, not observed

**What it is.** `bridge.py` and `relay.py`. There is no compliant feed for other people's connections. Instead: two people who spent 24 or more months at the same employer at the same time score 45; colleagues right now score 45; six months together 30; brief overlap 12; same employer different years 8; unknown dates 15. Large employers (Google, Amazon, McKinsey and so on) are downweighted to 35 percent in relay because sharing an employer of 100,000 people means little. Universities, self-employment and consulting are skipped.

**Chosen over.** Asking the user to paste the mutual-connections list from LinkedIn (rejected in testing: 80-odd names, two or three real relationships, nobody reads it), a browser extension that reads the mutuals page (works, but it is a gray zone under LinkedIn's terms and it is the first step toward the thing the tool promised not to do), and buying graph data.

**Why.** Career overlap is the same inference a person makes in their head ("she was at Amplitude when he was, they probably know each other"), it uses only public data, and it is wrong in a way the user can see and check. Every output says which side is observed (your relationship, from the export) and which is inferred (theirs, from overlap).

**Cost.** Exa queries as above; the math is free.

**How it could be wrong.** Overlap does not imply acquaintance, especially at 500-plus companies. This is the single most important thing to measure (section 3, intro-ask precision), because if the mutuals the tool names turn out not to know the target most of the time, the feature should be cut or the thresholds raised.

### 1.4 Draft generator: scaffold first, Claude optional, prompt for anyone

**What it is.** Three paths for the same `DraftInput`:
- `scaffold`: deterministic templates keyed to verdict and seat, in `drafts.py`. Default. Zero cost, offline, always available.
- `claude-opus-5` (`--llm`): the scaffold plus a system prompt containing the research rules is sent to Claude, which returns a finished message. Uses the Anthropic SDK with server-side fallback so a model outage degrades to the scaffold, not to an error. Only the draft prompt leaves the machine, never message history.
- `prompt-paste` (`--prompt`): the same context printed as a paste-ready prompt for any chat model the user already has open.

**Chosen over.** LLM-only drafting (no scaffold), a smaller or cheaper model, a local model.

**Why.**
- Scaffold first because the message shape is the product decision (which ask, to which seat, how long) and it should not depend on a model call, an API key, or a bill. The research in `messaging.md` is encoded in the templates and in `STYLE`, so both paths obey it.
- Claude Opus 5 for the optional polish because the job is a short, high-stakes piece of writing where tone matters more than throughput; the cost is one message at a time, so the most capable model is affordable. If the outcome data ever shows the scaffold replies as often as the polished version, the LLM path is a convenience, not a lift, and the doc will say so.
- Prompt-paste because most of the intended users have a chat window open and will not install an SDK. It also makes the tool model-agnostic by design: swap the model by pasting somewhere else.

**Cost.** Scaffold: none. Claude: fractions of a cent per draft at 2026 pricing. Prompt-paste: whatever the user already pays.

**How it could be wrong.** The LLM can add hedges, warmth, or length that the scaffold deliberately avoids. `length_note` runs on the output either way, so a draft that drifts over 400 or 800 characters is flagged. The `STYLE` prompt says no hedges, one ask, seat-matched; whether the model obeys is checked by reading, and eventually by the generator column in the report.

### 1.5 Runtime: standard library, SQLite, localhost

Not an AI choice but it constrains all of them. No framework, no server beyond `http.server`, one database file, bound to 127.0.0.1. Reason: the input is a person's entire LinkedIn message history. The fewer moving parts, the shorter the list of things that could leak it. The `serve` UI exists so people who do not use a terminal can use the tool; it does not change what leaves the machine.

## 2. What "working" means

The tool makes predictions. Each draft says: this verdict, this shape, to this seat, made this way, will get a reply. The log is where those predictions meet reality.

| Question | Metric | Where it comes from |
|---|---|---|
| Does the tool find paths that convert? | Reply rate by verdict (`spend`, `ask-for-routing`, `forward-note`, `cold`, `ask-for-intro`, `relay`) | `outcomes --report`, "By verdict" |
| Are the shapes right for the seat? | Reply rate by seat (`route`, `champion`, `peer`, `other`) | "By seat" |
| Does the second-degree inference hold up? | Intro-ask precision: of the mutuals the tool named who then answered, how many actually knew the target (`intro-made`/`replied` vs `not-close`) | "Intro-ask precision" |
| Is the LLM polish worth it? | Reply rate by generator (`scaffold` vs `claude-opus-5` vs `prompt-paste` vs `hand`) | "By generator" |
| Is the scorer calibrated? | Reply rate for `strong`/`warm` vs `cold-untested` (needs the verdict column, which encodes tier) | "By verdict", once there are enough rows |
| Are we faster than doing nothing? | Median days to first reply; and the `hand` generator rows logged before the tool existed as the baseline | "Overall" median, "By generator: hand" |

Rules for reading it:
- A thread counts as settled when it has an answer, or is marked `silent`/`rejected`/`not-close`, or is 14 days old. Younger unanswered threads are shown as open and excluded from the denominator, so a busy week does not look like a bad week.
- Read direction, not decimals, until a bucket has 20 or more settled threads. The report prints this reminder every time.
- The baseline is the user's own pre-tool outreach, logged with `--generator hand`. Two recruiter cold messages with zero replies are already in the author's log for that reason.

## 3. What is instrumented today, and what is not

Instrumented:
- Every send: person, company, shape, channel, date, seat, verdict, generator, note. `draft` prints the exact `log` command with these filled in; the UI's "Log as sent" fills them from the draft that was just made.
- Every status change: `replied`, `silent`, `intro-made`, `call-booked`, `rejected`, `not-close`, with the first positive date recorded for days-to-reply.
- Follow-up timing: day 5 and day 12 flags from the same rows.
- Enrich coverage: `enrich --status` prints how many of the top 150 are `high`/`medium`/`none`.
- The report itself: `outcomes --report`, and the Report panel on the Outcomes tab.

Not instrumented yet, and honest about why:
- **The scorer does not read the log.** Roadmap item. It needs more than a few dozen settled threads before adjusting weights would be anything but noise.
- **A/B on generator.** Rows are tagged, but nothing forces a split. The comparison is observational until there are enough drafts to alternate on purpose.
- **Bridge and relay predictions are not stored as numbers.** The `predicted` column exists for it (bridge score, relay link score) but the CLI does not fill it yet. Once it does, calibration (did 45-point pairs reply more than 15-point pairs?) is one query.
- **Exa recall.** We measure how many contacts Exa could not find, not how many people at a target company `discover` missed. No ground truth for that without scraping, which we do not do.
- **Message quality beyond replies.** A reply is not a job. `call-booked` and `intro-made` are the next rungs and are logged, but offers and hires are not, on purpose: they are months out and depend on far more than the message.

## 4. How to change a decision

Every choice above has an interface behind it: `enrich.lookup`, `drafts.render`, `score.score_all`, `bridge._score_pair`. Swap the implementation, run `python -m unittest`, run `outcomes --report` a month later, and update this page with what moved. If the numbers do not move, say that too. The point of writing the reasons down is that they can be wrong in public.
