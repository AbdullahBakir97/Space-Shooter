"""One flown loop of the war: the tug and what it carries across fights, closed exactly once."""

from __future__ import annotations

import random

from space_shooter import campaign
from space_shooter.echoes import EchoRecorder, EchoTrace, select_roster, store_trace
from space_shooter.entities.player import Player
from space_shooter.salvage import PART_TYPES, SLOT_OFFSETS, Part
from space_shooter.save import Record, add_record
from space_shooter.scenes.loop_end import RunResult


class CampaignRun:
    def __init__(self, game, seed: int | None = None) -> None:
        self.game = game
        self.rng = random.Random(seed)
        self.state = game.campaign()
        self.loop = game.save.loop
        self.player = Player()
        for kind in self.state.requisition:  # requisitioned parts are spent the moment the tug undocks
            free = [s for s in PART_TYPES[kind].slots if self.player.loadout.slots[s] is None]
            if free:
                self.player.loadout.attach(Part(kind), SLOT_OFFSETS[free[0]])
        self.state.requisition = []
        game.store_campaign(self.state)
        self.recorder = EchoRecorder(self.loop)
        self.traces: list[EchoTrace] = select_roster([EchoTrace.from_data(d) for d in game.save.echoes])
        self.lost_echoes: list[int] = []
        self.carried = 0
        self.time = 0.0
        self.reached = -1  # highest encounter index won this loop
        self.last_fought: str | None = None
        self.repaired: set[str] = set()
        self.result: RunResult | None = None

    def roster(self) -> list[EchoTrace]:
        return [t for t in self.traces if t.loop not in self.lost_echoes]

    def win_fight(self, node_id: str | None, encounter_index: int, salvage: int) -> None:
        self.carried += salvage
        if node_id is not None:  # an ambush claims nothing and reaches nowhere
            self.reached = max(self.reached, encounter_index)
            campaign.claim(self.state, node_id)
            self.game.store_campaign(self.state)

    def finish(self, died: bool, warden_killed: bool = False) -> RunResult:
        """End the loop: keep the echo, record it, bank salvage, let the swarm move, save."""
        if self.result is not None:
            return self.result
        game, save, system, state = self.game, self.game.save, self.game.system, self.state
        reached = max(0, self.reached)
        trace = self.recorder.finish(reached=reached, duration=self.time)
        if trace.samples:  # a loop that never fought leaves no echo
            traces = store_trace([EchoTrace.from_data(d) for d in save.echoes], trace)
            save.echoes = [t.to_data() for t in traces]
        add_record(save, Record(self.loop, reached, self.carried, round(self.time, 1), game.settings.difficulty))
        save.loop += 1
        report = campaign.end_turn(system, state, self.carried, died, warden_killed, self.rng)
        flags = save.flags
        if report.claimed:
            flags.add("node_claimed")
        if report.lost:
            flags.add("node_lost")
        if report.hives:
            flags.add("hive_formed")
        if report.home_threatened:
            flags.add("home_threatened")
        if not campaign.locked(system, state, campaign.GATE):
            flags.add("gate_open")
        if state.status == "lost":
            flags.add("war_lost")
        save.campaign = state.to_dict()
        game.persist()
        where = system.nodes[self.last_fought].name if self.last_fought else system.nodes[campaign.HOME].name
        self.result = RunResult(
            self.loop,
            reached,
            self.carried,
            self.time,
            list(self.lost_echoes),
            victory=warden_killed,
            report=report,
            docked=not died and not warden_killed,
            reached_name=where,
        )
        return self.result
