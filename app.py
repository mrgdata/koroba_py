"""
Корова 006 (6 Nimmt!) — Flask web application.

Run:  python app.py
Then open http://localhost:5000 in a browser.
"""

from __future__ import annotations

import json
from flask import Flask, render_template, request, redirect, url_for, session

import game as g

app = Flask(__name__)
app.secret_key = "korova-006-secret-key-change-me"

# ── Serialisation helpers ────────────────────────────────────────────────────
# Flask sessions use JSON, so we convert GameState ↔ dict.


def _gs_to_dict(gs: g.GameState) -> dict:
    return {
        "players": [
            {"name": p.name, "hand": p.hand, "score": p.score} for p in gs.players
        ],
        "board": gs.board,
        "points_table": {str(k): v for k, v in gs.points_table.items()},
        "round_num": gs.round_num,
        "phase": gs.phase,
        "chosen_cards": gs.chosen_cards,
        "pending_resolve": gs.pending_resolve,
        "waiting_player": gs.waiting_player,
        "waiting_card": gs.waiting_card,
        "game_log": gs.game_log[-50:],  # keep last 50 entries
    }


def _dict_to_gs(d: dict) -> g.GameState:
    players = [
        g.Player(name=p["name"], hand=p["hand"], score=p["score"]) for p in d["players"]
    ]
    pts = {int(k): v for k, v in d["points_table"].items()}
    gs = g.GameState(
        players=players,
        board=d["board"],
        points_table=pts,
        round_num=d["round_num"],
        phase=d["phase"],
        chosen_cards=[tuple(c) for c in d["chosen_cards"]],
        pending_resolve=[tuple(c) for c in d["pending_resolve"]],
        waiting_player=d["waiting_player"],
        waiting_card=d["waiting_card"],
        game_log=d["game_log"],
    )
    return gs


def _save(gs: g.GameState) -> None:
    session["gs"] = json.dumps(_gs_to_dict(gs))


def _load() -> g.GameState | None:
    raw = session.get("gs")
    if raw is None:
        return None
    return _dict_to_gs(json.loads(raw))


# ── Routes ───────────────────────────────────────────────────────────────────


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", page="setup")


@app.route("/new", methods=["POST"])
def new_game():
    num = int(request.form.get("num_players", 2))
    names = []
    for i in range(num):
        name = request.form.get(f"player_{i}", "").strip()
        names.append(name if name else f"Player {i + 1}")
    gs = g.new_game(num, names)
    _save(gs)
    return redirect(url_for("play"))


@app.route("/play", methods=["GET"])
def play():
    gs = _load()
    if gs is None:
        return redirect(url_for("index"))

    submitted = {p for _, p in gs.chosen_cards}
    rankings = g.get_rankings(gs) if gs.phase == "game_over" else None

    return render_template(
        "index.html",
        page="play",
        gs=gs,
        submitted=submitted,
        rankings=rankings,
        points=gs.points_table,
        max_cols=g.MAX_COLS,
    )


@app.route("/submit_card", methods=["POST"])
def submit_card():
    gs = _load()
    if gs is None:
        return redirect(url_for("index"))

    player_idx = int(request.form["player_idx"])
    card = int(request.form["card"])
    g.submit_card(gs, player_idx, card)
    _save(gs)
    return redirect(url_for("play"))


@app.route("/choose_row", methods=["POST"])
def choose_row():
    gs = _load()
    if gs is None:
        return redirect(url_for("index"))

    row_idx = int(request.form["row_idx"])
    g.choose_row(gs, row_idx)
    _save(gs)
    return redirect(url_for("play"))


@app.route("/restart", methods=["POST"])
def restart():
    session.clear()
    return redirect(url_for("index"))


# ── Run ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True, port=5000)
