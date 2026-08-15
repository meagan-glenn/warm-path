"""Message drafts keyed to the verdict.

Every verdict has a deterministic scaffold that works with no API key. The shape
is the same one that worked in practice for a cold, in-function peer:

  1. one specific reason you connected (not "love what you're building")
  2. one genuine question about their work
  3. one transparent clause about the application, explicitly not the ask
  4. a small ask, their call

If the `anthropic` package is installed and credentials resolve (ANTHROPIC_API_KEY,
or an `ant auth login` profile), `--llm` turns the scaffold plus context into a
finished message. The agent drafts. The human sends. Nothing here touches LinkedIn.
"""

from __future__ import annotations

from dataclasses import dataclass

from .targets import TargetPerson

MODEL = "claude-opus-5"

STYLE = """You write short LinkedIn messages and emails for a job seeker reaching out to a
specific person at a company they applied to. Rules:
- 90 to 130 words. Plain, warm, direct. No flattery, no "I hope this finds you well".
- Open with one specific reason for the connection, drawn from the context given.
- Ask one genuine question about the person's actual work that they would enjoy answering.
- Mention the application in a single transparent clause and say plainly it is not the ask.
- Close with a small ask that leaves the choice with them (answer here, or 15 minutes).
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
    verdict: str                  # spend / ask-for-routing / forward-note / cold / skip
    ask_shape: str                # from targets._verdict
    hook: str = ""                # user-supplied: why this company, why this person, shared context
    channel: str = "linkedin"     # linkedin | email


def scaffold(d: DraftInput) -> str:
    first = d.person_name.split()[0]
    hook = d.hook or f"[one specific reason you connected with {first}, or why {d.company}]"
    role = d.role or "[role]"
    if d.verdict == "spend":
        return (
            f"Hey {first}, {hook}\n\n"
            f"I applied for the {role} role and would love your read on the team before I go further: "
            f"what they actually value, and who I should be talking to. "
            f"If you're up for 20 minutes I'd really appreciate it, and if it makes sense to put in a word I'd never say no, "
            f"but no pressure either way."
        )
    if d.verdict == "ask-for-routing":
        return (
            f"Hey {first}, {hook}\n\n"
            f"Quick one: I applied for the {role} role at {d.company}. Do you know who owns that req or leads the team? "
            f"Not asking you to carry it, I just want to make sure it lands with the right person. "
            f"Happy to send you the two-line version if that helps."
        )
    if d.verdict == "forward-note":
        return (
            f"Hey {first}, {hook}\n\n"
            f"Genuinely curious about [one real question about their work at {d.company}].\n\n"
            f"Full disclosure, I applied for the {role} role a little while back. Not asking you to do anything with that, "
            f"just didn't want it to feel like a surprise later. If a two-line note would be easy to forward to whoever runs "
            f"that team I'd be grateful, but happy with a reply here too."
        )
    if d.verdict == "cold":
        return (
            f"Hey {first}, {hook}\n\n"
            f"[one real question about their work at {d.company}]\n\n"
            f"Full disclosure, I applied for the {role} role. Not asking you to do anything with that. "
            f"If you're up for 15 minutes on your side of things I'd love that, but happy to take an answer here too."
        )
    return (
        f"(Verdict is SKIP for {d.person_name}: {d.ask_shape})\n"
        f"If you still want to reach out, use the 'cold' shape and keep expectations low."
    )


def _client():
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return None
    import anthropic as _a
    return _a.Anthropic()


def llm_draft(d: DraftInput) -> str | None:
    """Return a finished message, or None if the LLM path is unavailable."""
    client = _client()
    if client is None:
        return None
    context = "\n".join([
        f"Recipient: {d.person_name}, {d.person_title} at {d.company}",
        f"Channel: {d.channel}",
        f"Relationship: {d.relationship}",
        f"Verdict: {d.verdict}. Ask shape: {d.ask_shape}",
        f"Role applied for: {d.role or 'unspecified'}",
        f"Sender-supplied hook or context: {d.hook or 'none, keep it general and honest'}",
        "",
        "Scaffold to improve (keep its structure and intent):",
        scaffold(d),
    ])
    resp = client.beta.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=STYLE,
        betas=["server-side-fallback-2026-07-01"],
        extra_body={"fallbacks": "default"},
        messages=[{"role": "user", "content": context}],
    )
    if resp.stop_reason == "refusal":
        return None
    return "".join(b.text for b in resp.content if b.type == "text").strip()


def draft_for(tp: TargetPerson, role: str, hook: str, channel: str, use_llm: bool) -> str:
    p = tp.person
    rel = f"{p.tier}, score {p.strength:.0f}; " + ("; ".join(p.reasons) or "no history")
    d = DraftInput(p.name, p.position, p.company, role, rel, tp.verdict, tp.ask, hook, channel)
    if use_llm:
        out = llm_draft(d)
        if out:
            return out
        return "(LLM unavailable: install `anthropic` and set ANTHROPIC_API_KEY, or run `ant auth login`)\n\n" + scaffold(d)
    return scaffold(d)
