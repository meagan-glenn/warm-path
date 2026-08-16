# Warm Path

Find the warm paths in your own network into the company you just applied to, and stop spending on the cold ones.

Most "networking" tools either fake your network (matching you to strangers by profile affinity), track contacts you already found, or do real graph work at sales-team prices. Warm Path reads the LinkedIn export you already own, scores every relationship for real strength from your message history, and per application tells you which pairs are worth spending on and which are not. It never touches LinkedIn.

**Status:** v1. Works end to end on a real export; ships with a synthetic one so you can try it in a minute.

## The problem, in the user's words

> I apply to a visible AI company. I open the company page, 200 people. Each one has between 2 and 80 mutuals with me. For every one I have to judge two things: is this mutual actually close enough to me to make an intro, and is this person actually in a seat where they could champion me or at least route me? I can do that for one application. By application eight it degrades to connection requests with no note, and recruiters who ignore me.

The judging step is the bottleneck, not the finding step. That is what this tool does.

## Three real cases

Built and tested on the author's own network (4,606 connections, 37k messages, 1,082 two-way threads). Names withheld; the shapes are exact.

| Case | What the network had | What the tool said | What happened |
|---|---|---|---|
| Company A, applied twice before | One strong ex-colleague (interviewed the author years ago), two recruiters who had ignored two prior notes, one thin peer | `spend` on the ex-colleague; `skip` both recruiters, named as already-tried; `forward-note` for the peer | Note to the ex-colleague sent day one. Recruiter spend stopped. |
| Company B, hot lab | Two connections, both cold, neither in function | `cold` for both, with the explicit "one cheap message, then move on"; empty-state routes shown | No spend. Discovery instead. |
| Company C, new startup | Zero connections under the current name | Empty state, then `--alias` (the company had renamed) found nothing, then `discover` returned the Head of Talent, two recruiters, and the CEO from a public people index | Cold outreach to the right people, with the disclosure-not-ask draft shape. |

A fourth case, a peer at a startup the author had just applied to and did not know how to message without it reading as "hey I applied, let's chat": the `cold` draft shape (specific reason, real question, one-clause disclosure, small ask) is what went out. Outcomes are tracked in `outcomes` and this table will be updated honestly, including the misses.

## What it does

- `ingest` the official LinkedIn export (ZIP or folder). Message content is read for counts and dates and never stored.
- `people`: every relationship scored 0 to 100 with the reasons printed. Tiers: strong, warm, weak, cold-unanswered (you wrote, they never replied), cold-untested.
- `target "Company" --function cs`: everyone you know at the target, each pair scored on both sides. Mutual strength (will they help?) from the export; target strength (can they champion?) from their title. Verdicts: `spend`, `ask-for-routing`, `forward-note`, `cold`, `skip`, with the weak side named. `--alias` for renames and parents, `--orbit` for adjacent companies to seed second-degree asks.
- `draft "Name" --target X`: a message scaffold keyed to the verdict, with a character count against LinkedIn's response-rate bands. `--shape` overrides (including `feedback` for products you have used and `blurb` for the forwardable two-liner a mutual pastes), `--followup 1|2` for the day-5 bump and day-12 close, `--prompt` prints a paste-ready prompt for any chat model, `--llm` finishes it with Claude. Works for people who are not in your network too (`--title`).
- `discover "Company" --function cs`: recruiters, likely hiring managers, and in-function peers at the target from Exa's people index. Public profile URLs. This is the empty state's answer.
- `enrich` then `bridge "Elena Verna" --company Lovable`: the second-degree layer. There is no compliant feed for other people's connections, so the tool infers who of *your* people probably knows the target from overlapping employers and years (public work history from Exa, cached once for your top 150 strong/warm contacts). Each pair is judged on both sides, your relationship observed and their bridge inferred, and it says which is which. Verdicts: `ask-for-intro`, `ask-if-they-know`, `forward-note`, `long-shot`. If nothing overlaps it says so, and that is a real answer.
- `log` and `outcomes`: what you sent, in what shape, and what came back, plus which threads are due a follow-up. The honest record, and the data the scorer will eventually learn from.
- `serve`: all of the above in a local web page for people who would rather not use a terminal.

## What it deliberately does not do

No auto-connect, no auto-DM, no scraping, no browser automation, no bulk email finding, no auto-apply, no resume tailoring, no job discovery. LinkedIn restricts accounts that use automation, and the collateral is your account; scraper vendors get sued out of existence. Other tools do those things. This one does paths. The tool reads your export; you send every message.

## Quickstart with the synthetic dataset

Python 3.10+, standard library only for the core.

```bash
git clone https://github.com/meagan-glenn/warm-path && cd warm-path
python3 -m warmpath demo
```

That writes a fictional export to `demo/export/` (122 people, 16 invented companies, a persona named Sam Rivera) and ingests it into `data/demo.db`. Then:

```bash
python3 -m warmpath --db data/demo.db people --top 15
python3 -m warmpath --db data/demo.db target "Corvid AI" --function cs          # warm case
python3 -m warmpath --db data/demo.db target Halberd --function cs               # cold case
python3 -m warmpath --db data/demo.db target Tessellate --function cs            # zero case, empty state
python3 -m warmpath --db data/demo.db target Tessellate --alias "Fractal Ops" --function cs --orbit "Northwind Ventures" --orbit Meridian
python3 -m warmpath --db data/demo.db draft "Elena Castellano" --target "Corvid AI" --function cs --role "CS Lead" --hook "your post on onboarding handoffs stuck with me"
python3 -m warmpath --db data/demo.db bridge "Nora Fitzgerald" --company "Corvid AI"    # second degree, inferred from career overlap
```

Prefer a screen to a terminal? Same code, same local database:

```bash
python3 -m warmpath --db data/demo.db serve
```

That opens `http://127.0.0.1:8765` with Target, People, Discover, Outcomes, and Setup tabs and a draft drawer with a copy button. Standard library only, bound to localhost; the browser talks to your machine and nothing else.

Tests: `python3 -m unittest discover tests`.

### With your own export

1. LinkedIn: Settings & Privacy, Data privacy, Get a copy of your data. Request the **full archive** (you want `messages.csv` and `Positions.csv`, not just Connections). It arrives by email as a ZIP, usually within a day.
2. `python3 -m warmpath ingest path/to/export.zip`, then the same commands without `--db` (default is `data/warmpath.db`). `data/`, `*.zip`, `*.db`, and `.env` are gitignored.

Two optional extras, both off until you install them and put a key in `./.env`:

- `pip install exa-py` plus `EXA_API_KEY` turns on `discover`. Use `--about "one-line description"` when the company name is a common word.
- `pip install anthropic` plus `ANTHROPIC_API_KEY` turns `draft --llm` from a scaffold into a finished message (model `claude-opus-5`).

## How scoring works

**Mutual strength**, 0 to 100, from the export alone: two-way thread exists (the single strongest cut), message volume with a per-day cap so support bursts do not dominate, thread span, recency, written recommendations, shared former employer, invitation direction, endorsements. Unanswered outreach is a penalty and a flag.

**Target strength**, from their title: recruiter or TA (a route to process, not advocacy), senior in your function, senior elsewhere, in-function peer, other.

The pair verdict names the weak side, because the ask differs. Strong relationship in the wrong seat: "who runs hiring for this?" Right seat with a thin relationship: "would you forward a two-line note?" Recruiter who ignored you twice: stop.

## Draft shapes, and the evidence behind them

The default for `cold` and `forward-note`, and the one that worked for a cold in-function peer:

1. One specific reason you connected. Not "love what you're building."
2. One genuine question about their work.
3. The application in a single transparent clause, explicitly not the ask.
4. One small ask, their call: answer here, or 15 minutes.

`ask-for-routing` asks who owns the req and attaches the forwardable blurb. `spend` asks for a read on the team and lets them offer to advocate. `feedback` leads with three product findings, one line each, then the disclosure. Follow-ups: one bump at day 5, one close at day 12, none after; `outcomes` tells you when they are due.

The rules these follow (under 400 characters, ask for advice not favors, one plain ask, spend on moderately weak ties, follow up once) each trace to a named source: LinkedIn's InMail response data, Brooks/Gino/Schweitzer 2015, Flynn and Lake 2008, Rajkumar et al. in Science 2022, and the large follow-up corpora from sales email. What is evidence, what is judgment, and what we could not find is in [docs/messaging.md](docs/messaging.md).

## Architecture

```
LinkedIn export (zip)                    Exa people index (optional)
        |                                          |
     ingest.py  ---> data/warmpath.db <---     discover.py
        |              (local SQLite)              |
     score.py   mutual strength, tiers             |
        |                                          |
    targets.py  pair verdicts per company  <-------+  (same title classifier)
        |
    enrich.py   public work history for your top contacts (Exa, cached once)
        |
    bridge.py   second degree, inferred: who of mine overlapped with the target
        |
    drafts.py   verdict-keyed scaffolds, optional Claude
        |
   outcomes.py  what was sent, what happened, what is due
        |
     serve.py   local web UI over the same functions (127.0.0.1)
```

Everything is stdlib Python and one SQLite file. Nothing leaves the machine unless you turn on an extra, and even then only a company name and a role go to Exa, and only a draft prompt (no message history) goes to Anthropic.

## Red lines, and why

- Never act on LinkedIn: no connecting, messaging, or scraping. Bulk data comes only from your own export and third-party indexes that maintain their own coverage.
- Message content is never stored, only per-person counts and dates.
- No real network data in this repo, ever. The demo dataset is generated and every name in it is invented.

The full research behind these (what happened to the scraper vendors, why the automation extensions get accounts restricted, what the paid graph tools cost) is in [docs/spec.md](docs/spec.md).

## Roadmap and open questions

- **Second degree, the observed half.** `bridge` infers who knows the target from career overlap, which catches the ex-colleague and misses the conference friend. Reading the actual mutual-connections list is the only way to get the rest, and every bulk way of doing that is a ToS problem. On the table, off by default: a bookmarklet that copies the names on the mutuals page you are already looking at, one click per page, no requests, disclosed as a gray zone. Not built.
- **Learning from outcomes.** The log exists; the scorer does not read it yet.
- **User overrides.** "Close," "would vouch," "barely know," persisted, so a wrong score can be corrected once.
- **Honest limit.** The tool cannot conjure paths that do not exist. For the hottest companies the answer is often "cold route only," and the best it can do is make the cold route a good one.
