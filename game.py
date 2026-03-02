"""
Корова 006 (6 Nimmt!) — Game engine.

Pure game logic with no I/O.  The Flask app drives this module.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field


# ── Card points (exponentially distributed 1-6) ─────────────────────────────


def _generate_points() -> dict[int, int]:
    return {
        i: max(1, min(7, math.ceil(random.expovariate(1 / 2)))) for i in range(1, 105)
    }


# ── Constants ────────────────────────────────────────────────────────────────

MAX_ROWS = 4
MAX_COLS = 6
MAX_PLAYERS = 10
CARDS_PER_PLAYER = 10
TOTAL_CARDS = 104


# ── Data classes ─────────────────────────────────────────────────────────────


@dataclass
class Player:
    name: str
    hand: list[int] = field(default_factory=list)
    score: int = 0


@dataclass
class RoundEvent:
    """One resolution step shown in the game log."""

    player_idx: int
    card: int
    row_idx: int | None = None  # row the card was placed in
    took_row: bool = False  # player had to take a row
    filled_row: bool = False  # 6th-card trigger
    points_taken: int = 0
    needs_row_choice: bool = False  # waiting for human to pick a row


@dataclass
class GameState:
    players: list[Player]
    board: list[list[int]]
    points_table: dict[int, int]
    round_num: int = 0
    phase: str = "pick"  # pick | resolve | choose_row | game_over
    chosen_cards: list[tuple[int, int]] = field(
        default_factory=list
    )  # (card, player_idx)
    pending_resolve: list[tuple[int, int]] = field(default_factory=list)
    events: list[RoundEvent] = field(default_factory=list)
    waiting_player: int | None = None  # player who must pick a row
    waiting_card: int | None = None  # the card that triggered it
    round_events: list[RoundEvent] = field(default_factory=list)
    game_log: list[str] = field(default_factory=list)


# ── Engine functions ─────────────────────────────────────────────────────────


def new_game(num_players: int, player_names: list[str] | None = None) -> GameState:
    """Initialise a fresh game."""
    if not 2 <= num_players <= MAX_PLAYERS:
        raise ValueError(f"Players must be between 2 and {MAX_PLAYERS}.")

    pts = _generate_points()
    deck = list(range(1, TOTAL_CARDS + 1))
    random.shuffle(deck)

    if player_names is None:
        player_names = [f"Player {i + 1}" for i in range(num_players)]

    players: list[Player] = []
    for i in range(num_players):
        hand = sorted(deck[:CARDS_PER_PLAYER])
        deck = deck[CARDS_PER_PLAYER:]
        players.append(Player(name=player_names[i], hand=hand))

    starter = sorted(deck[:MAX_ROWS])
    deck = deck[MAX_ROWS:]
    board = [[c] for c in starter]

    gs = GameState(players=players, board=board, points_table=pts, round_num=1)
    gs.game_log.append("Game started!")
    return gs


def submit_card(gs: GameState, player_idx: int, card: int) -> bool:
    """A player picks a card for this round.  Returns True on success."""
    if gs.phase != "pick":
        return False
    if card not in gs.players[player_idx].hand:
        return False
    # Already submitted?
    if any(p == player_idx for _, p in gs.chosen_cards):
        return False

    gs.chosen_cards.append((card, player_idx))
    gs.players[player_idx].hand.remove(card)

    # All players submitted → move to resolve
    if len(gs.chosen_cards) == len(gs.players):
        gs.chosen_cards.sort(key=lambda x: x[0])
        gs.pending_resolve = list(gs.chosen_cards)
        gs.round_events = []
        _resolve_next(gs)

    return True


def choose_row(gs: GameState, row_idx: int) -> bool:
    """Player picks which row to take (when card < all last cards)."""
    if gs.phase != "choose_row":
        return False
    if not 0 <= row_idx < MAX_ROWS:
        return False

    player_idx = gs.waiting_player
    card = gs.waiting_card
    pts = sum(gs.points_table[c] for c in gs.board[row_idx])
    gs.players[player_idx].score += pts

    ev = RoundEvent(
        player_idx=player_idx,
        card=card,
        row_idx=row_idx,
        took_row=True,
        points_taken=pts,
    )
    gs.round_events.append(ev)
    gs.game_log.append(
        f"{gs.players[player_idx].name} takes Row {row_idx + 1} "
        f"(+{pts} pts) and starts it with card {card}."
    )
    gs.board[row_idx] = [card]
    gs.waiting_player = None
    gs.waiting_card = None

    # Continue resolving remaining cards
    _resolve_next(gs)
    return True


# ── Internal helpers ─────────────────────────────────────────────────────────


def _find_target_row(board: list[list[int]], card: int) -> int | None:
    best_row: int | None = None
    best_diff = float("inf")
    for i, row in enumerate(board):
        last = row[-1]
        diff = card - last
        if 0 < diff < best_diff:
            best_diff = diff
            best_row = i
    return best_row


def _resolve_next(gs: GameState) -> None:
    """Resolve the next pending card, or finish the round."""
    while gs.pending_resolve:
        card, player_idx = gs.pending_resolve.pop(0)
        target = _find_target_row(gs.board, card)

        if target is None:
            # Need the player to choose a row
            gs.phase = "choose_row"
            gs.waiting_player = player_idx
            gs.waiting_card = card
            gs.game_log.append(
                f"{gs.players[player_idx].name} plays {card} — "
                f"must pick a row to take!"
            )
            return  # pause until choose_row() is called

        gs.board[target].append(card)

        if len(gs.board[target]) == MAX_COLS:
            taken = gs.board[target][:-1]
            pts = sum(gs.points_table[c] for c in taken)
            gs.players[player_idx].score += pts
            gs.board[target] = [card]
            ev = RoundEvent(
                player_idx=player_idx,
                card=card,
                row_idx=target,
                filled_row=True,
                points_taken=pts,
            )
            gs.round_events.append(ev)
            gs.game_log.append(
                f"{gs.players[player_idx].name} fills Row {target + 1} "
                f"(+{pts} pts). Row restarted with {card}."
            )
        else:
            ev = RoundEvent(player_idx=player_idx, card=card, row_idx=target)
            gs.round_events.append(ev)
            gs.game_log.append(
                f"{gs.players[player_idx].name} places {card} → Row {target + 1}."
            )

    # All cards resolved → next round or game over
    gs.events.extend(gs.round_events)
    gs.chosen_cards = []
    gs.round_num += 1

    if gs.round_num > CARDS_PER_PLAYER:
        gs.phase = "game_over"
        gs.game_log.append("Game over!")
    else:
        gs.phase = "pick"


def get_rankings(gs: GameState) -> list[tuple[int, str, int]]:
    """Return players sorted by score ascending (winner first)."""
    ranked = [(i, p.name, p.score) for i, p in enumerate(gs.players)]
    ranked.sort(key=lambda x: x[2])
    return ranked
