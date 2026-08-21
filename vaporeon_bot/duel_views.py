"""Discord UI for Ripple Duel; mechanics live in :mod:`vaporeon_bot.duels`."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable

import discord

from .database import record_ripple_duel_result
from .duels import DuelState, Move


def duel_embed(state: DuelState, turn_text: str = "") -> discord.Embed:
    description = f"{turn_text}\n\n" if turn_text else ""
    description += state.card_text()
    return discord.Embed(title="💦 Ripple Duel", description=description, color=discord.Color.blue())


def rules_embed() -> discord.Embed:
    return discord.Embed(
        title="💦 Ripple Duel Rules",
        description=("**Aqua Jet** > **Hydro Charge**\n**Hydro Charge** > **Water Veil**\n**Water Veil** > **Aqua Jet**\n\n"
                     "First to **3** round wins wins the match.\n"
                     "You cannot see your opponent's move before choosing yours.\n"
                     "You may use **Ripple Read** once per duel. It privately narrows a locked opponent move to exactly two possible moves."),
        color=discord.Color.blue(),
    )


class DuelChallengeView(discord.ui.View):
    def __init__(self, challenger_id: int, opponent_id: int, on_accept: Callable[[], DuelState], release: Callable[[], None]) -> None:
        super().__init__(timeout=60)
        self.challenger_id, self.opponent_id = challenger_id, opponent_id
        self.on_accept, self.release = on_accept, release
        self.message: discord.Message | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.opponent_id:
            return True
        await interaction.response.send_message("This Ripple Duel invitation is for someone else.", ephemeral=True)
        return False

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        try:
            state = self.on_accept()
        except ValueError as error:
            await interaction.response.send_message(str(error), ephemeral=True)
            return
        self.stop()
        view = DuelView(state, self.release, interaction.message)
        await interaction.response.edit_message(embed=duel_embed(state, "⚔️ **Ripple Duel accepted!** Both players choose secretly."), view=view)

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.secondary)
    async def decline(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        self.release()
        self.stop()
        await interaction.response.edit_message(content="💧 Vaporeon understands. The Ripple Duel invitation dissolves into a peaceful puddle.", embed=None, view=None)

    async def on_timeout(self) -> None:
        self.release()
        if self.message:
            await self.message.edit(content="💧 The Ripple Duel invitation expired before the water could settle.", view=None)


class DuelView(discord.ui.View):
    def __init__(self, state: DuelState, release: Callable[[], None], message: discord.Message | None = None) -> None:
        super().__init__(timeout=120)
        self.state, self.release, self.message = state, release, message
        for move in Move:
            self.add_item(DuelMoveButton(move))
        self.add_item(RippleReadButton())
        self.add_item(RulesButton())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id not in {self.state.challenger.user_id, self.state.opponent.user_id}:
            await interaction.response.send_message(f"This Ripple Duel belongs to {self.state.challenger.name} and {self.state.opponent.name}. Start your own with /vaporeon-duel.", ephemeral=True)
            return False
        return True

    async def choose(self, interaction: discord.Interaction, move: Move) -> None:
        async with self.state.lock:
            try:
                update = self.state.lock_move(interaction.user.id, move)
            except ValueError as error:
                await interaction.response.send_message(str(error), ephemeral=True)
                return
            await interaction.response.send_message(f"You locked in **{move.value}**. " + ("Waiting for the other duelist…" if not update.round_resolved else "Both moves are now revealed."), ephemeral=True)
            if update.finished:
                winner = self.state.player(update.winner_id or 0)
                loser = self.state.other(winner.user_id)
                record_ripple_duel_result(
                    winner.user_id, loser.user_id, winner_name=winner.name, loser_name=loser.name,
                    winner_rounds=winner.wins, loser_rounds=loser.wins,
                    ties=sum(1 for a, b in zip(winner.history, loser.history) if a == b),
                    winner_moves=dict(Counter(move.value for move in winner.history)), loser_moves=dict(Counter(move.value for move in loser.history)),
                    winner_ripple_used=winner.ripple_used, loser_ripple_used=loser.ripple_used,
                )
                self.release()
                final = (f"🏆 **Ripple Duel Complete!**\n\n**{winner.name} defeats {loser.name}**\n"
                         f"**{winner.wins} — {loser.wins}**\n\n{update.text}\n\n💧 Vaporeon declares **{winner.name}** extremely splashworthy.")
                await interaction.message.edit(embed=duel_embed(self.state, final), view=None)
                self.stop()
                return
            await interaction.message.edit(embed=duel_embed(self.state, update.text), view=DuelView(self.state, self.release, interaction.message))
            self.stop()

    async def ripple_read(self, interaction: discord.Interaction) -> None:
        async with self.state.lock:
            try:
                clue = self.state.use_ripple_read(interaction.user.id)
            except ValueError as error:
                await interaction.response.send_message(str(error), ephemeral=True)
                return
            await interaction.response.send_message(
                "💧 **Vaporeon studies the ripples…**\n\n"
                f'“{clue.flavor}”\n\n**Possible moves:**\n• **{clue.possible_moves[0].value}**\n• **{clue.possible_moves[1].value}**\n\nThis clue is private; the opponent only knows you used Ripple Read.',
                ephemeral=True,
            )
            await interaction.message.edit(embed=duel_embed(self.state, f"💧 **{self.state.player(interaction.user.id).name}** has used Ripple Read."), view=DuelView(self.state, self.release, interaction.message))
            self.stop()

    async def on_timeout(self) -> None:
        self.release()
        if self.message and not self.state.finished:
            await self.message.edit(content="💧 The ripples have gone still. The Ripple Duel ended because a move was not selected in time.", embed=None, view=None)


class DuelMoveButton(discord.ui.Button):
    def __init__(self, move: Move) -> None:
        super().__init__(label=move.value, style=discord.ButtonStyle.primary)
        self.move = move

    async def callback(self, interaction: discord.Interaction) -> None:
        if isinstance(self.view, DuelView):
            await self.view.choose(interaction, self.move)


class RippleReadButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(label="💧 Ripple Read", style=discord.ButtonStyle.secondary, row=1)

    async def callback(self, interaction: discord.Interaction) -> None:
        if isinstance(self.view, DuelView):
            await self.view.ripple_read(interaction)


class RulesButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(label="Rules", style=discord.ButtonStyle.secondary, row=1)

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(embed=rules_embed(), ephemeral=True)
