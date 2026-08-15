# Warm Path: build spec v0.1

Working name. Alternatives at the end. Drafted 2026-08-15 from live research plus a pass over Meagan's own LinkedIn export.

## 1. Thesis

Job seekers targeting visible companies lose not because they can't find people, but because they can't judge them at volume. The information is on every profile. Reading 200 profiles times up to 80 mutuals each, and deciding which pair (mutual + target) is strong on both sides, is where the manual process collapses. Existing tools either fake the network (Jobright matches your profile against their dataset), track contacts you already found (Teal, Huntr, Careerflow), or do real graph work at $99 to $6,500 per month for sales teams (The Swarm, Connect The Dots, Commsor). Nobody joins "the job I applied to" with "my actual relationships" with "the multi-hop ask."

Warm Path is an open-source agent that ingests your own LinkedIn export, scores every relationship for real strength, and, per application, tells you where to spend and where not to.

## 2. Evidence from a real network (4,606 connections, 37k messages)

The single most important number: **1,082 two-way message threads out of 4,606 connections.** Roughly a quarter of "connections" are relationships. The rest is noise. Separating them is the tool's first job.

Three live targets, three different states:

| Target | 1st-degree reach | What a tool would have done |
|---|---|---|
| Lovable | 4 people: one four-year relationship (a former interviewer, now on the CS side), one untested GTM lead, two recruiters | Flag the relationship instantly. Score the recruiters as low-yield before three unanswered messages were spent on them. Suggest the GTM lead as a second route. |
| Anthropic | 2 people, both accepted requests with zero message history | Rank as cheap "who owns hiring for X?" asks, not champion paths. Push to 2nd degree. |
| Ode with Anthropic | Nothing. Company is four weeks old (~100 people, core acquired from Fractional AI). | External discovery of recruiters and hiring managers, plus 2nd-degree via mutuals. Note the LinkedIn company field likely still reads "Fractional AI." |

What broke by hand, in the user's own words: click through 200 people at the target, each with 2 to 80 mutuals, read every mutual, judge whether the mutual is close enough to intro and whether the target is senior enough to champion. Nobody sustains that past a few applications. By application eight the diligent process degrades to blind connection requests with no note.

Design conclusions:
- The 1st-degree scorer alone has real value (Lovable) but a ceiling.
- Two of three targets produce nothing without external target discovery and a 2nd-degree layer. Those are not "later" features.
- Half the value is negative: "these two paths are cold, stop spending on them."

## 3. Positioning

- Against Jobright: "Jobright guesses from your profile. This uses your actual network."
- Against automation tools (Dux-Soup, Waalaxy, Dripify): we never act on LinkedIn. Reported restriction rates for automation users run 20 to 40 percent per quarter. The agent drafts, the human sends.
- Against referral marketplaces (Refer.me, Refermarket): hiring teams increasingly discount stranger referrals. Genuine warm paths are the counter-position.
- Against Sales Navigator ($99 to $150/mo): built for the job seeker's unit of work, the application, not the account list.
- Pricing: free, open source. The category's biggest trust wound is billing hostility (Simplify, Jobright, Teal one-star reviews). Being free is itself a differentiator.

## 4. Red lines and legal posture

Research summary (August 2026):
- LinkedIn's official export is the one blessed bulk artifact. Connections.csv has 7 columns: First Name, Last Name, URL, Email Address, Company, Position, Connected On. Email populated for about 3 percent. Company and title decay roughly 20 percent per quarter. There is a preamble of "Notes:" rows above the header that must be stripped.
- No official API path for an indie US tool. Connections API died in 2015; partner programs exclude individuals. The EEA-only DMA portability API exists and is worth bookmarking, but is useless for a US user base.
- LinkedIn sues scraping vendors out of existence now (Proxycurl sued January 2025, dead by July; ProAPIs sued October 2025). Do not build on real-time LinkedIn scraper APIs.
- Aggregated B2B datasets (People Data Labs, Apollo, Clay) and neural people search (Exa) are the compliant path for enrichment and target discovery. The product never presents itself to LinkedIn's servers.
- Browser extensions that automate or bulk-read are detected and punished; the user's own account is the collateral. A single-click, single-page, user-initiated capture (the CareerOS pattern) is a tolerated gray zone with precedent, not a green light. It must be disclosed plainly in the README.

Rules for the build:
1. Never send, connect, view, or navigate on LinkedIn on the user's behalf. Ever.
2. Bulk data enters only via export upload and third-party indexes.
3. Anything in-session is one click, one page, human-initiated. Optional. Off by default. Disclosed.
4. No bulk mode for email lookup. Per-target, rate-limited, intended for contacting recruiters and hiring managers, whose job is to be contacted.
5. All processing local by default. The messages file is the user's entire DM history; it never leaves the machine unless the user explicitly enables a cloud enrichment call, and even then only names and companies go out, never message content.

## 5. Architecture

Claude Agent SDK, Python, reusing the `second_me` scaffolding pattern. Local SQLite. CLI first, thin web UI later if warranted.

### 5.1 Ingest
- Parse the export ZIP: Connections.csv (spine), messages.csv (relationship strength), Positions.csv (the user's own history, for overlap), Invitations.csv (who reached out to whom), Recommendations and Endorsements (weak but free reciprocity signals).
- Optional enrichment pass: refresh company and title for the connections that matter (top-scored, or those matching a target) via PDL or Apollo free tiers. Not the whole 4,600. Enrich on demand.
- Output: a local graph of people with a relationship-strength score.

### 5.2 Target dossier (per application)
Input: company, role, optionally the JD URL.
- Recruiters and TA at the company: Exa People Search or Apollo/PDL person search by title + company. Zero LinkedIn contact.
- Likely hiring manager and in-role peers: same, filtered by function.
- Company aliases: recent renames, acquisitions, parent entities (Ode = Fractional AI). Ask the model, confirm with the user.
- Adjacent orbit: investors' portfolio, direct competitors, former employers common among current staff. Used to widen the 1st-degree net.
- Optional: waterfall email lookup for the recruiter and hiring manager only (two providers, first verified hit).

### 5.3 Path scoring
A path is a pair (mutual, target), scored on both sides, with the weak side named.

Mutual strength (will they actually intro?), all from the export:
- Reciprocity: two-way thread exists at all (the single strongest cut).
- Thread volume and span: number of messages, days between first and last.
- Recency: last exchange.
- Work overlap: same employer, overlapping dates, from Positions.csv against connection company history.
- Direction of the original invitation.
- Recommendations or endorsements exchanged.
- User override: "close," "would vouch," "barely know." One click. Persisted.

Target strength (can they champion?):
- Function match to the role.
- Seniority: hiring manager or skip, lead in the adjacent function, in-role peer, versus new hire or unrelated function.
- Recruiters scored on a separate axis: route to process, not route to advocacy.
- Tenure, if enrichment provides it.

Output per application: a shortlist of at most five pairs, reasoning shown, plus an explicit "cold" list of people at the target the user is connected to but should not spend on. The two asymmetric cases get different drafts:
- Strong mutual, weak target: "can you tell me who actually runs hiring for this?"
- Weak mutual, strong target: "would you be comfortable forwarding a two-line note?"

### 5.4 Second-degree layer (v2)
No data feed exists. Two mechanisms:
- Guided flow: deep-link the user into LinkedIn's own filtered search (2nd degree + current company = X) and their school's alumni page filtered by company. The user does the browsing.
- Optional clipper: a browser extension that reads the mutual-connections list of the single 2nd-degree profile the user is currently viewing, on click, and hands it to the local graph. No navigation, no background requests, no bulk. Off by default. Disclosed as a ToS gray zone.
Once mutuals are captured, the same pair-scoring runs. This is where the 200-times-80 problem actually gets solved.

### 5.5 Relay orchestration
The novel part. A state machine per application:
- Which paths were chosen, who has been asked, what blurb was forwarded, when.
- Nudge timing per hop.
- Reconciliation when a parallel route (recruiter email) replies while an intro thread is still open.
- Outcome logging, so the score learns which kinds of paths actually convert for this user.
The agent drafts every message. The user sends every message.

### 5.6 Empty state
Must be designed, not defaulted. When no path exists: say so, show the enriched cold route (recruiter and hiring manager from external discovery, email if found, a draft that leads with the strongest specific hook), and suggest the 2nd-degree flow.

## 6. Phases

**v0, this week, own use only.** Scripts against the real export. Ingest, relationship score, per-target 1st-degree shortlist. Run it on the three live targets and one more. Log what it got right and wrong versus what the user already knew. This is user research and it becomes the README story.

**v1, portfolio release.** Clean repo. Ingest + scoring + external target discovery + drafts + empty state. Synthetic demo dataset baked in (never the real export). CLI. README with the three-case table, the "what broke by hand" story, the red lines, and a clear "what this deliberately does not do."

**v2.** Guided 2nd-degree flow, optional clipper, relay orchestration state machine, outcome learning.

Cut list, said out loud in the README: no auto-apply, no auto-connect, no auto-DM, no bulk email finding, no resume tailoring, no job discovery. Other tools do those; this one does paths.

## 7. Risks and open questions

- The tool cannot conjure paths that do not exist. For the hottest companies the honest answer is often "cold route only." The alumni surface and adjacent-orbit inference soften this. They do not eliminate it.
- Message-based strength scoring overweights people you chatted with in a work-tool context (customer support threads inflate counts). Needs a cap on per-day bursts and a downweight for one-sided threads.
- Enrichment cost and freshness: PDL/Apollo free tiers cover a job seeker's volume, but the model must degrade gracefully when they return nothing.
- The clipper's gray zone is a reputational risk on a portfolio piece. Mitigation: off by default, separate package, blunt disclosure, and the product is useful without it.
- Demo problem: real networks cannot be screencast. Synthetic dataset from day one.
- Jobright will look similar at a glance. The differentiation sentence must be in the first paragraph of the README.
- Untested assumption: that a stranger installs a tool for the aggregate benefit when a single application gets 70 percent of the value from a spreadsheet. The v0 self-test on four targets is the cheapest way to find out.

## 8. Portfolio framing

What this shows a hiring manager: product judgment (a narrow, opinionated scope with a visible cut list), user research (a real process run by hand and documented where it broke), constraint-aware design (a legal and platform landscape most builders in this space ignore), and shipping (an agent on a modern SDK with a synthetic demo). The README should be readable by a non-engineer in five minutes.

README outline:
1. One-sentence pitch and the differentiation sentence.
2. The problem, in the user's words. The 200 times 80 story.
3. The three-case table.
4. What it does. What it deliberately does not do.
5. Red lines and why (short, linked to the research).
6. Quickstart with the synthetic dataset.
7. Architecture in one diagram.
8. Roadmap and open questions, honestly.

## 9. Name candidates

Warm Path (working). Backchannel. Mutual. Insider (taken by Jobright's feature name, avoid). Relay (captures the multi-hop idea). Threadline.
