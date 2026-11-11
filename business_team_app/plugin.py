"""
Entrypoint referenced by aw-app.json's runtime.entrypoint
("business_team_app.plugin:BusinessTeamAppPlugin").

Like aw-app-devteam, this app is deliberately almost empty. Everything it
delivers — the five business personas, the config bundle they run under, the
group instructions they share, the five skills that define their boundaries,
and the Agents Flow that says how they hand off — is *declared* in
``aw-app.json`` and seeded by the workspace's own contribution surfaces
(``contributes.agents``, ``contributes.skills``). There is no HTTP route, no
window and no CLI, so ``activate`` has nothing to register.

Why the app exists at all: this team is reached by the Agents Platform's
**plan ticker**, not by a human clicking anything. An active Plan whose
``follow_up_agent_slug`` is ``business-steward`` wakes that agent once per
cadence period, and the steward routes the iteration to whichever persona the
plan's current gap names. A missing agent in that chain fails the way
everything in this workspace fails — silently: the ticker dispatches into a
slug that does not exist, the iteration records a failure nobody reads, and
the plan simply stops moving. Declaring the whole team as one installable
unit is the point; the Python here is the hook the framework needs to hang
that manifest on.

Create-if-absent, then PER-FIELD reconcile (aw-workspace's
``src/apps/agents.py::AgentsRegistry._reconcile`` plus
``src/apps/seeded_state.py``'s ``updatable_fields``): a later version of this
app CAN correct a prompt or a skill reference on an already-seeded row, as
long as nobody hand-edited that same field in the UI. A field a human touched
is theirs from then on. So shipping a corrected boundary paragraph is an
ordinary version bump here — not a new slug, and emphatically not a reason to
version the slugs the plan-memory ``writer_key``s depend on.
"""

from __future__ import annotations

import logging

log = logging.getLogger("aw_apps.business_team")


class BusinessTeamAppPlugin:
    """Tier-1 in-process plugin with no runtime surface of its own."""

    def __init__(self, ctx=None):
        self.ctx = ctx

    async def activate(self, ctx=None) -> None:
        if ctx is not None:
            self.ctx = ctx
        # The contribution registries run from the framework's own activation
        # path, not from here — an app declares, the runtime dispatches. All
        # this needs to do is come up cleanly so that dispatch happens.
        log.info(
            "aw-app-business-team active — the five business personas, their "
            "skills and the business-planning flow are seeded by the "
            "workspace from aw-app.json's contributes block"
        )

    async def deactivate(self) -> None:
        log.info("aw-app-business-team deactivated")
