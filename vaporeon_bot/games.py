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
    {"prompt": "Vaporeon is carrying a berry with enormous concentration.", "choices": [
        {"label": "Offer a bowl", "outcome": "The berry receives a proper ceremonial landing. Vaporeon is impressed.", "affection": 5},
        {"label": "Ask about it", "outcome": "Vaporeon explains nothing, but lets you admire the berry from a respectful distance.", "affection": 2},
        {"label": "Try to juggle it", "outcome": "The berry rolls away. Vaporeon watches the attempt with worried little ears.", "affection": -5},
    ]},
    {"prompt": "A tiny puddle has formed near the door and Vaporeon has found it immediately.", "choices": [
        {"label": "Make it a tiny lake", "outcome": "With one careful splash, the puddle is promoted. Vaporeon has never been prouder.", "affection": 5},
        {"label": "Sit beside it", "outcome": "You both observe the puddle. It is a surprisingly good use of time.", "affection": 2},
        {"label": "Mop it up", "outcome": "The puddle is gone. Vaporeon files a quiet complaint with the Department of Water.", "affection": -5},
    ]},
    {"prompt": "Vaporeon brings you a wet leaf as though it is a priceless gift.", "choices": [
        {"label": "Thank Vaporeon", "outcome": "Vaporeon beams. The leaf is placed somewhere important immediately.", "affection": 5},
        {"label": "Inspect the leaf", "outcome": "After a careful review, you agree it is a very respectable leaf.", "affection": 2},
        {"label": "Throw it away", "outcome": "Vaporeon retrieves the leaf and looks personally betrayed by the bin.", "affection": -5},
    ]},
    {"prompt": "A glass of water is sitting unattended. Vaporeon looks at you, then at the glass.", "choices": [
        {"label": "Add ice", "outcome": "Excellent decision. Vaporeon considers the beverage situation greatly improved.", "affection": 5},
        {"label": "Guard the glass", "outcome": "You become the official water guardian. Vaporeon approves of the responsibility.", "affection": 2},
        {"label": "Move it away", "outcome": "Vaporeon loses sight of the water and becomes dramatically concerned.", "affection": -5},
    ]},
    {"prompt": "Vaporeon has tucked itself into a blanket burrito and refuses to elaborate.", "choices": [
        {"label": "Protect the nap", "outcome": "The blanket burrito achieves perfect defensive positioning. Vaporeon sleeps soundly.", "affection": 5},
        {"label": "Bring a pillow", "outcome": "Vaporeon makes room for the pillow with a grateful little wiggle.", "affection": 2},
        {"label": "Unwrap the burrito", "outcome": "The burrito is disturbed. Vaporeon has noted this extremely serious event.", "affection": -5},
    ]},
    {"prompt": "You hear a single splash from somewhere Vaporeon definitely should not be.", "choices": [
        {"label": "Join the mission", "outcome": "It turns out there was a perfectly good splash zone. Vaporeon welcomes your support.", "affection": 5},
        {"label": "Ask what happened", "outcome": "Vaporeon offers an innocent expression and one suspiciously wet paw.", "affection": 2},
        {"label": "Ban splashing", "outcome": "Vaporeon considers this proposal incompatible with its core values.", "affection": -5},
    ]},
    {"prompt": "A cardboard box is empty. Vaporeon suspects it may be an important new home.", "choices": [
        {"label": "Add a blanket", "outcome": "The box becomes a deluxe Vaporeon suite in under ten seconds.", "affection": 5},
        {"label": "Label it cozy", "outcome": "Vaporeon accepts the official designation and begins a slow inspection.", "affection": 2},
        {"label": "Recycle it now", "outcome": "Vaporeon watches the box leave with quiet, theatrical sadness.", "affection": -5},
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
        embed = discord.Embed(title="💧 Vaporeon Play", description=f"{choice['outcome']}\n\nAffection **{choice['affection']:+d}** · Total: **{stats.affection:,}**", color=discord.Color(WATER_BLUE))
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
    selected = random.choice(SCENARIOS)
    choices = list(selected["choices"])
    random.shuffle(choices)
    return {"prompt": selected["prompt"], "choices": choices}
