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
        {"label": "Dive in", "outcome": "A tiny splash! Vaporeon follows you into a very successful puddle adventure.", "affection": 5},
        {"label": "Skip it away", "outcome": "The pebble disappears into the puddle. Vaporeon looks at the empty water with quiet disappointment.", "affection": -5},
    ]},
    {"prompt": "A blanket corner has fallen to the floor. Vaporeon looks concerned.", "choices": [
        {"label": "Fix the nest", "outcome": "The blanket nest is restored to peak coziness. Vaporeon is deeply grateful.", "affection": 5},
        {"label": "Take a nap", "outcome": "Vaporeon decides the unfinished nest is still nap-ready. An excellent compromise.", "affection": 2},
        {"label": "Take the blanket", "outcome": "The nest is gone. Vaporeon has issued a tiny but unmistakable disappointed chirp.", "affection": -5},
    ]},
    {"prompt": "Vaporeon hears a mysterious crinkle from the other room.", "choices": [
        {"label": "Investigate", "outcome": "It was a snack wrapper. Vaporeon considers this a major discovery.", "affection": 5},
        {"label": "Stay cozy", "outcome": "Vaporeon agrees that comfort comes first and resumes the cuddle mission.", "affection": 2},
        {"label": "Blame Vaporeon", "outcome": "Vaporeon was not responsible for the crinkle and would like that formally noted.", "affection": -5},
    ]},
    {"prompt": "Rain begins tapping softly against the window.", "choices": [
        {"label": "Dance in it", "outcome": "Vaporeon performs a very small rain dance. The timing is perfect.", "affection": 5},
        {"label": "Watch together", "outcome": "Vaporeon sits beside you and counts raindrops with great concentration.", "affection": 2},
        {"label": "Close the curtains", "outcome": "Vaporeon watches the rain disappear behind the curtains. The mood becomes noticeably less splashy.", "affection": -5},
    ]},
    {"prompt": "Vaporeon has found an unusually round pebble and needs advice.", "choices": [
        {"label": "Name it", "outcome": "The pebble is named immediately. Vaporeon treats it like an honored guest.", "affection": 5},
        {"label": "Keep it safe", "outcome": "Vaporeon places the pebble in the official treasure pile.", "affection": 2},
        {"label": "Call it boring", "outcome": "Vaporeon places the pebble behind you with a tiny offended splash.", "affection": -5},
    ]},
    {"prompt": "A sunbeam has appeared on the floor. Vaporeon is deciding what to do.", "choices": [
        {"label": "Share it", "outcome": "You and Vaporeon sit in the warm patch together. No further plans are required.", "affection": 5},
        {"label": "Guard it", "outcome": "Vaporeon posts you as official sunbeam guardian. It is an important role.", "affection": 2},
        {"label": "Block it", "outcome": "The sunbeam is gone. Vaporeon looks at you as if this was a surprising tactical error.", "affection": -5},
    ]},
)


class PlayView(discord.ui.View):
    def __init__(self, owner_id: int, display_name: str, scenario: Scenario) -> None:
        super().__init__(timeout=60)
        self.owner_id, self.display_name, self.scenario = owner_id, display_name, scenario
        for index, choice in enumerate(scenario["choices"]):
            self.add_item(PlayButton(index, choice["label"], choice["affection"]))

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
        embed = discord.Embed(title="💧 Vaporeon Play", description=f"{choice['outcome']}\n\nAffection **{choice['affection']:+d}** · Total: **{stats.affection:,}**", color=discord.Color(WATER_BLUE))
        await interaction.response.edit_message(embed=embed, view=self)


class PlayButton(discord.ui.Button):
    def __init__(self, index: int, label: str, affection: int) -> None:
        style = discord.ButtonStyle.success if affection > 2 else discord.ButtonStyle.danger if affection < 0 else discord.ButtonStyle.primary
        super().__init__(label=label, style=style, row=0)
        self.index = index

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if isinstance(view, PlayView):
            await view.choose(interaction, self.index)


def random_scenario() -> Scenario:
    return random.choice(SCENARIOS)
