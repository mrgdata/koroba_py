"""
Корова 006 (6 Nimmt!) — Flask web application.

Run:  python app.py
Then open http://localhost:5000 in a browser.
"""

from __future__ import annotations

import json
import secrets
from flask import Flask, render_template, request, redirect, url_for, session

import game as g
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "korova-006-secret-key-change-me")
# ── Room storage (in-memory) ────────────────────────────────────────────────
rooms: dict[str, dict] = {}


def _get_player_id() -> str:
    """Get or create a unique player ID for this browser session."""
    if "player_id" not in session:
        session["player_id"] = secrets.token_hex(16)
    return session["player_id"]

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
        "ai_difficulty": gs.ai_difficulty,
        "ai_players": gs.ai_players,
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
        ai_difficulty=d.get("ai_difficulty"),
        ai_players=d.get("ai_players", []),
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
    return render_template("index.jinja-html", page="setup")


@app.route("/new", methods=["POST"])
def new_game():
    num = int(request.form.get("num_players", 2))
    ai_difficulty = request.form.get("ai_difficulty")  # None when > 1 player

    if num == 1:
        # Single-player vs AI
        human_name = request.form.get("player_0", "").strip()
        if not human_name:
            return render_template(
                "index.jinja-html",
                page="setup",
                error="All players must have a name!",
            )
        diff_label = (ai_difficulty or "medium").capitalize()
        bot_name = f"\U0001f916 Bot ({diff_label})"
        gs = g.new_game(2, [human_name, bot_name])
        gs.ai_difficulty = ai_difficulty or "medium"
        gs.ai_players = [1]
    else:
        names = []
        for i in range(num):
            name = request.form.get(f"player_{i}", "").strip()
            if not name:
                return render_template(
                    "index.jinja-html",
                    page="setup",
                    error="All players must have a name!",
                )
            names.append(name)
        gs = g.new_game(num, names)

    _save(gs)
    return redirect(url_for("play"))


@app.route("/play", methods=["GET"])
def play():
    gs = _load()
    if gs is None:
        return redirect(url_for("index"))

    # Auto-play any pending AI actions
    if gs.ai_players:
        g.auto_play_ai(gs)
        _save(gs)

    submitted = {p for _, p in gs.chosen_cards}
    rankings = g.get_rankings(gs) if gs.phase == "game_over" else None

    return render_template(
        "index.jinja-html",
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

    # Auto-play AI after human action
    if gs.ai_players:
        g.auto_play_ai(gs)

    _save(gs)
    return redirect(url_for("play"))


@app.route("/choose_row", methods=["POST"])
def choose_row():
    gs = _load()
    if gs is None:
        return redirect(url_for("index"))

    row_idx = int(request.form["row_idx"])
    g.choose_row(gs, row_idx)

    # Auto-play AI after human action
    if gs.ai_players:
        g.auto_play_ai(gs)

    _save(gs)
    return redirect(url_for("play"))


@app.route("/restart", methods=["POST"])
def restart():
    session.clear()
    return redirect(url_for("index"))


# ── Online multiplayer routes ────────────────────────────────────────────────


@app.route("/create_room", methods=["POST"])
def create_room():
    num_players = int(request.form.get("num_players", 2))
    num_players = max(2, min(10, num_players))

    host_name = request.form.get("host_name", "").strip()
    if not host_name:
        return render_template(
            "index.jinja-html", page="setup", error="Enter your name!"
        )

    player_id = _get_player_id()
    room_code = secrets.token_hex(3).upper()
    while room_code in rooms:
        room_code = secrets.token_hex(3).upper()

    rooms[room_code] = {
        "max_players": num_players,
        "host_id": player_id,
        "players": {player_id: {"name": host_name, "idx": 0}},
        "player_order": [player_id],
        "game_state": None,
        "phase": "lobby",
    }

    return redirect(url_for("lobby", room_code=room_code))


@app.route("/join_by_code", methods=["POST"])
def join_by_code():
    code = request.form.get("room_code", "").strip().upper()
    if code not in rooms:
        return render_template(
            "index.jinja-html", page="setup", error="Room not found!"
        )
    return redirect(url_for("join_page", room_code=code))


@app.route("/room/<room_code>")
def join_page(room_code):
    room_code = room_code.upper()
    if room_code not in rooms:
        return render_template(
            "index.jinja-html", page="setup", error="Room not found!"
        )

    room = rooms[room_code]
    player_id = _get_player_id()

    if player_id in room["players"]:
        if room["phase"] == "lobby":
            return redirect(url_for("lobby", room_code=room_code))
        return redirect(url_for("online_play", room_code=room_code))

    if len(room["players"]) >= room["max_players"]:
        return render_template(
            "index.jinja-html", page="setup", error="Room is full!"
        )

    return render_template(
        "index.jinja-html", page="join", room_code=room_code, room=room
    )


@app.route("/join_room/<room_code>", methods=["POST"])
def join_room(room_code):
    room_code = room_code.upper()
    if room_code not in rooms:
        return render_template(
            "index.jinja-html", page="setup", error="Room not found!"
        )

    room = rooms[room_code]
    player_id = _get_player_id()

    if player_id in room["players"]:
        return redirect(url_for("lobby", room_code=room_code))

    if len(room["players"]) >= room["max_players"]:
        return render_template(
            "index.jinja-html", page="setup", error="Room is full!"
        )

    name = request.form.get("player_name", "").strip()
    if not name:
        return render_template(
            "index.jinja-html",
            page="join",
            room_code=room_code,
            room=room,
            error="Enter your name!",
        )

    idx = len(room["player_order"])
    room["players"][player_id] = {"name": name, "idx": idx}
    room["player_order"].append(player_id)

    return redirect(url_for("lobby", room_code=room_code))


@app.route("/lobby/<room_code>")
def lobby(room_code):
    room_code = room_code.upper()
    if room_code not in rooms:
        return render_template(
            "index.jinja-html", page="setup", error="Room not found!"
        )

    room = rooms[room_code]
    player_id = _get_player_id()

    if player_id not in room["players"]:
        return redirect(url_for("join_page", room_code=room_code))

    if room["phase"] == "playing":
        return redirect(url_for("online_play", room_code=room_code))

    is_host = player_id == room["host_id"]
    return render_template(
        "index.jinja-html",
        page="lobby",
        room_code=room_code,
        room=room,
        is_host=is_host,
        player_id=player_id,
    )


@app.route("/start_room/<room_code>", methods=["POST"])
def start_room(room_code):
    room_code = room_code.upper()
    if room_code not in rooms:
        return redirect(url_for("index"))

    room = rooms[room_code]
    player_id = _get_player_id()
    if player_id != room["host_id"]:
        return redirect(url_for("lobby", room_code=room_code))

    if len(room["players"]) < 2:
        return redirect(url_for("lobby", room_code=room_code))

    names = [room["players"][pid]["name"] for pid in room["player_order"]]
    gs = g.new_game(len(names), names)
    room["game_state"] = gs
    room["phase"] = "playing"

    return redirect(url_for("online_play", room_code=room_code))


@app.route("/play/<room_code>")
def online_play(room_code):
    room_code = room_code.upper()
    if room_code not in rooms:
        return render_template(
            "index.jinja-html", page="setup", error="Room not found!"
        )

    room = rooms[room_code]
    player_id = _get_player_id()

    if player_id not in room["players"]:
        return redirect(url_for("join_page", room_code=room_code))

    gs = room["game_state"]
    if gs is None:
        return redirect(url_for("lobby", room_code=room_code))

    my_idx = room["players"][player_id]["idx"]
    submitted = {p for _, p in gs.chosen_cards}
    rankings = g.get_rankings(gs) if gs.phase == "game_over" else None

    # Determine if page should auto-refresh (waiting for others)
    waiting = False
    if gs.phase == "pick" and my_idx in submitted:
        waiting = True
    elif gs.phase == "choose_row" and gs.waiting_player != my_idx:
        waiting = True

    return render_template(
        "index.jinja-html",
        page="online_play",
        gs=gs,
        submitted=submitted,
        rankings=rankings,
        points=gs.points_table,
        max_cols=g.MAX_COLS,
        room_code=room_code,
        my_idx=my_idx,
        is_host=player_id == room["host_id"],
        waiting=waiting,
    )


@app.route("/submit_card_online/<room_code>", methods=["POST"])
def submit_card_online(room_code):
    room_code = room_code.upper()
    if room_code not in rooms:
        return redirect(url_for("index"))

    room = rooms[room_code]
    player_id = _get_player_id()
    if player_id not in room["players"]:
        return redirect(url_for("index"))

    gs = room["game_state"]
    if gs is None:
        return redirect(url_for("index"))

    my_idx = room["players"][player_id]["idx"]
    card = int(request.form["card"])
    g.submit_card(gs, my_idx, card)

    return redirect(url_for("online_play", room_code=room_code))


@app.route("/choose_row_online/<room_code>", methods=["POST"])
def choose_row_online(room_code):
    room_code = room_code.upper()
    if room_code not in rooms:
        return redirect(url_for("index"))

    room = rooms[room_code]
    player_id = _get_player_id()
    if player_id not in room["players"]:
        return redirect(url_for("index"))

    gs = room["game_state"]
    if gs is None:
        return redirect(url_for("index"))

    my_idx = room["players"][player_id]["idx"]
    if gs.waiting_player != my_idx:
        return redirect(url_for("online_play", room_code=room_code))

    row_idx = int(request.form["row_idx"])
    g.choose_row(gs, row_idx)

    return redirect(url_for("online_play", room_code=room_code))


@app.route("/restart_room/<room_code>", methods=["POST"])
def restart_room(room_code):
    room_code = room_code.upper()
    if room_code not in rooms:
        return redirect(url_for("index"))

    room = rooms[room_code]
    player_id = _get_player_id()
    if player_id != room["host_id"]:
        return redirect(url_for("online_play", room_code=room_code))

    names = [room["players"][pid]["name"] for pid in room["player_order"]]
    gs = g.new_game(len(names), names)
    room["game_state"] = gs

    return redirect(url_for("online_play", room_code=room_code))


# ── Run ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True, port=5000)
