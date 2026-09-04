# 🎲 Tung Sic Bo

A virtual Sic Bo (Tài Xỉu) web game built with Flask. Players receive **36,000,000 đ** in virtual currency and compete for the all-time leaderboard. Built by **Tùng** for fun and tech exploration — no real money involved.

---

## ✨ Features

| Feature | Description |
|---|---|
| 🎲 **Sic Bo gameplay** | Roll 3 dice, bet on Big (Tài) or Small (Xỉu), 1:1 payout |
| 🌪️ **Triple rule** | All 3 dice matching → house takes the entire bet |
| 🏆 **Hall of Fame** | All-time leaderboard ranked by each player's personal peak balance |
| 🔮 **Live stream** | Auto-rolls dice every 10 seconds for trend watching (soi cầu) |
| 📋 **Round history** | Last 10 rounds shown in-game per player |
| 🔐 **Admin dashboard** | Secret URL shows full player stats and data |
| 💾 **Persistent DB** | SQLite locally, swappable to PostgreSQL/MySQL in production |
| 📱 **Responsive** | Works on desktop and mobile |

---

## 🗂️ Project Structure

```
TaiXiu/
├── app.py                  # Flask backend — routes, models, game logic
├── requirements.txt        # Python dependencies
├── .env                    # Environment variables (not committed)
├── update_duckdns.ps1      # Optional: auto-update DuckDNS IP
│
├── templates/
│   ├── index.html          # Main game UI (3 screens: welcome, game, broke)
│   └── admin.html          # Admin dashboard
│
└── static/
    ├── style.css           # All styling
    ├── scrips.js           # All front-end logic
    ├── bg new.jpg          # Background image
    └── bgvideo.mp4         # (legacy) background video
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- pip

### 1. Clone / download the project

```powershell
cd C:\Users\OS\Downloads\TaiXiu
```

### 2. Create and activate virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the project root:

```env
SECRET_KEY=your-random-secret-key-here
DATABASE_URL=sqlite:///taixiu.db
ADMIN_KEY=your-admin-password-here
```

> **SECRET_KEY** — any long random string. Used to sign session cookies.  
> **DATABASE_URL** — leave as SQLite for local, swap for production (see below).  
> **ADMIN_KEY** — the secret path segment for your admin dashboard.

### 5. Run the server

```powershell
# Kill any leftover Python processes first
Stop-Process -Name python* -Force -ErrorAction SilentlyContinue

# Start Flask
.\.venv\Scripts\python.exe app.py
```

Visit **http://127.0.0.1:5000** in your browser.

---

## 🌐 Making It Public with ngrok

ngrok tunnels your local server to a public HTTPS URL so anyone can play.

### Step 1 — Create a free ngrok account

Sign up at https://dashboard.ngrok.com/signup

### Step 2 — Get your authtoken

Go to https://dashboard.ngrok.com/get-started/your-authtoken and copy your token.

### Step 3 — Authenticate ngrok

```powershell
ngrok.exe config add-authtoken YOUR_TOKEN_HERE
```

### Step 4 — Start Flask (Terminal 1)

```powershell
cd C:\Users\OS\Downloads\TaiXiu
Stop-Process -Name python* -Force -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe app.py
```

### Step 5 — Start ngrok (Terminal 2)

```powershell
ngrok.exe http 5000
```

You will see:

```
Forwarding   https://abc123.ngrok-free.app -> http://localhost:5000
```

Share that URL with anyone. ⚠️ **Both terminals must stay open** while the game is running.

> **Note:** The ngrok URL changes every time you restart ngrok on the free tier. Upgrade to a paid plan to get a fixed domain.

---

## 🔐 Admin Dashboard

Access your private admin panel at:

```
http://127.0.0.1:5000/admin/<ADMIN_KEY>
```

Or via ngrok:

```
https://xxxx.ngrok-free.app/admin/<ADMIN_KEY>
```

Replace `<ADMIN_KEY>` with the value set in your `.env` file (default: `sicbo-admin-2026`).

The dashboard shows:
- Total players and total rounds played
- Per-player: balance, all-time peak balance, win/loss record, total wagered, join date, last seen

---

## 🗄️ Database

### Default: SQLite (local)

Zero setup. The file `instance/taixiu.db` is created automatically on first run.

### Production: PostgreSQL or MySQL

Set the `DATABASE_URL` environment variable before starting:

```env
# PostgreSQL
DATABASE_URL=postgresql://user:password@host:5432/taixiu

# MySQL
DATABASE_URL=mysql+pymysql://user:password@host:3306/taixiu
```

No code changes needed — SQLAlchemy handles the rest.

### Database schema

| Table | Key columns |
|---|---|
| `players` | `id`, `name`, `balance`, `peak_balance`, `created` |
| `rounds` | `player_id`, `dice1-3`, `total`, `outcome`, `choice`, `bet`, `profit`, `played_at` |
| `stream` | `dice1-3`, `total`, `outcome`, `rolled_at` (max 200 rows, auto-cleaned) |

---

## 🎮 Game Rules

| Result | Condition | Payout |
|---|---|---|
| **Xỉu (Small)** | Dice total 4–10 | Win: 1:1 |
| **Tài (Big)** | Dice total 11–17 | Win: 1:1 |
| **Bão (Triple)** | All 3 dice identical | House takes the full bet |

- Starting balance: **36,000,000 đ** (virtual, no real value)
- Game ends when balance reaches **0**

---

## 📡 API Reference

All endpoints return JSON.

### `POST /api/register`
Register a new player and start a session.

**Request body:**
```json
{ "name": "YourName" }
```

**Response:**
```json
{
  "success": true,
  "player_id": 1,
  "name": "YourName",
  "balance": 36000000
}
```

---

### `POST /api/play`
Place a bet and roll the dice. Requires an active session.

**Request body:**
```json
{ "choice": "TAI", "betAmount": 500000 }
```

**Response:**
```json
{
  "success": true,
  "dices": [4, 2, 6],
  "total": 12,
  "outcome": "TAI",
  "choice": "TAI",
  "profit": 500000,
  "balance": 36500000,
  "message": "🎉 Thắng rồi!",
  "broke": false
}
```

---

### `GET /api/history`
Returns the last 10 rounds for the current player.

---

### `GET /api/stream`
Returns the last 30 auto-rolled results for trend watching.

---

### `GET /api/leaderboard`
Returns the top 10 players by all-time peak balance.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3, Flask 3 |
| ORM | Flask-SQLAlchemy 3 / SQLAlchemy 2 |
| Database | SQLite (dev) / PostgreSQL or MySQL (prod) |
| Frontend | Vanilla HTML, CSS, JavaScript (no frameworks) |
| Fonts | Google Fonts — Cinzel, Inter |
| Tunnel | ngrok (for public access) |
| Config | python-dotenv |

---

## ⚙️ Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `SECRET_KEY` | ✅ | random (changes on restart) | Flask session signing key — **set a fixed value in production** |
| `DATABASE_URL` | ❌ | `sqlite:///taixiu.db` | Database connection string |
| `ADMIN_KEY` | ❌ | `sicbo-admin-2026` | Secret path for admin dashboard |

---

## 📝 Notes

- This project was built by **Tùng** for personal enjoyment and technology exploration.
- No real money is involved. All currency is virtual and has no real-world value.
- Not intended for commercial use or real gambling.
