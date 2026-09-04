import os
import secrets
import threading
import time
from datetime import datetime, timezone

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, session, abort
from flask_sqlalchemy import SQLAlchemy

load_dotenv()

# ---------------------------------------------------------------------------
# App & DB setup
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))

DB_URL = os.environ.get("DATABASE_URL", "sqlite:///taixiu.db")
app.config["SQLALCHEMY_DATABASE_URI"] = DB_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
STARTING_BALANCE = 36_000_000
STREAM_INTERVAL  = 10
STREAM_HISTORY   = 30
LEADERBOARD_SIZE = 10   # Top bao nhiêu người trên bảng danh vọng


class Player(db.Model):
    __tablename__ = "players"

    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(80), nullable=False)
    balance     = db.Column(db.BigInteger, default=STARTING_BALANCE, nullable=False)
    peak_balance = db.Column(db.BigInteger, default=STARTING_BALANCE, nullable=False)
    # peak_balance: số dư cao nhất từ trước đến nay của người chơi này
    created     = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    rounds      = db.relationship("Round", back_populates="player", lazy="dynamic")


class Round(db.Model):
    __tablename__ = "rounds"

    id         = db.Column(db.Integer, primary_key=True)
    player_id  = db.Column(db.Integer, db.ForeignKey("players.id"), nullable=False)
    dice1      = db.Column(db.Integer, nullable=False)
    dice2      = db.Column(db.Integer, nullable=False)
    dice3      = db.Column(db.Integer, nullable=False)
    total      = db.Column(db.Integer, nullable=False)
    outcome    = db.Column(db.String(10), nullable=False)
    choice     = db.Column(db.String(10), nullable=False)
    bet        = db.Column(db.BigInteger, nullable=False)
    profit     = db.Column(db.BigInteger, nullable=False)
    played_at  = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    player = db.relationship("Player", back_populates="rounds")


class Stream(db.Model):
    __tablename__ = "stream"

    id        = db.Column(db.Integer, primary_key=True)
    dice1     = db.Column(db.Integer, nullable=False)
    dice2     = db.Column(db.Integer, nullable=False)
    dice3     = db.Column(db.Integer, nullable=False)
    total     = db.Column(db.Integer, nullable=False)
    outcome   = db.Column(db.String(10), nullable=False)
    rolled_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


with app.app_context():
    db.create_all()
    # Migration nhẹ: thêm cột peak_balance cho DB cũ chưa có cột này
    try:
        with db.engine.connect() as conn:
            conn.execute(db.text(
                "ALTER TABLE players ADD COLUMN peak_balance BIGINT DEFAULT 36000000"
            ))
            conn.commit()
    except Exception:
        pass  # Cột đã tồn tại → bỏ qua


# ---------------------------------------------------------------------------
# Background thread – soi cầu
# ---------------------------------------------------------------------------
def stream_roller():
    time.sleep(2)
    while True:
        try:
            with app.app_context():
                dices = [secrets.randbelow(6) + 1 for _ in range(3)]
                total = sum(dices)
                if dices[0] == dices[1] == dices[2]:
                    outcome = "TRIPLE"
                elif total <= 10:
                    outcome = "XIU"
                else:
                    outcome = "TAI"

                db.session.add(Stream(
                    dice1=dices[0], dice2=dices[1], dice3=dices[2],
                    total=total, outcome=outcome
                ))
                db.session.commit()

                oldest = (Stream.query.order_by(Stream.id.desc()).offset(200).first())
                if oldest:
                    Stream.query.filter(Stream.id <= oldest.id).delete()
                    db.session.commit()
        except Exception as e:
            print(f"[stream_roller] lỗi: {e}")
        time.sleep(STREAM_INTERVAL)


_roller = threading.Thread(target=stream_roller, daemon=True)
_roller.start()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()

    if not name:
        return jsonify({"success": False, "message": "Bạn chưa nhập tên!"}), 400
    if len(name) > 80:
        return jsonify({"success": False, "message": "Tên quá dài (tối đa 80 ký tự)."}), 400

    player = Player(name=name, balance=STARTING_BALANCE, peak_balance=STARTING_BALANCE)
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
    player_id = session.get("player_id")
    if not player_id:
        return jsonify({"success": False, "message": "Phiên hết hạn – hãy nhập lại tên."}), 401

    player = db.session.get(Player, player_id)
    if player is None:
        return jsonify({"success": False, "message": "Người chơi không tồn tại."}), 404

    data   = request.get_json(silent=True) or {}
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

    dices = [secrets.randbelow(6) + 1 for _ in range(3)]
    total = sum(dices)

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

    # Cập nhật peak_balance nếu balance hiện tại vượt kỷ lục cá nhân
    if player.balance > player.peak_balance:
        player.peak_balance = player.balance

    db.session.add(Round(
        player_id=player.id,
        dice1=dices[0], dice2=dices[1], dice3=dices[2],
        total=total, outcome=outcome, choice=choice,
        bet=bet, profit=profit,
    ))
    db.session.commit()

    return jsonify({
        "success":  True,
        "dices":    dices,
        "total":    total,
        "outcome":  outcome,
        "choice":   choice,
        "profit":   profit,
        "balance":  player.balance,
        "message":  message,
        "broke":    player.balance <= 0,
    })


@app.route("/api/history", methods=["GET"])
def history():
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
    return jsonify({"success": True, "rounds": [
        {
            "dice1": r.dice1, "dice2": r.dice2, "dice3": r.dice3,
            "total": r.total, "outcome": r.outcome,
            "choice": r.choice, "bet": r.bet, "profit": r.profit,
        }
        for r in rows
    ]})


@app.route("/api/stream", methods=["GET"])
def stream():
    rows = list(reversed(
        Stream.query.order_by(Stream.id.desc()).limit(STREAM_HISTORY).all()
    ))
    return jsonify({
        "success":  True,
        "interval": STREAM_INTERVAL,
        "entries": [
            {
                "id": r.id,
                "dice1": r.dice1, "dice2": r.dice2, "dice3": r.dice3,
                "total": r.total, "outcome": r.outcome,
                "time":  r.rolled_at.strftime("%H:%M:%S"),
            }
            for r in rows
        ],
    })


@app.route("/api/leaderboard", methods=["GET"])
def leaderboard():
    """Top LEADERBOARD_SIZE người có peak_balance cao nhất mọi thời đại."""
    rows = (
        Player.query
        .order_by(Player.peak_balance.desc())
        .limit(LEADERBOARD_SIZE)
        .all()
    )
    current_id = session.get("player_id")
    entries = [
        {
            "rank":         idx + 1,
            "name":         p.name,
            "peak_balance": p.peak_balance,
            "is_me":        p.id == current_id,
        }
        for idx, p in enumerate(rows)
    ]
    return jsonify({"success": True, "entries": entries})


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------
ADMIN_KEY = os.environ.get("ADMIN_KEY", "sicbo-admin-2026")


@app.route("/admin/<key>")
def admin(key):
    if key != ADMIN_KEY:
        abort(404)

    players = Player.query.order_by(Player.peak_balance.desc()).all()

    stats = []
    for p in players:
        rounds    = Round.query.filter_by(player_id=p.id).all()
        wins      = sum(1 for r in rounds if r.profit > 0)
        losses    = sum(1 for r in rounds if r.profit < 0)
        total_bet = sum(r.bet for r in rounds)
        net       = sum(r.profit for r in rounds)
        last_seen = rounds[-1].played_at.strftime("%d/%m/%Y %H:%M") if rounds else "–"
        stats.append({
            "id": p.id, "name": p.name,
            "balance": p.balance, "peak_balance": p.peak_balance,
            "joined": p.created.strftime("%d/%m/%Y %H:%M"),
            "last_seen": last_seen,
            "total_rounds": len(rounds), "wins": wins, "losses": losses,
            "total_bet": total_bet, "net": net,
        })

    return render_template("admin.html", stats=stats, total_players=len(players))


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
