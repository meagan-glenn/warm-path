"""Message drafts keyed to the verdict, with the evidence behind each choice.

Every shape has a deterministic scaffold that works with no API key. The rules the
scaffolds follow are drawn from the research summarized in docs/messaging.md:

  length      first touch under 400 characters where possible, never over 800
              (LinkedIn's own InMail data: <400 chars +22% vs average, >1,200 -11%)
  advice      ask for a read or advice, not a favor; advice-seeking raises perceived
              competence and the advisor's willingness (Brooks, Gino, Schweitzer 2015)
  directness  one plain ask; people underestimate how often others say yes by ~50%
              (Flynn and Lake 2008), so do not bury the ask in hedges
  weak ties   the moderately-weak contact is the one most likely to move a job
              (Rajkumar et al., Science 2022), which is why forward-note and cold-peer
              are first-class shapes and not consolation prizes
  follow-up   one follow-up is the biggest single lift; two is the ceiling; then stop
              (Woodpecker and Backlinko sales-email corpora, applied with caution)
  timing      Monday best, Friday -4%, Saturday -8% (LinkedIn InMail data)

Shapes:
  spend            real relationship, right seat: ask for a read on the team
  ask-for-routing  real relationship, wrong seat: who owns the req? plus a blurb
  forward-note     thin relationship, right seat: one question, then offer a blurb
  cold             thin relationship, peer: reason, question, disclosure, small ask
  feedback         for products you have used: three findings, then the disclosure
  blurb            the forwardable two-liner, third person, for the mutual to paste
  followup 1 / 2   day 5-7 bump, day 12-14 close; nothing after

`--llm` (anthropic installed, key set) polishes the scaffold. `--prompt` prints a
paste-ready prompt for any chat model. The human sends every message.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .targets import TargetPerson

MODEL = "claude-opus-5"
SOFT_LIMIT = 400   # characters; LinkedIn's best-performing band
HARD_LIMIT = 800   # above this, response rates fall below average

STYLE = """You write short LinkedIn messages and emails for a job seeker reaching out to a
specific person at a company they applied to. Rules, each backed by outreach research:
- Under 400 characters if you can, never over 800. Shorter messages get more replies.
- Open with one specific reason for the connection, drawn only from the context given.
- Ask for the person's read or advice, not a favor. Advice requests land better than help requests.
- Match the ask to their seat. Recruiter or TA: a one-line state check (still open? anything missing?), never a meeting. Hiring manager or senior in function: their read on fit, answerable in a line. Peer: a real question about their work, then 15 minutes as an option. Wrong function: routing only.
- Make one plain ask. Do not stack hedges; one graceful out is enough.
- Mention the application in a single transparent clause and say plainly it is not the ask.
- Plain, warm, direct. No flattery, no "I hope this finds you well", no "love what you're building".
- Never use em dashes. Use periods, commas, or a middot instead.
- Never invent facts about the person or the company. If context is thin, stay general.
- No subject line, no signature, no bullet points. Output only the message body."""


@dataclass
class DraftInput:
    person_name: str
    person_title: str
    company: str
    role: str                     # role applied for
    relationship: str             # e.g. "strong, 4-year thread" / "cold, connected yesterday"
    verdict: str                  # spend / ask-for-routing / forward-note / cold / skip / feedback
    ask_shape: str                # from targets._verdict, or a one-line description
    hook: str = ""                # user-supplied: why this company, why this person, shared context
    channel: str = "linkedin"     # linkedin | email
    me: str = ""                  # sender's name, for the blurb
    me_line: str = ""             # one line on who the sender is, for the blurb
    findings: list[str] = field(default_factory=list)   # for the feedback shape
    profile_url: str = ""         # sender's link, for the blurb
    role_class: str = "other"     # route (recruiter/TA) / champion (senior) / peer / other; drives the cold ask


def _first(name: str) -> str:
    return name.split()[0] if name.strip() else "there"


def blurb(d: DraftInput) -> str:
    """The forwardable two-liner. Third person, no ask, ends with a link. The mutual pastes it as-is."""
    me = d.me or "[your name]"
    who = d.me_line or "[one line: what you do and the result you are known for]"
    role = d.role or "[role]"
    link = d.profile_url or "[your LinkedIn or portfolio URL]"
    return (
        f"{me} is {who}. They applied for the {role} role at {d.company} and asked me if I knew who runs that team; "
        f"I said I would pass it along. Worth a look: {link}"
    )


def scaffold(d: DraftInput) -> str:
    first = _first(d.person_name)
    hook = d.hook or f"[finish this sentence: I am writing because ... (one specific thing about {first} or {d.company})]"
    role = d.role or "[role]"
    q = f"[one real question about their work at {d.company}]"
    v = d.verdict

    if v == "spend":
        return (
            f"Hey {first}, {hook}\n\n"
            f"I applied for the {role} role and would value your read before I go further: what the team actually cares about, "
            f"and who I should be talking to. 20 minutes whenever suits, and if you end up wanting to put in a word I would not say no."
        )
    if v == "ask-for-routing":
        return (
            f"Hey {first}, {hook}\n\n"
            f"Quick one: I applied for the {role} role at {d.company}. Do you know who owns that req or leads the team? "
            f"Not asking you to carry it, just want it to land with the right person. Two-line version below in case it is easy to forward.\n\n"
            f"---\n{blurb(d)}\n---"
        )
    if v == "forward-note":
        return (
            f"Hey {first}, {hook}\n\n"
            f"{q}\n\n"
            f"Full disclosure, I applied for the {role} role. Not asking you to do anything with that. "
            f"If a two-line note would be easy to forward to whoever runs the team I would be grateful, and a reply here is great too."
            f"\n\n(If they say yes, send the blurb: `warmpath draft \"{d.person_name}\" --target \"{d.company}\" --shape blurb`)"
        )
    if v == "cold":
        if d.role_class == "route":
            # Recruiter or TA. They own the process, not the opinion. Do not ask for their time; ask for a state check.
            who = f" {d.me_line}." if d.me_line else ""
            link = f" {d.profile_url}" if d.profile_url else ""
            return (
                f"Hi {first}, I applied for the {role} role at {d.company}{(' ' + d.hook) if d.hook else ''}.{who} "
                f"Two questions, either is fine to answer in a line: is the role still open, and is there anything you would want "
                f"from me beyond the application? Happy to send it.{link}"
            )
        if d.role_class == "champion":
            # Likely hiring manager or senior in function. Ask for their read on fit, not for a meeting.
            return (
                f"Hey {first}, {hook}\n\n"
                f"{q}\n\n"
                f"Full disclosure, I applied for the {role} role and I think it sits near your team. Not asking you to carry it. "
                f"One question you can answer in a line: is that the kind of profile you are actually hiring for? If yes I will keep going through the front door; if no, I would rather know."
            )
        if d.role_class == "other":
            # Wrong function. The only useful ask is routing.
            return (
                f"Hey {first}, {hook}\n\n"
                f"Quick one: I applied for the {role} role at {d.company}. Do you happen to know who owns that team? "
                f"Not asking for anything beyond a name; I want it to land with the right person."
            )
        return (  # peer
            f"Hey {first}, {hook}\n\n"
            f"{q}\n\n"
            f"Full disclosure, I applied for the {role} role. Not asking you to do anything with that. "
            f"If you are up for 15 minutes on your side of things I would love that, and an answer here is great too."
        )
    if v == "feedback":
        f = d.findings or ["[finding 1, one line]", "[finding 2, one line]", "[finding 3, one line]"]
        lines = "\n".join(f"{i+1}. {x}" for i, x in enumerate(f[:3]))
        return (
            f"Hey {first}, {d.hook or f'I spent my first session in {d.company} this week and wrote down what I hit.'} "
            f"Three things, one line each:\n\n{lines}\n\n"
            f"Full disclosure, I applied for the {role} role, and I would have sent this either way. "
            f"Happy to walk through any of it if useful."
        )
    if v == "blurb":
        return blurb(d)
    return (
        f"(Verdict is SKIP for {d.person_name}: {d.ask_shape})\n"
        f"If you still want to reach out, use --shape cold and keep expectations low."
    )


def followup(d: DraftInput, n: int) -> str:
    """Day 5-7 bump, day 12-14 close. Data says the first follow-up is the big lift and the third is noise."""
    first = _first(d.person_name)
    if n <= 1:
        return (
            f"Hey {first}, bumping this once in case it got buried. Still curious about "
            f"{d.hook or '[the question you asked]'}. No worries if now is not the time."
        )
    return (
        f"Hey {first}, closing the loop so this is not hanging in your inbox. If it is ever useful to talk "
        f"{d.company} or {d.role or 'the role'}, I am easy to find. Thanks either way."
    )


def length_note(text: str, channel: str = "linkedin") -> str:
    """One-line read on length against LinkedIn's response-rate bands."""
    body = text.split("\n---")[0]  # do not count an attached blurb block
    n = len(body)
    if channel == "email":
        return f"{n} characters."
    if n <= SOFT_LIMIT:
        return f"{n} characters. Under {SOFT_LIMIT}: LinkedIn's best-performing band."
    if n <= HARD_LIMIT:
        return f"{n} characters. Under {HARD_LIMIT} is fine; under {SOFT_LIMIT} does about 22% better on LinkedIn."
    return f"{n} characters. Over {HARD_LIMIT}: response rates fall below average here. Cut a sentence."


def prompt_for(d: DraftInput) -> str:
    """A paste-ready prompt for any chat model, for people who will not install an SDK."""
    return STYLE + "\n\n" + _context(d) + "\n\nWrite the message."


def _context(d: DraftInput) -> str:
    return "\n".join([
        f"Recipient: {d.person_name}, {d.person_title} at {d.company}",
        f"Channel: {d.channel}",
        f"Relationship: {d.relationship}",
        f"Verdict: {d.verdict}. Their seat: {d.role_class}. Ask shape: {d.ask_shape}",
        f"Role applied for: {d.role or 'unspecified'}",
        f"Sender-supplied hook or context: {d.hook or 'none, keep it general and honest'}",
        *( [f"Findings to include, one line each: " + " | ".join(d.findings)] if d.findings else [] ),
        "",
        "Scaffold to improve (keep its structure and intent):",
        scaffold(d),
    ])


def _client():
    try:
        import anthropic as _a
    except ImportError:
        return None
    return _a.Anthropic()


def llm_draft(d: DraftInput) -> str | None:
    """Return a finished message, or None if the LLM path is unavailable."""
    client = _client()
    if client is None:
        return None
    resp = client.beta.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=STYLE,
        betas=["server-side-fallback-2026-07-01"],
        extra_body={"fallbacks": "default"},
        messages=[{"role": "user", "content": _context(d)}],
    )
    if resp.stop_reason == "refusal":
        return None
    return "".join(b.text for b in resp.content if b.type == "text").strip()


def input_for(tp: TargetPerson, role: str, hook: str, channel: str, **kw) -> DraftInput:
    p = tp.person
    rel = f"{p.tier}, score {p.strength:.0f}; " + ("; ".join(p.reasons) or "no history")
    return DraftInput(p.name, p.position, p.company, role, rel, tp.verdict, tp.ask, hook, channel, role_class=tp.role_class, **kw)


def render(d: DraftInput, use_llm: bool = False, followup_n: int = 0) -> str:
    if followup_n:
        return followup(d, followup_n)
    if use_llm:
        out = llm_draft(d)
        if out:
            return out
        return "(LLM unavailable: install `anthropic` and set ANTHROPIC_API_KEY. Or use --prompt and paste into any chat.)\n\n" + scaffold(d)
    return scaffold(d)


def draft_for(tp: TargetPerson, role: str, hook: str, channel: str, use_llm: bool) -> str:
    """Back-compat wrapper."""
    return render(input_for(tp, role, hook, channel), use_llm)
