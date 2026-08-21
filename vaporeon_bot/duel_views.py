"""Discord button views for optional turn-based Vaporeon duels."""

from __future__ import annotations

from collections.abc import Callable

import discord

from .database import consume_inventory_item, inventory_for_user, record_duel_result
from .duels import DuelState, DuelTurn


ACTION_LABELS = {
    "bubble_beam": "Bubble Beam",
    "aqua_jet": "Aqua Jet",
    "surf": "Surf",
    "hydro_pump": "Hydro Pump",
    "brace": "Brace",
    "rain_dance": "Rain Dance",
    "tide_burst": "Tide Burst (75)",
    "potion": "Potion (+20)",
}


def duel_embed(state: DuelState, turn_text: str = "") -> discord.Embed:
    description = f"{turn_text}\n\n" if turn_text else ""
    description += state.card_text()
    return discord.Embed(title="💧 Vaporeon Duel", description=description, color=discord.Color.blue())


class DuelChallengeView(discord.ui.View):
    def __init__(self, challenger_id: int, opponent_id: int, on_accept: Callable[[], DuelState], release: Callable[[], None], touch: Callable[[], None]) -> None:
        super().__init__(timeout=120)
        self.challenger_id, self.opponent_id = challenger_id, opponent_id
        self.on_accept, self.release, self.touch = on_accept, release, touch

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.opponent_id:
            return True
        await interaction.response.send_message("This duel invitation is for someone else.", ephemeral=True)
        return False

    @discord.ui.button(label="Accept Duel", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        state = self.on_accept()
        self.touch()
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(embed=duel_embed(state, "⚔️ Duel accepted! **Choose your action.**"), view=DuelView(state, self.release, self.touch))

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.secondary)
    async def decline(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        self.release()
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content="💧 Vaporeon understands. The duel invitation dissolves into a peaceful puddle.", embed=None, view=self)


class DuelView(discord.ui.View):
    def __init__(self, state: DuelState, release: Callable[[], None], touch: Callable[[], None]) -> None:
        super().__init__(timeout=300)
        self.state, self.release, self.touch = state, release, touch
        current = state.current_player()
        potion_available = inventory_for_user(current.user_id).get("Potion", 0) > 0
        for index, action in enumerate(state.available_actions(current.user_id, potion_available=potion_available)):
            style = discord.ButtonStyle.success if action == "tide_burst" else discord.ButtonStyle.primary
            self.add_item(DuelActionButton(action, ACTION_LABELS[action], index // 5, style))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id not in {self.state.challenger.user_id, self.state.opponent.user_id}:
            await interaction.response.send_message("Only the two duelists can use these buttons.", ephemeral=True)
            return False
        if interaction.user.id != self.state.current_player_id:
            await interaction.response.send_message("It is not your turn yet.", ephemeral=True)
            return False
        return True

    async def choose(self, interaction: discord.Interaction, action: str) -> None:
        potion_available = inventory_for_user(interaction.user.id).get("Potion", 0) > 0
        try:
            turn = self.state.resolve(interaction.user.id, action, potion_available=potion_available)
        except ValueError as error:
            await interaction.response.send_message(str(error), ephemeral=True)
            return
        if action == "potion":
            consume_inventory_item(interaction.user.id, "Potion")
        self.touch()
        if turn.winner_id is not None:
            winner, loser = self.state.player(turn.winner_id), self.state.other(turn.winner_id)
            record_duel_result(winner.user_id, loser.user_id, winner_name=winner.name, loser_name=loser.name)
            self.release()
            await interaction.response.edit_message(embed=duel_embed(self.state, turn.text), view=None)
            return
        await interaction.response.edit_message(embed=duel_embed(self.state, turn.text), view=DuelView(self.state, self.release, self.touch))


class DuelActionButton(discord.ui.Button):
    def __init__(self, action: str, label: str, row: int, style: discord.ButtonStyle) -> None:
        super().__init__(label=label, style=style, row=row)
        self.action = action

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if isinstance(view, DuelView):
            await view.choose(interaction, self.action)
