# Warm Path

Find the warm paths in your own network into the company you just applied to, and stop spending on the cold ones.

**Status: v0, private, own use.** Scripts over the official LinkedIn data export. Nothing here talks to LinkedIn. See [the spec](../warm-path-spec.md) for the full plan.

## Why

Networking into a visible company fails at the judging step, not the finding step. You can open 200 profiles at the target and read every mutual, but you cannot sustain that past a few applications, and by application eight the process degrades to blind connection requests. Existing tools either fake your network (profile-affinity matching), track contacts you already found, or do real graph work at sales-team prices.

Warm Path ingests your own export, scores every relationship for real strength from your message history, and per target tells you which pairs are worth spending on and which are not.

## What it does not do

No auto-connect, no auto-DM, no scraping, no browser automation, no bulk email finding. LinkedIn restricts accounts that use those tools, and the collateral is your account. The tool reads your export; you send every message.

## Quickstart

1. On LinkedIn: Settings & Privacy, Data privacy, Get a copy of your data. Request the full archive (you want `messages.csv` and `Positions.csv`, not just Connections). It arrives by email as a ZIP.
2. Then:

```bash
python3 -m warmpath ingest path/to/export.zip
python3 -m warmpath people --top 30
python3 -m warmpath target "Lovable" --function cs
python3 -m warmpath target "Ode with Anthropic" --alias "Fractional AI" --function cs --orbit Anthropic --orbit Deloitte
python3 -m warmpath draft "Ryan Boyd" --target Simile --function cs --role "Deployment Strategist" --hook "why you connected"
python3 -m warmpath discover "Ode with Anthropic" --alias "Fractional AI" --function cs
python3 -m warmpath discover Simile --about "synthetic-user AI startup, San Francisco" --function cs
```

Python 3.10+, standard library only for the core. Everything is written to `data/warmpath.db`, which is gitignored along with the export.

Two optional extras, both off until you install them and add a key to `./.env` (also gitignored):

- `pip install anthropic` plus `ANTHROPIC_API_KEY` (or `ant auth login`) turns `draft --llm` from a scaffold into a finished message. Model: `claude-opus-5`.
- `pip install exa-py` plus `EXA_API_KEY` makes `discover` return recruiters, likely hiring managers, and in-function peers at a company from Exa's people index. Public profile URLs, opened by you. Nothing touches LinkedIn.

## Drafts

`draft` picks the message shape from the verdict. The shape that worked in practice for a cold, in-function peer, and the default for `cold` and `forward-note`:

1. One specific reason you connected, not "love what you're building."
2. One genuine question about their work.
3. The application in a single transparent clause, explicitly not the ask.
4. A small ask, their call: answer here, or 15 minutes.

`ask-for-routing` (real relationship, wrong seat) asks who owns the req. `spend` (real relationship, right seat) asks for a read on the team and lets them offer to advocate.

## How scoring works

**Mutual strength** (will this person help me?), 0 to 100, from the export alone: two-way thread exists, message volume with a per-day cap so support bursts do not dominate, thread span, recency, written recommendations, shared former employer, invitation direction, endorsements. Unanswered outreach is a penalty and a flag. Every reason is printed next to the score.

**Target strength** (can this person champion me?), from their title: recruiter or TA (a route to process, not advocacy), senior in your function, senior elsewhere, in-function peer, other.

The output names the weak side of every pair, because the ask is different: strong relationship in the wrong seat means "who runs hiring for this?", right seat with a thin relationship means "would you forward a two-line note?"

## Roadmap

- v1 (in progress): drafts and discovery are in. Still to do: synthetic demo dataset, outcome logging, clean public release.
- v2: guided second-degree flow, optional single-click mutuals capture, relay orchestration across multi-hop intros.
