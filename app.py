import secrets
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, request, session
from flask_sqlalchemy import SQLAlchemy

# ---------------------------------------------------------------------------
# App & DB setup
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = secrets.token_hex(32)  # replace with a fixed key in production

# SQLite for local dev – swap DATABASE_URL env var for MySQL/Postgres in prod:
#   e.g.  mysql+pymysql://user:pass@host/taixiu
import os
DB_URL = os.environ.get("DATABASE_URL", "sqlite:///taixiu.db")
app.config["SQLALCHEMY_DATABASE_URI"] = DB_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
STARTING_BALANCE = 36_000_000  # 36 million virtual currency


class Player(db.Model):
    __tablename__ = "players"

    id       = db.Column(db.Integer, primary_key=True)
    name     = db.Column(db.String(80), nullable=False)
    balance  = db.Column(db.BigInteger, default=STARTING_BALANCE, nullable=False)
    created  = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    rounds   = db.relationship("Round", back_populates="player", lazy="dynamic")


class Round(db.Model):
    __tablename__ = "rounds"

    id         = db.Column(db.Integer, primary_key=True)
    player_id  = db.Column(db.Integer, db.ForeignKey("players.id"), nullable=False)
    dice1      = db.Column(db.Integer, nullable=False)
    dice2      = db.Column(db.Integer, nullable=False)
    dice3      = db.Column(db.Integer, nullable=False)
    total      = db.Column(db.Integer, nullable=False)
    outcome    = db.Column(db.String(10), nullable=False)   # TAI / XIU / TRIPLE
    choice     = db.Column(db.String(10), nullable=False)   # TAI / XIU
    bet        = db.Column(db.BigInteger, nullable=False)
    profit     = db.Column(db.BigInteger, nullable=False)
    played_at  = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    player = db.relationship("Player", back_populates="rounds")


with app.app_context():
    db.create_all()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/register", methods=["POST"])
def register():
    """
    Called when the visitor submits the 'What should we call you?' form.
    Creates a new Player row, stores the player_id in the Flask session,
    and returns the starting balance so the front-end can initialise.
    """
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()

    if not name:
        return jsonify({"success": False, "message": "Bạn chưa nhập tên!"}), 400
    if len(name) > 80:
        return jsonify({"success": False, "message": "Tên quá dài (tối đa 80 ký tự)."}), 400

    player = Player(name=name, balance=STARTING_BALANCE)
    db.session.add(player)
    db.session.commit()

    session["player_id"] = player.id

    return jsonify({
        "success": True,
        "player_id": player.id,
        "name": player.name,
        "balance": player.balance,
    })


@app.route("/api/play", methods=["POST"])
def play():
    """Roll the dice, settle the bet, persist the round, return the result."""
    player_id = session.get("player_id")
    if not player_id:
        return jsonify({"success": False, "message": "Phiên hết hạn – hãy nhập lại tên."}), 401

    player = db.session.get(Player, player_id)
    if player is None:
        return jsonify({"success": False, "message": "Người chơi không tồn tại."}), 404

    data = request.get_json(silent=True) or {}
    choice = (data.get("choice") or "").upper()
    if choice not in ("TAI", "XIU"):
        return jsonify({"success": False, "message": "Lựa chọn không hợp lệ."}), 400

    try:
        bet = int(data.get("betAmount", 0))
    except (ValueError, TypeError):
        bet = 0

    if bet <= 0:
        return jsonify({"success": False, "message": "Tiền cược phải lớn hơn 0."}), 400
    if bet > player.balance:
        return jsonify({"success": False, "message": "Bạn không đủ tiền!"}), 400

    # --- Roll ---
    dices = [secrets.randbelow(6) + 1 for _ in range(3)]
    total = sum(dices)

    # --- Settle ---
    if dices[0] == dices[1] == dices[2]:
        outcome = "TRIPLE"
        profit  = -bet
        message = "🌪️ Bão! Nhà cái ăn hết tiền cược."
    elif total <= 10:
        outcome = "XIU"
        profit  = bet if choice == "XIU" else -bet
        message = "🎉 Thắng rồi!" if profit > 0 else "😞 Thua rồi."
    else:
        outcome = "TAI"
        profit  = bet if choice == "TAI" else -bet
        message = "🎉 Thắng rồi!" if profit > 0 else "😞 Thua rồi."

    player.balance += profit

    # Persist the round
    round_record = Round(
        player_id=player.id,
        dice1=dices[0], dice2=dices[1], dice3=dices[2],
        total=total,
        outcome=outcome,
        choice=choice,
        bet=bet,
        profit=profit,
    )
    db.session.add(round_record)
    db.session.commit()

    return jsonify({
        "success": True,
        "dices": dices,
        "total": total,
        "outcome": outcome,
        "choice": choice,
        "profit": profit,
        "balance": player.balance,
        "message": message,
        "broke": player.balance <= 0,
    })


@app.route("/api/history", methods=["GET"])
def history():
    """Last 10 rounds for the current player."""
    player_id = session.get("player_id")
    if not player_id:
        return jsonify({"success": False, "rounds": []}), 401

    rows = (
        Round.query
        .filter_by(player_id=player_id)
        .order_by(Round.id.desc())
        .limit(10)
        .all()
    )

    rounds = [
        {
            "dice1": r.dice1, "dice2": r.dice2, "dice3": r.dice3,
            "total": r.total,
            "outcome": r.outcome,
            "choice": r.choice,
            "bet": r.bet,
            "profit": r.profit,
        }
        for r in rows
    ]

    return jsonify({"success": True, "rounds": rounds})


if __name__ == "__main__":
    app.run(debug=True)
