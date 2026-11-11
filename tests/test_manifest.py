"""The manifest IS this app.

There is no route, no window and no CLI here — everything the app delivers is
a declaration in ``aw-app.json`` that some other component seeds. So the only
things worth testing are that those declarations are well-formed and
internally consistent, and that the five skill files still say what was
ratified — which is exactly what breaks silently otherwise: an agent naming a
skill slug nobody ships seeds fine and then runs with no contract, a flow node
naming an agent that isn't declared draws a box wired to nothing, and a
"tidied up" boundary paragraph re-opens a lane split that was decided once.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1]
MANIFEST = APP_DIR / "aw-app.json"

#: The five personas, in the order the loop usually walks them. These slugs
#: are NOT cosmetic: each one doubles as the persona's plan-memory
#: ``writer_key`` and as the id of the skill that defines it, so renaming one
#: orphans every memory subtree written under the old name and silently
#: detaches the contract from the agent. Pinned here for that reason.
PERSONAS = ("business-steward", "business-scout", "business-finance",
            "business-strategist", "business-pm")

#: Agents this app's flow names but does NOT declare — they belong to
#: aw-app-devteam. A flow node is a plain slug, so this is legal and
#: deliberate ("the flow is a map, not a fence"), and an agent sitting in two
#: enabled flows just gets a merged adjacency list. Pinned so that adding a
#: fourth borrowed node is a decision somebody makes on purpose.
BORROWED = ("product-owner", "architect", "ux-coder-sonnet")

#: The boundary paragraphs, verbatim, as ratified on the design card
#: (4155bf3b-9510-81ac-8359-c443831beeb6, the architect's finalization
#: comment). Duplicated here ON PURPOSE: the paragraphs are the whole point
#: of the five skills, and the failure mode they guard against is not a
#: deleted file but a later edit that paraphrases a lane split into
#: ambiguity. A diff against a literal is the only check that catches that.
BOUNDARIES = {
    "business-steward":
        "Each tick you receive the plan state pack; read the memory digest first. Route to whichever persona the plan's current gap names — discovery → business-scout, costing → business-finance, traction/GTM → business-strategist, pursue/park-ready → business-pm, graduated build item → product-owner (Dev Team entry) — via `run_agent_async`, then close with `finish_plan_iteration` using the decision that names what actually happened. Before dispatching business-pm for a pursue/park, verify the three ext subtrees exist for that opportunity (business-scout, business-finance, business-strategist) — you are the enforcement point of that mandate. Dispatch business-strategist's traction review every Nth iteration (N kept in your own memory subtree, default 4), not every tick. Business plans run `auto_conclude=false`: your strongest conclusion move is `proposed_conclude` — a human concludes. When recording criterion evidence, always carry the source run id so the human at conclude can audit it. Maintain the shared `summary` (≤2000 chars — every future cycle reads it first) and your own state under `writer_key='business-steward'`.",
    "business-scout":
        "You watch the MARKET: competitors, demand signals, emerging opportunities, gaps. You do not evaluate our own products' traction — ad performance, A/B outcomes and growth KPIs belong to the Strategist. You surface opportunities with evidence; you never propose solutions and never decide pursue/park — that is PM-business's call. Write every finding worth keeping into plan memory via `update_plan_memory` under `writer_key='business-scout'`: one entry per opportunity (source, signal, date, confidence); prune your own subtree before it crowds the document's 64 KiB cap. v1 tooling is web search and browsing only — no paid market-data API; say so in your findings when a question needs data you cannot reach.",
    "business-finance":
        "You estimate BEFORE anything is built: cost-to-build, cost-to-run, rough ROI/pricing hypothesis. You advise — PM-business decides — but your numbers have teeth: write them into the enforced budget fields (Target `budget_tokens`/`budget_usd` via create_target/update_target today; Plan-level budgets once project-plan enforcement lands). Record every estimate under `writer_key='business-finance'`, one entry per opportunity, with its assumptions stated so a later revision can say what changed.",
    "business-strategist":
        "You watch OUR traction: campaign performance, A/B outcomes, growth KPIs, audience fit. You do not scan the market for new opportunities — competitor and demand discovery belong to the Business Scout. You define audience/ICP and GTM as sections of the Plan's needs_strategy, and you design ad campaigns and A/B tests freely — but any REAL ad spend, spend change, or ad-platform credential use requires explicit human approval EVERY time (`ask_human`); design is autonomous, money is not. Record metrics and strategy decisions under `writer_key='business-strategist'`.",
    "business-pm":
        "You decide WHETHER an opportunity is worth pursuing — problem statement, target user, hypothesis, success metric, pursue/park — and you own the Plan's delivery criteria. You do not scope build work: how a graduated item becomes a buildable card belongs to the product-owner, and you never write acceptance criteria for implementation. A pursue/park decision is valid ONLY when plan memory already contains, for that opportunity, a Scout finding (`ext['business-scout']`), a Finance estimate (`ext['business-finance']`) and a Strategist read (`ext['business-strategist']`) — if any is missing, request it through the steward rather than deciding without it. You may build fake/demo products for adherence testing with ux-proto + ux-coder-sonnet autonomously; pilots are disposable scratch projects by default, and promotion into a real repo is a graduation Target through Dev Team, never an in-place conversion. PUBLISHING anything outward-facing requires human approval per publish (`ask_human`) and the labs/sandbox identity, never the main brand. Record decisions under `writer_key='business-pm'`.",
}


def _strings(value):
    """Every string leaf in a nested manifest value."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v)


@pytest.fixture(scope="module")
def manifest() -> dict:
    return json.loads(MANIFEST.read_text())


@pytest.fixture(scope="module")
def spec(manifest) -> dict:
    return manifest["contributes"]["agents"]


def _neighbours(spec, *, agent_slug=None, group_slug=None):
    """Who a node can hand off to, named by agent slug, the way the platform
    itself resolves it (agents-platform core/executor.py::_agents_flow_context).

    Two things that trip up a naive read of the graph and are asserted on
    here because the executor does them: edges are **undirected** for the
    purpose of the adjacency list injected into a prompt, and a group node
    expands to its members.
    """
    flow = spec["agent_flows"][0]
    by_id = {n["id"]: n for n in flow["graph"]["nodes"]}
    mine = {nid for nid, n in by_id.items()
            if (agent_slug and n.get("agent_slug") == agent_slug)
            or (group_slug and n.get("group_slug") == group_slug)}
    assert len(mine) == 1, f"expected exactly one node for {agent_slug or group_slug}"

    def expand(node):
        if node["type"] == "agent":
            return {node["agent_slug"]}
        if node["type"] == "group":
            return {a["slug"] for a in spec["agents"]
                    if a["group_slug"] == node["group_slug"]}
        return {node["type"]}  # the source node has no agent behind it

    out = set()
    for e in flow["graph"]["edges"]:
        far = e["target"] if e["source"] in mine else (
            e["source"] if e["target"] in mine else None)
        if far is not None:
            out |= expand(by_id[far])
    return out


def test_manifest_is_valid_json_with_the_expected_identity(manifest):
    assert manifest["id"] == "business-team"
    assert manifest["manifest_version"] == 1
    assert manifest["tier"] == "inprocess"


def test_declares_the_capability_its_contributions_need(manifest):
    # Core rejects contributes.agents without this — a missing capability
    # fails the install rather than silently dropping the contribution.
    assert "agents:contribute" in manifest["permissions"]


def test_ships_the_whole_team_the_app_is_named_for(spec):
    assert {a["slug"] for a in spec["agents"]} == set(PERSONAS)


def test_each_persona_slug_is_also_its_writer_key_and_its_skill_id(manifest, spec):
    """One slug, three jobs: the agent row, the skill that defines it, and the
    plan-memory ``writer_key`` its entries live under.

    The design card chose that deliberately — the steward's enforcement check
    looks for ``ext['business-scout']`` and friends by name, so a skill id
    that drifted from its agent slug would leave the enforcement reading a
    subtree nobody writes. Asserting the three-way identity is cheaper than
    discovering it from a pursue decision that passed a check on an empty
    subtree.
    """
    shipped = {s["id"]: s["path"] for s in manifest["contributes"]["skills"]}
    assert set(shipped) == set(PERSONAS)
    for slug, path in shipped.items():
        assert path == f"skills/{slug}/SKILL.md", slug
    for agent in spec["agents"]:
        assert agent["skill_slugs"] == [agent["slug"]], agent["slug"]


def test_every_skill_still_carries_its_ratified_boundary_paragraph(manifest):
    """The one test this app exists for.

    Everything else here guards a join between two declarations. This guards
    the content: five paragraphs that divide the lanes (market vs our own
    traction, estimate vs decide, decide-whether vs scope-the-build) and
    attach a human to the two irreversible actions (ad spend, publishing).
    They were argued out once and ratified; a later agent "improving" the
    prose is how a boundary quietly becomes a suggestion.
    """
    for skill in manifest["contributes"]["skills"]:
        text = (APP_DIR / skill["path"]).read_text()
        assert BOUNDARIES[skill["id"]] in text, (
            f"{skill['id']}'s SKILL.md no longer contains its ratified "
            f"boundary paragraph verbatim")


def test_every_skill_names_its_own_writer_key_and_no_other(manifest):
    """A persona writing into another's subtree breaks the steward's
    enforcement check and is unreadable afterwards, so each contract names
    exactly one writer_key: its own.
    """
    for skill in manifest["contributes"]["skills"]:
        text = (APP_DIR / skill["path"]).read_text()
        assert f"writer_key='{skill['id']}'" in text, skill["id"]
        for other in PERSONAS:
            if other != skill["id"]:
                assert f"writer_key='{other}'" not in text, (
                    f"{skill['id']} tells its agent to write under {other}")


def test_the_two_market_watching_lanes_point_at_each_other(manifest):
    """Scout = the market, Strategist = our own traction. That split is the
    one most likely to collapse in practice, because both roles read numbers
    and both produce "insights" — so each contract names the other as the
    owner of what it must not do, and the test checks both directions rather
    than trusting one.
    """
    scout = (APP_DIR / "skills/business-scout/SKILL.md").read_text()
    strategist = (APP_DIR / "skills/business-strategist/SKILL.md").read_text()
    assert "belong to the Strategist" in scout
    assert "belong to the Business Scout" in strategist


def test_the_pursue_park_mandate_is_stated_on_both_sides(manifest):
    """PM-business may not decide without a Scout finding, a Finance estimate
    and a Strategist read, and the steward refuses to dispatch that decision
    until all three exist. Belt-and-braces on purpose: the failure being
    prevented (a pursue call resting on one guess) leaves no trace at all
    afterwards, so one-sided enforcement is indistinguishable from none.
    """
    pm = (APP_DIR / "skills/business-pm/SKILL.md").read_text()
    steward = (APP_DIR / "skills/business-steward/SKILL.md").read_text()
    for subtree in ("business-scout", "business-finance", "business-strategist"):
        assert f"ext['{subtree}']" in pm, subtree
        assert f"ext['{subtree}']" in steward, subtree
    assert "enforcement point" in steward


def test_the_two_irreversible_actions_require_a_human_every_time(manifest):
    """Real ad spend (Strategist) and outward-facing publishing (PM-business)
    are the only two things this team can do that cannot be undone by
    deleting a memory entry. Both are gated on `ask_human`, per occurrence —
    a standing approval is exactly what the rule refuses.
    """
    strategist = (APP_DIR / "skills/business-strategist/SKILL.md").read_text()
    assert "ask_human" in strategist
    assert "EVERY time" in strategist
    pm = (APP_DIR / "skills/business-pm/SKILL.md").read_text()
    assert "ask_human" in pm
    assert "per publish" in pm


def test_the_steward_never_concludes_a_plan_itself(manifest):
    """auto_conclude=false is the ratified posture for business plans, and the
    column default is the opposite — so the contract has to say both halves:
    the strongest move is `proposed_conclude`, and a human concludes.
    """
    steward = (APP_DIR / "skills/business-steward/SKILL.md").read_text()
    assert "auto_conclude=false" in steward
    assert "proposed_conclude" in steward
    assert "a human concludes" in steward


def test_the_steward_is_not_on_the_most_expensive_model(spec):
    """The steward runs on EVERY cadence tick of EVERY business plan, so its
    model is a recurring bill rather than a one-off choice — and its job is
    routing a state pack, not the deepest reasoning on the team (that is
    PM-business's pursue/park call, which is why that one is on Opus).

    Asserted as "not the deepest model" rather than a pinned slug, so a
    future retune can move it without rewriting the test, but cannot
    accidentally promote the one agent whose cost multiplies by the number of
    active plans.
    """
    steward = next(a for a in spec["agents"] if a["slug"] == "business-steward")
    assert steward["model_slug"] != "claude-runner-opus"
    pm = next(a for a in spec["agents"] if a["slug"] == "business-pm")
    assert pm["model_slug"] == "claude-runner-opus"


def test_the_steward_is_the_hub_and_reaches_every_persona(spec):
    """The loop's shape: one router, four specialists, plus the Dev Team door.

    The ticker only ever wakes the steward, so anything it cannot reach is
    unreachable in practice — a persona off this list is an agent that seeds,
    appears in the UI, and never runs.
    """
    reachable = _neighbours(spec, agent_slug="business-steward")
    assert {"business-scout", "business-finance", "business-strategist",
            "business-pm"} <= reachable
    # The graduation door: an item PM-business pursued becomes a Dev Team
    # Target, and the steward is who hands it over.
    assert "product-owner" in reachable
    # Source is the SECONDARY entrance — a human or another agent firing an
    # iteration by hand. The primary one is the plan ticker, which is not a
    # flow node at all (see the flow's own description).
    assert "source" in reachable


def test_pm_business_reaches_the_ux_coder_for_pilots(spec):
    """PM-business builds throwaway demo products with ux-proto +
    ux-coder-sonnet autonomously — that is its own contract's wording, so the
    graph has to make the hand-off reachable or the skill is lying to it.
    """
    assert "ux-coder-sonnet" in _neighbours(spec, agent_slug="business-pm")


def test_the_flow_borrows_exactly_three_agents_from_another_app(manifest, spec):
    """Three nodes name agents aw-app-devteam owns. That is legal — the
    platform stores agent_slug as a plain string and the injected adjacency
    list is a map rather than a fence — and it is the whole mechanism by which
    a graduated business item enters the Dev Team instead of being rebuilt
    here.

    What it is NOT is free: without that app installed those three nodes draw
    boxes wired to nothing. Hence the declared dependency, asserted with it.
    """
    declared = {a["slug"] for a in spec["agents"]}
    wired = {n["agent_slug"] for n in spec["agent_flows"][0]["graph"]["nodes"]
             if n["type"] == "agent"}
    assert wired - declared == set(BORROWED)
    assert declared <= wired, "every persona this app ships is in the flow"
    depends_on = {d["id"] for d in manifest["dependencies"]["apps"]}
    assert "devteam" in depends_on


def test_every_flow_edge_connects_two_real_nodes(spec):
    for flow in spec["agent_flows"]:
        ids = {n["id"] for n in flow["graph"]["nodes"]}
        for edge in flow["graph"]["edges"]:
            assert edge["source"] in ids, edge
            assert edge["target"] in ids, edge


def test_no_node_is_wired_to_nothing(spec):
    """A node with no edge is the quietest possible mistake: it renders in the
    flow editor, it seeds without error, and it injects nothing into anybody.
    """
    for flow in spec["agent_flows"]:
        touched = set()
        for edge in flow["graph"]["edges"]:
            touched |= {edge["source"], edge["target"]}
        for node in flow["graph"]["nodes"]:
            assert node["id"] in touched, node["id"]


def test_the_flow_has_exactly_one_source_and_it_is_called_source(spec):
    # The flow editor keys its single entry node on the literal id "source";
    # a graph that re-opens without one loses where work enters the team.
    for flow in spec["agent_flows"]:
        sources = [n for n in flow["graph"]["nodes"] if n["type"] == "source"]
        assert len(sources) == 1, flow["slug"]
        assert sources[0]["id"] == "source"


def test_the_flow_description_says_how_the_loop_is_actually_entered(spec):
    """The Source node is a half-truth and the description is where that gets
    corrected: this team is woken by the plan ticker through a Plan's
    `follow_up_agent_slug`, not by anything arriving at Source. An enabled
    flow injects its adjacency into every member's prompt, so a description
    that implied Source was the entrance would teach five agents to wait for
    work that arrives somewhere else.
    """
    flow = spec["agent_flows"][0]
    assert "follow_up_agent_slug" in flow["description"]
    assert "plan ticker" in flow["description"]
    assert "auto_conclude=false" in flow["description"]


def test_the_flow_is_enabled(spec):
    # Unlike a scheduled task, an Agents Flow that isn't enabled does nothing
    # at all — no context injection, no handoff guidance. A disabled flow is
    # indistinguishable from not shipping one.
    for flow in spec["agent_flows"]:
        assert flow.get("enabled") is True, flow["slug"]


def test_every_flow_node_has_a_position(spec):
    # Positions are editor-only, but omit them and every node stacks at the
    # origin the first time somebody opens the flow.
    for flow in spec["agent_flows"]:
        for node in flow["graph"]["nodes"]:
            assert set(node.get("position", {})) == {"x", "y"}, node["id"]


def test_every_flow_group_node_names_a_group_this_app_declares(spec):
    """This app wires agents individually today — five personas with five
    distinct positions, no family of model variants to collapse. The check
    stays anyway: a group node whose group_slug matches nothing expands to an
    empty member list, silently.
    """
    declared = {g["slug"] for g in spec["groups"]}
    for flow in spec["agent_flows"]:
        for node in flow["graph"]["nodes"]:
            if node["type"] == "group":
                assert node["group_slug"] in declared, node["id"]


def test_agents_reference_a_declared_config_and_group(spec):
    configs = {c["slug"] for c in spec["agent_configs"]}
    groups = {g["slug"] for g in spec["groups"]}
    for agent in spec["agents"]:
        assert agent["agent_config_slug"] in configs, agent["slug"]
        assert agent["group_slug"] in groups, agent["slug"]


def test_the_group_prompt_carries_the_shared_team_rules(spec):
    """Group instructions are prepended to a member's own system prompt, and
    an agent belongs to exactly one group — so the rules every Business Team
    agent shares live in this one file. If the team is ever split into
    lanes the way the Dev Team was, each new group's prompt has to restate
    them or they silently stop reaching whoever moved out.
    """
    for group in spec["groups"]:
        text = (APP_DIR / group["instructions_file"]).read_text()
        assert "knowledge_search" in text, group["slug"]
        assert "Report what is true" in text, group["slug"]
        assert "Hand off rather than guess" in text, group["slug"]
        # The two rules whose cost is money rather than rework.
        assert "ask_human" in text, group["slug"]
        assert "update_plan_memory" in text, group["slug"]


def test_referenced_files_exist(manifest, spec):
    for skill in manifest["contributes"]["skills"]:
        assert (APP_DIR / skill["path"]).is_file(), skill["path"]
    for agent in spec["agents"]:
        ref = agent.get("system_prompt_file")
        assert ref and (APP_DIR / ref).is_file(), agent["slug"]
    for group in spec["groups"]:
        ref = group.get("instructions_file")
        assert ref and (APP_DIR / ref).is_file(), group["slug"]


def test_every_persona_prompt_points_at_its_own_skill(spec):
    """The system prompt is a pointer, not the contract — so the one thing it
    must get right is which contract. A prompt naming the wrong skill (or no
    skill) produces an agent that improvises the job from four paragraphs.
    """
    for agent in spec["agents"]:
        text = (APP_DIR / agent["system_prompt_file"]).read_text()
        slug = agent["slug"]
        assert f"skills/{slug}/SKILL.md" in text, slug
        assert f'name="{slug}"' in text, slug


def test_no_declaration_marks_a_card_finished_on_dispatch(spec):
    """kanban_target_status is applied when a run is DISPATCHED, not when it
    finishes (agents-platform core/executor.py::_auto_set_kanban_status), so a
    terminal status here would mark a card finished the moment an agent picked
    it up. Guarded as a test because the field reads like an on-completion
    setting.
    """
    terminal = {"done", "ready_to_deploy", "auto_resolved", "archived"}
    for kind in ("agents", "groups"):
        for entry in spec[kind]:
            assert entry.get("kanban_target_status") not in terminal, entry["slug"]


def test_no_declaration_ships_a_credential(spec):
    """A manifest goes to a marketplace; a gateway token must not ride along.

    The aw-gateway entry carries a bearer token, so the config declares the
    server BY NAME via mcp_servers and the workspace resolves it at seed
    time, inside the machine that owns the secret.
    """
    for cfg in spec["agent_configs"]:
        assert "mcp_config" not in cfg
        assert cfg["mcp_servers"] == ["aw-gateway"]
    # Scan the string VALUES that actually get POSTed — not the manifest text
    # and not the field names. A leaked credential is always a value, while
    # legitimate field names contain the same words
    # (`auto_compact_threshold_tokens`) and descriptions here discuss tokens
    # and budgets on purpose.
    for kind in ("models", "agent_configs", "groups", "agents", "agent_flows"):
        for entry in spec.get(kind, []):
            payload = {k: v for k, v in entry.items() if k != "description"}
            for value in _strings(payload):
                low = value.lower()
                for marker in ("bearer ", "authorization", "ntn_", "sk-"):
                    assert marker not in low, (
                        f"{kind} {entry.get('slug')!r}: {marker} in {value!r}")


def test_the_shipped_skills_do_not_carry_monolith_paths(manifest):
    """These contracts are written for this workspace, not the monolith it
    conceptually descends from — a skill naming awserv or
    /opt/agentic-workspace teaches an agent to call something that isn't
    here."""
    for skill in manifest["contributes"]["skills"]:
        text = (APP_DIR / skill["path"]).read_text()
        assert "/opt/agentic-workspace" not in text, skill["id"]
        assert "awserv" not in text, skill["id"]
        assert "ntn_" not in text, skill["id"]


def test_the_provider_floor_is_new_enough_for_what_the_skills_assume(manifest):
    """Below 0.55.0 the provider seeds the agents and silently drops the
    agent_flows entry. This floor is higher than that on purpose: 0.225.0 is
    the first release carrying plan memory, finish_plan_iteration and
    plan_slug on create_target/update_target — the three tools every one of
    these five contracts tells its agent to call.
    """
    dep = next(d for d in manifest["dependencies"]["apps"]
               if d["id"] == "agents-platform-runners")
    assert dep["version"] == ">=0.225.0"
    assert dep["required"] is False
