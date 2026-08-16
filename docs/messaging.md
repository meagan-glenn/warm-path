# What the drafts are built on

Every rule in `warmpath/drafts.py` traces to one of the findings below. Where the evidence is from sales email rather than job-seeker outreach, it says so. Where there is no evidence and the rule is a judgment call, it says that too. Reviewed August 2026.

## 1. Shorter gets more replies

LinkedIn's own analysis of InMail response rates (Talent Solutions blog, based on platform-wide data): messages under 400 characters get a **22% higher** response rate than average; up to 800 characters is still about 5% above; 800 to 1,200 is 6% below; over 1,200 is 11% below. Only about 10% of InMails are under 400 characters, so brevity is also a way to stand out.

The same dataset: individually written messages get about 15% more replies than bulk sends. Monday is the best day (marginally); Friday is 4% below average and Saturday 8% below.

What the tool does: every draft prints its character count against the 400 and 800 bands. Scaffolds are written to land under 400 before the user's hook. The blurb block on `ask-for-routing` is excluded from the count because the recipient does not have to read it. The CLI reminds you to send Monday to Thursday.

Caveat: InMail is recruiter-to-candidate, not candidate-to-employee. Direction is reversed. The length effect is the most robust finding across every outreach corpus we could find, so we treat it as transferable. The day-of-week effect is small; treat it as a tiebreaker.

Source: [These InMails Get the Best Response Rates, LinkedIn Data Reveals](https://business.linkedin.com/talent-solutions/blog/trends-and-research/2021/these-inmails-get-best-response-rates) (LinkedIn Talent Blog).

## 2. Ask for advice, not for a favor

Brooks, Gino and Schweitzer, *Management Science* 2015: people who ask for advice are rated **more competent**, not less, by the person they ask, and the effect is stronger when the task is hard and the advisor is an expert being asked personally. Liljenquist and Galinsky's earlier work: asking for advice increases the advisor's perspective-taking and their liking of the asker.

What the tool does: `spend` asks for "your read on the team," not for a referral. The referral is left for the other person to offer ("if you end up wanting to put in a word I would not say no"). `cold` and `forward-note` ask a real question about the person's own work before anything else.

Sources: [Smart People Ask for (My) Advice](https://pubsonline.informs.org/doi/10.1287/mnsc.2014.2054) (Brooks, Gino, Schweitzer, Management Science 61(6), 2015); [Asking Advice Makes a Good Impression](https://www.scientificamerican.com/article/asking-advice-makes-a-good-impression/) (Scientific American, on Liljenquist and Galinsky).

## 3. Ask plainly. People say yes more than you think.

Flynn and Lake, *Journal of Personality and Social Psychology* 2008: across field and lab studies, help-seekers underestimated the probability that a direct request would be granted by **as much as 50%**. The mechanism: askers fixate on the cost of saying yes and ignore the social cost of saying no.

What the tool does: one ask per message, one graceful out. Earlier versions of these scaffolds stacked hedges ("no pressure either way," "happy either way," "totally understand if not"). Those are gone. The evidence says the hedging protects the sender's feelings, not the reply rate.

Source: [If You Need Help, Just Ask](https://www.gsb.stanford.edu/faculty-research/publications/if-you-need-help-just-ask-underestimating-compliance-direct-requests) (Flynn and Lake, JPSP 95(1), 2008).

## 4. The moderately weak tie is the one that moves a job

Rajkumar, Saint-Jacques, Bojinov, Brynjolfsson and Aral, *Science* 2022: a causal test on 20 million LinkedIn members over five years (randomized variation in the People You May Know algorithm; 2 billion new ties, 600,000 new jobs). Weak ties increased job mobility more than strong ties, but the relationship is an **inverted U**: the greatest job transmission came from *moderately* weak ties, between the very weakest and average strength.

What the tool does: this is why `forward-note` (thin relationship, right seat) and `cold` peer outreach are first-class shapes and not consolation prizes, and why the scorer separates "cold-untested" (never tried, could be a moderately weak tie) from "cold-unanswered" (tried, ignored, stop). It is also why `--orbit` exists: the adjacent-company contact you know a little is exactly the tie the study says matters.

Caveat: the study measures ties that already existed on LinkedIn and job transitions that followed. It does not measure the reply rate to a message. It supports *where to spend*, not *what to write*.

Source: [A causal test of the strength of weak ties](https://www.science.org/doi/10.1126/science.abl4476) (Science 377(6612), 2022); [MIT IDE summary](https://medium.com/mit-initiative-on-the-digital-economy/study-weak-ties-strong-employment-value-5a16a6884a54).

## 5. Follow up once. Maybe twice. Then stop.

The best large-N follow-up data is from sales-email tools, so treat the numbers as directional. Woodpecker (20 million emails): one follow-up raised reply rate from about 16% to 27%. Backlinko (12 million outreach emails): a single follow-up produced about 66% more replies than the first message alone. Across these corpora, most replies that come from follow-ups come from the first one; the sweet spot is two to three touches total; beyond that unsubscribe and complaint rates climb.

What the tool does: `outcomes` flags a thread at day 5 with no reply (one bump, `--followup 1`) and at day 12 (close the loop, `--followup 2`). There is no `--followup 3`. The close-the-loop message is written to be the last one and to leave the door open, because on LinkedIn the same person will see your name again.

Caveat: sales cadences are optimized for pipeline, not for a relationship you may need later. We took the "one follow-up is the big lift" finding and ignored the "send five" advice on purpose.

Sources: [How Many Follow-Ups to Send](https://whali.co.uk/blog/how-many-follow-ups-to-send) (summarizing Woodpecker and Backlinko corpora); [Woodpecker cold email benchmarks](https://www.mailforge.ai/blog/average-cold-email-response-rates).

## 6. The forwardable blurb

Not a study; a convention that has been stable since Fred Wilson wrote up the double opt-in introduction in 2009, and codified for forwardable emails by Alex Iskold in 2015. The rule: when you ask someone to make an intro, hand them the text they will forward, so the intro costs them one click and no writing. Third person, short, who you are and why this company, a link, no ask on the recipient. The connector adds their own line on top if they want.

What the tool does: `ask-for-routing` appends the blurb automatically. `forward-note` offers it and tells you how to generate it if they say yes. `--shape blurb` prints it alone. `--me-line` and `--url` fill it in.

Sources: [The Double Opt-In Introduction](https://avc.com/2009/11/the-double-optin-introduction/) (Fred Wilson); [How to write a forwardable introduction email](https://www.alexiskold.net/2015/06/24/how-to-write-a-forwardable-introduction-email/) (Alex Iskold).

## 7. Referrals convert. This is why any of it matters.

Widely reported industry figures put referrals at roughly 30 to 40 percent of hires at larger companies while being a small fraction of applicants, and referred candidates are hired at several times the rate of job-board applicants. These come from vendor and survey aggregates (Jobvite, SHRM, referral-software vendors) rather than a single controlled study, so they are quoted here as an order of magnitude, not a precise number. The direction is not in dispute.

## 8. Match the ask to the seat

The relationship verdict says how much you can ask for. The person's seat says what to ask for. A cold message to a recruiter, a hiring manager, and a peer are three different messages:

| Seat | What they can do | The ask | What not to do |
|---|---|---|---|
| Recruiter / TA (`route`) | Own the process, not the opinion | One-line state check: is the role still open, is anything missing from my application; one line on you; your link | Ask for 15 minutes. Their calendar is the scarcest thing they have and a call is not how they route you. |
| Hiring manager / senior in function (`champion`) | Form an opinion on fit | Their read, answerable in a line: "is this the profile you are actually hiring for?" plus one real question about their work | Ask them to carry your application. Let them offer. |
| Peer (`peer`) | Tell you what it is like inside; sometimes refer | A real question about their work, then 15 minutes as an option | Pitch yourself. They are not evaluating you. |
| Other function (`other`) | Point you to a name | Routing only: who owns this team? | Anything more than a name. |

Evidence: the advice-seeking effect (section 2) is about people who *can* form a view, so it applies to champions and peers, not to process owners. LinkedIn's InMail data (section 1) rewards specificity and brevity, and the recruiter shape is the most specific and shortest of the four. The rest is judgment from having sent the wrong ask to the wrong seat.

## 9. Intro asks: let the mutual say no

`ask-for-intro` is a real ask (Flynn and Lake: make it plainly), with the blurb attached so the cost to them is one paste, and an explicit out ("if you do not know them well enough, just say so"). The out is not a hedge; it is there because the tool *inferred* that they know the target and could be wrong, and a mutual who is asked to intro someone they barely know either declines awkwardly or makes a weak intro. `ask-if-they-know` exists for the thin-overlap case: check first, ask nothing yet. Both are judgment; the double opt-in convention (section 6) is the closest thing to a standard.

## 10. Relay asks: make the hallway cost one paste

`relay` asks your contact to ask *their* coworker. Two hops of goodwill, so the message does three things the evidence supports: names the specific coworker and why (specificity, section 1), hands over a blurb the contact can forward without writing (section 6), and offers a clean exit ("if it is awkward, say so and I will go cold"), because a friend who feels cornered into a hallway ask makes a bad one. The tool says out loud that everything past your contact is inferred; the ask should too.

## What is judgment, not evidence

- **The disclosure clause.** "Full disclosure, I applied. Not asking you to do anything with that." No study tests this. It comes from the author's own experience that the alternative, a friendly message with a hidden agenda, reads as exactly that when the ask arrives later. Transparency here is a bet on trust over cleverness. Outcomes are logged so this can be checked over time.
- **The feedback shape.** Product feedback as an opener for a PLG company is a hypothesis with one data point (a CPO who accepted the connection). It is in the tool because it is the only shape that lets you demonstrate the job instead of asking for it.
- **The 5-day and 12-day thresholds.** The corpora say "a few days apart" and "two or three total." The specific days are ours.

## What we could not find

- Any controlled study of job-seeker-to-employee outreach reply rates. Everything above is recruiter-to-candidate, sales-to-prospect, or lab studies of asking. If you know of one, open an issue.
- Whether the "advice not favor" effect survives when the recipient knows an application is pending. The transparency clause tests this in the field, one message at a time.
