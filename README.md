# aw-app-business-team — the business-planning agent team

Installs the agents that take a business idea from "somebody noticed a gap"
to "this is worth building, here is what it costs and who it is for" — and
then hand the building itself to the Dev Team:

| Agent | Model | Contract (shipped here) |
|---|---|---|
| **Business Steward** | Sonnet | `business-steward` |
| **Business Scout** | Sonnet | `business-scout` |
| **Business Finance** | Sonnet | `business-finance` |
| **Business Strategist** | Sonnet | `business-strategist` |
| **PM-business** | Opus | `business-pm` |

…wired together by the **Agents Flow: Business Planning**:

```
                        ┌──→ Business Scout
                        ├──→ Business Finance
(plan ticker) → Steward ─┼──→ Business Strategist   (every Nth iteration)
    Source ───┘          ├──→ PM-business ──→ UX Coder - Sonnet  (pilots)
                         └──→ Product Owner ──→ Architect        (graduation)
```

Every edge is two-way: a persona that cannot answer routes back through the
Steward rather than guessing, which is what makes the evidence mandate below
enforceable.

## The loop is entered by the plan ticker, not by Source

This is the one thing to understand before reading anything else here, and
the reason the flow diagram has a door that is not the Source node.

The team drives one **Plan** — the Agents Platform's existing long-running
umbrella above several Targets, with written delivery criteria, a cadence,
and its own JSON memory document. A business Plan sets
`follow_up_agent_slug = "business-steward"`, and from then on the platform's
plan ticker wakes the Steward once per cadence period with that plan's full
state pack. No human clicks anything, and nothing arrives at Source.

The `source` node exists because the flow editor requires exactly one and
because a human firing an iteration by hand is a real secondary door. It is
not how the loop normally runs.

**Zero backend changes were needed for any of that.** No new schema, no new
plan `kind`, no ticker change — the Plan entity already supports everything
this team does. This app is five agents, five contracts and one graph.

## What each persona is for, and what it must not do

The five boundary paragraphs in `skills/*/SKILL.md` are the product. They
were argued out and ratified once on the design card
(`4155bf3b-9510-81ac-8359-c443831beeb6`), and they are reproduced in those
files **verbatim** — `tests/test_manifest.py` fails the build if any of them
is edited, because a boundary that gets "tidied up" quietly becomes a
suggestion. Three of those splits are the load-bearing ones:

- **Scout watches the market; Strategist watches our own traction.** Both
  roles read numbers and both produce insights, which is exactly why they
  collapse into each other if nobody holds the line. Competitors and demand
  signals are the Scout's. Ad performance, A/B outcomes and growth KPIs are
  the Strategist's. Each contract names the other as the owner of what it
  must not do, and the test checks both directions.
- **Finance estimates before anything exists; PM-business decides.** The
  estimate is advisory on the decision and binding as a number: it goes into
  the budget fields that actually refuse a dispatch (Target
  `budget_tokens`/`budget_usd` today — see the caveat below).
- **PM-business decides *whether*; the Product Owner decides *what to
  build*.** PM-business never writes acceptance criteria for an
  implementation. An item that earns real build work leaves as a graduation
  Target through the Dev Team.

### The pursue/park evidence mandate

A pursue/park decision is valid **only** when plan memory already holds, for
that specific opportunity, a Scout finding (`ext['business-scout']`), a
Finance estimate (`ext['business-finance']`) and a Strategist read
(`ext['business-strategist']`).

It is stated on both sides on purpose — PM-business refuses to decide
without them, and the Steward refuses to dispatch the decision until they
exist. That is belt-and-braces rather than redundancy: the failure being
prevented is a pursue call resting on one persona's guess, and afterwards it
leaves no trace at all, so one-sided enforcement would be
indistinguishable from none.

### Money and publishing need a human, every single time

Designing a campaign, an experiment or a demo product is autonomous. The two
things that cannot be undone by deleting a memory entry are not:

- **Real ad spend, a spend change, or any ad-platform credential use** —
  `ask_human` per occurrence (Strategist).
- **Publishing anything outward-facing** — `ask_human` per publish, under
  the labs/sandbox identity, never the main brand (PM-business).

A previous yes never carries over to the next one. Note that neither an
ad-platform integration nor a publishing path exists in this workspace yet;
the rules ship now so that whoever builds the first one inherits them
instead of discovering them afterwards.

## The Steward's model is a recurring bill

The Steward runs on **every cadence tick of every active business plan**, so
its model choice multiplies by the number of plans, forever. Its job is
routing a state pack and enforcing the evidence check — not the deepest
reasoning on the team. It runs on Sonnet; PM-business, which makes the one
genuinely irreversible judgement call, runs on Opus. A test asserts the
Steward is not promoted to Opus by accident.

The same logic sets the Strategist's cadence: traction does not change
hourly, so its review runs every Nth iteration (N in the Steward's own
memory subtree, default 4) rather than every tick.

## Conclusion belongs to a human

Business plans are created with `auto_conclude=false` — **explicitly**,
because the column default is the opposite and a plan created without saying
so silently reverses the ruling. With it off, the Steward's strongest ending
is `proposed_conclude`, which notifies a human and concludes nothing.

That human is also the independent check. A sixth business-QA persona was
considered and deliberately deferred for v1: the conclude endpoint validates
only that evidence *exists*, and judging whether the evidence is any good is
precisely the reviewer's job. Which is why evidence recorded against a
criterion always carries the run id that produced it — a human cannot audit
what they cannot trace back to a run.

## Three nodes name agents another app owns

`product-owner`, `architect` and `ux-coder-sonnet` appear in the flow and
are **not** declared here — they belong to `aw-app-devteam`, declared as a
non-required dependency. That is legal and intentional: the platform stores
a flow node's `agent_slug` as a plain string, the adjacency list injected
into a prompt is a map rather than a fence, and an agent sitting in two
enabled flows simply gets a merged list.

It is not free, though. Without that app installed those three nodes draw
boxes wired to nothing — the graph still seeds, the hand-off target just
is not there. Discovery, costing and traction iterations never touch them;
only graduation and pilots do.

## Why an app, and what reaching an installation means

A team of agents used to be a dozen unrelated objects somebody created by
hand across two UIs: an agent row each, a config bundle, a group, a skill
file each, then a flow graph drawn node by node. Nothing linked them,
nothing checked them, and the failure when one was missing was silent. Here
the ticker makes that worse, not better: it dispatches into
`follow_up_agent_slug` whether or not such an agent exists, and a plan whose
steward is missing just stops moving.

So everything is declared in `aw-app.json` and seeded together.
`business_team_app/plugin.py` registers nothing — there is no route, no
window and no CLI.

Seeding is **create-if-absent, then per-field reconcile**: a later version of
this app can correct a prompt or a skill reference on an already-seeded row,
but any field a human edited in the UI stays theirs. So shipping a corrected
boundary paragraph is an ordinary version bump — not a new slug, and
emphatically not a reason to version the slugs, which double as the
plan-memory `writer_key`s.

## Known caveat: project-plan budgets are not enforced yet

Finance's numbers have real teeth on **Target** budgets (checked at every
dispatch) and on **operation**-kind windowed plan budgets. On a
**project**-kind plan, the platform's dispatch budget check is still a
documented pass, so a figure in `budget_tokens` there is advisory until that
branch is implemented (tracked separately, not in this app). The Finance
contract says so in as many words rather than letting a number imply a
ceiling nobody checks.

## Deliberately not in v1

A business-QA persona (above), any ad-platform integration, A/B variant
hosting, a public publishing path, demand-signal capture, a paid
market-data API for the Scout (v1 is web search and browsing), a second
Kanban board (same board, `business-team` tag), and any AP-MT backend
change. The app ships the team — not a running plan.

## Tests

```bash
python3 -m pytest tests/ -q
python3 tests/validate_manifest.py aw-app.json   # needs aw-marketplace checked out alongside
```

The manifest IS this app, so the suite tests the declarations and the five
contracts: the verbatim boundary paragraphs, the three-way identity of
`slug` / skill id / `writer_key`, both directions of every lane split, the
hub topology, and the joins that otherwise fail silently.
