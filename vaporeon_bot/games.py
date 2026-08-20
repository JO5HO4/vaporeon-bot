"""Small button-based Vaporeon encounters."""

from __future__ import annotations

import random
from typing import TypedDict

import discord

from .constants import WATER_BLUE
from .database import record_play


class Choice(TypedDict):
    label: str
    outcome: str
    affection: int


class Scenario(TypedDict):
    prompt: str
    choices: list[Choice]


SCENARIOS: tuple[Scenario, ...] = (
    {"prompt": "Vaporeon spots a sparkle beneath a shallow puddle.", "choices": [
        {"label": "Inspect it", "outcome": "It was a smooth little pebble. Vaporeon gives it a proud fin tap.", "affection": 2},
        {"label": "Dive in", "outcome": "A tiny splash! Vaporeon follows you into a very successful puddle adventure.", "affection": 3},
        {"label": "Offer a berry", "outcome": "Vaporeon accepts the berry, then lets you inspect the sparkle together.", "affection": 2},
    ]},
    {"prompt": "A blanket corner has fallen to the floor. Vaporeon looks concerned.", "choices": [
        {"label": "Fix the nest", "outcome": "The blanket nest is restored to peak coziness. Vaporeon is deeply grateful.", "affection": 3},
        {"label": "Make it bigger", "outcome": "The nest becomes a blanket fortress. Vaporeon has appointed you architect.", "affection": 3},
        {"label": "Take a nap", "outcome": "Vaporeon decides the unfinished nest is still nap-ready. An excellent compromise.", "affection": 2},
    ]},
    {"prompt": "Vaporeon hears a mysterious crinkle from the other room.", "choices": [
        {"label": "Investigate", "outcome": "It was a snack wrapper. Vaporeon considers this a major discovery.", "affection": 3},
        {"label": "Stay cozy", "outcome": "Vaporeon agrees that comfort comes first and resumes the cuddle mission.", "affection": 2},
        {"label": "Send a splash", "outcome": "A tiny splash investigates on your behalf. The crinkle is intimidated.", "affection": 2},
    ]},
    {"prompt": "Rain begins tapping softly against the window.", "choices": [
        {"label": "Watch together", "outcome": "Vaporeon sits beside you and counts raindrops with great concentration.", "affection": 3},
        {"label": "Dance in it", "outcome": "Vaporeon performs a very small rain dance. The timing is perfect.", "affection": 3},
        {"label": "Make cocoa", "outcome": "Vaporeon approves of the cozy plan and guards the warmest spot.", "affection": 2},
    ]},
    {"prompt": "Vaporeon has found an unusually round pebble and needs advice.", "choices": [
        {"label": "Name it", "outcome": "The pebble is named immediately. Vaporeon treats it like an honored guest.", "affection": 3},
        {"label": "Skip it", "outcome": "The pebble skips once. Vaporeon is stunned by your talent.", "affection": 3},
        {"label": "Keep it safe", "outcome": "Vaporeon places the pebble in the official treasure pile.", "affection": 2},
    ]},
    {"prompt": "A sunbeam has appeared on the floor. Vaporeon is deciding what to do.", "choices": [
        {"label": "Claim it", "outcome": "Vaporeon curls up in the sunbeam and looks approximately perfect.", "affection": 3},
        {"label": "Share it", "outcome": "You and Vaporeon sit in the warm patch together. No further plans are required.", "affection": 3},
        {"label": "Guard it", "outcome": "Vaporeon posts you as official sunbeam guardian. It is an important role.", "affection": 2},
    ]},
)


class PlayView(discord.ui.View):
    def __init__(self, owner_id: int, display_name: str, scenario: Scenario) -> None:
        super().__init__(timeout=60)
        self.owner_id, self.display_name, self.scenario = owner_id, display_name, scenario
        for index, choice in enumerate(scenario["choices"]):
            self.add_item(PlayButton(index, choice["label"]))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message("This Vaporeon play encounter belongs to someone else. Run `/vaporeon-play` for your own.", ephemeral=True)
        return False

    async def choose(self, interaction: discord.Interaction, index: int) -> None:
        choice = self.scenario["choices"][index]
        stats = record_play(self.owner_id, choice["affection"], display_name=self.display_name)
        for item in self.children:
            item.disabled = True
        embed = discord.Embed(title="💧 Vaporeon Play", description=f"{choice['outcome']}\n\nAffection **+{choice['affection']}** · Total: **{stats.affection:,}**", color=discord.Color(WATER_BLUE))
        await interaction.response.edit_message(embed=embed, view=self)


class PlayButton(discord.ui.Button):
    def __init__(self, index: int, label: str) -> None:
        super().__init__(label=label, style=discord.ButtonStyle.primary, row=0)
        self.index = index

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if isinstance(view, PlayView):
            await view.choose(interaction, self.index)


def random_scenario() -> Scenario:
    return random.choice(SCENARIOS)
