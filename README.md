# Корова 006 (6 Nimmt!)

A multiplayer implementation of the classic card game **Корова 006** (aka *6 Nimmt!*) built with Python, Flask, HTML, and CSS. Play locally on one device or online with friends via shareable room links.

## Rules

1. **104 cards** numbered 1–104, each worth 1–7 penalty points (randomly and exponentially distributed).
2. **4 rows** on the board, each starting with 1 card. Rows can hold up to 6 cards.
3. Each round, all players **simultaneously** pick a card from their hand.
4. Cards are revealed in **ascending order** and placed on the board:
   - A card goes to the row whose last card is the **nearest smaller** value.
   - If a card is **smaller than all row endings**, the player must **pick a row to take** (collecting its penalty points).
   - If a card fills the **6th slot** of a row, the player collects the first 5 cards' points and restarts the row.
5. After **10 rounds**, the player with the **fewest** penalty points wins.

## Setup

```bash
# Create virtual environment (optional)
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # Linux/macOS

# Install dependencies
pip install -r requirements.txt

# Run
python app.py
```

Then open [http://localhost:5000](http://localhost:5000) in your browser.

## Project Structure

```text
koroba-py/
├── app.py              # Flask web server & routes
├── game.py             # Pure game logic (no I/O)
├── requirements.txt    # Python dependencies
├── static/
│   └── style.css       # Styles
└── templates/
    └── index.jinja-html      # Single-page template
```

## Features

- **Local multiplayer** — 2 to 10 players on the same device.
- **Online multiplayer** — create a room, share the link, and play with friends remotely.
- **1 vs AI** — 1 player can play against AI in 3 difficulty modes -easy, medium, hard-.
- **Show/Hide hands** — each player's hand is hidden by default to prevent peeking.
- **Dark theme** with colour-coded cards by point value.
- **Game log** tracking every action and points available in board and for each player.
- **Error handling** for player names and human errors in cards placing.

## Online Multiplayer

1. On the home page, use **Create a Room** — choose the number of players (2–10) and enter your name.
2. Share the room link or code with other players.
3. Once everyone has joined the lobby, the host clicks **Start Game**.
4. Each player sees only their own hand — no peeking possible.
5. The page auto-refreshes while waiting for other players to act.

## Deployment

The app is ready for deployment on [Render](https://render.com) (free tier):

```text
Build Command:  pip install -r requirements.txt
Start Command:  gunicorn app:app --bind 0.0.0.0:$PORT --workers 1
```

> Use `--workers 1` because online rooms are stored in-memory.
