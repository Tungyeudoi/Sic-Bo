/* ═══════════════════════════════════════════════════
   TÀI XỈU – Front-end logic
═══════════════════════════════════════════════════ */

'use strict';

// Unicode dice faces ⚀ – ⚅
const DICE_FACES = ['⚀', '⚁', '⚂', '⚃', '⚄', '⚅'];

// Keep a reference to the game table element so we can add/remove glow
const gameTable = document.getElementById('gameTable');

// Prevent double-clicks while a round is in flight
let isRolling = false;

// Current player balance (kept in sync with server responses)
let currentBalance = 36_000_000;

/* ─────────────────────────────────────────────────
   SCREEN SWITCHING
───────────────────────────────────────────────── */
function showScreen(id) {
    document.querySelectorAll('.screen').forEach(s => {
        s.classList.remove('active');
        s.classList.add('hidden');
    });
    const el = document.getElementById(id);
    el.classList.remove('hidden');
    // Trigger reflow so the CSS transition fires
    void el.offsetWidth;
    el.classList.add('active');
}

/* ─────────────────────────────────────────────────
   WELCOME SCREEN – register player
───────────────────────────────────────────────── */
// Allow pressing Enter in the name field
document.getElementById('playerName').addEventListener('keydown', e => {
    if (e.key === 'Enter') registerPlayer();
});

async function registerPlayer() {
    const nameInput = document.getElementById('playerName');
    const errorEl   = document.getElementById('welcome-error');
    const btnStart  = document.getElementById('btn-start');
    const name      = nameInput.value.trim();

    errorEl.textContent = '';
    errorEl.classList.add('hidden');

    if (!name) {
        showError(errorEl, 'Bạn chưa nhập tên!');
        nameInput.focus();
        return;
    }

    btnStart.disabled = true;
    btnStart.textContent = 'Đang xử lý…';

    try {
        const res  = await fetch('/api/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name }),
        });
        const data = await res.json();

        if (!data.success) {
            showError(errorEl, data.message || 'Đã có lỗi xảy ra.');
            return;
        }

        // Store & display player info
        currentBalance = data.balance;
        document.getElementById('display-name').textContent = data.name;
        document.getElementById('balance').textContent = fmt(currentBalance);

        showScreen('screen-game');
        loadHistory();

    } catch (err) {
        console.error(err);
        showError(errorEl, 'Không thể kết nối tới server.');
    } finally {
        btnStart.disabled = false;
        btnStart.textContent = 'Bắt đầu chơi →';
    }
}

function showError(el, msg) {
    el.textContent = msg;
    el.classList.remove('hidden');
}

/* ─────────────────────────────────────────────────
   QUICK-BET HELPERS
───────────────────────────────────────────────── */
function setBet(amount) {
    document.getElementById('bet-amount').value = amount;
}

function betAll() {
    document.getElementById('bet-amount').value = currentBalance;
}

/* ─────────────────────────────────────────────────
   MAIN GAME LOOP
───────────────────────────────────────────────── */
async function playGame(choice) {
    if (isRolling) return;

    const betInput  = document.getElementById('bet-amount');
    const bet       = parseInt(betInput.value, 10);
    const resultEl  = document.getElementById('result-text');
    const btnTai    = document.getElementById('btn-tai');
    const btnXiu    = document.getElementById('btn-xiu');
    const diceEls   = [
        document.getElementById('dice1'),
        document.getElementById('dice2'),
        document.getElementById('dice3'),
    ];

    // ── Client-side validation ──
    if (!Number.isInteger(bet) || bet <= 0) {
        flashResult(resultEl, '⚠️ Nhập số tiền cược hợp lệ!', '');
        return;
    }
    if (bet > currentBalance) {
        flashResult(resultEl, '⚠️ Bạn không đủ tiền!', '');
        return;
    }

    // ── Lock UI ──
    isRolling = true;
    btnTai.disabled = true;
    btnXiu.disabled = true;
    gameTable.classList.remove('win-glow');
    resultEl.className = 'result-display';
    resultEl.textContent = '🎲 Đang lắc…';

    // Start shake animation, reset dice face
    diceEls.forEach(d => {
        d.classList.remove('pop-in');
        d.textContent = '?';
        d.classList.add('shaking');
    });

    // ── API call ──
    let data;
    try {
        const res = await fetch('/api/play', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ choice, betAmount: bet }),
        });
        data = await res.json();
    } catch (err) {
        console.error(err);
        diceEls.forEach(d => d.classList.remove('shaking'));
        flashResult(resultEl, '❌ Mất kết nối server!', '');
        unlockUI(btnTai, btnXiu);
        return;
    }

    if (!data.success) {
        diceEls.forEach(d => d.classList.remove('shaking'));
        flashResult(resultEl, `⚠️ ${data.message}`, '');
        unlockUI(btnTai, btnXiu);
        return;
    }

    // ── Reveal dice one by one ──
    revealDice(diceEls[0], data.dices[0], 900);
    revealDice(diceEls[1], data.dices[1], 1600);
    revealDice(diceEls[2], data.dices[2], 2300, () => {
        // ── Show final result ──
        showResult(data, resultEl);

        // ── Update balance ──
        currentBalance = data.balance;
        animateBalance(data.balance);

        // ── Prepend to history panel ──
        prependHistory(data);

        // ── Unlock UI ──
        unlockUI(btnTai, btnXiu);

        // ── Broke? ──
        if (data.broke) {
            setTimeout(() => showScreen('screen-broke'), 1800);
        }
    });
}

/* ─────────────────────────────────────────────────
   DICE REVEAL
───────────────────────────────────────────────── */
function revealDice(el, value, delayMs, callback) {
    setTimeout(() => {
        el.classList.remove('shaking');
        el.textContent = DICE_FACES[value - 1];
        el.classList.add('pop-in');
        if (callback) callback();
    }, delayMs);
}

/* ─────────────────────────────────────────────────
   RESULT DISPLAY
───────────────────────────────────────────────── */
function showResult(data, el) {
    const { total, outcome, profit, message } = data;
    el.className = 'result-display';

    if (outcome === 'TRIPLE') {
        el.textContent = `🌪️ BÃOOO! Tổng ${total} – ${message}`;
        el.classList.add('result-triple');
    } else if (profit > 0) {
        el.textContent = `🎉 Tổng ${total} – ${outcome} – +${fmt(profit)} đ`;
        el.classList.add('result-win');
        gameTable.classList.add('win-glow');
    } else {
        el.textContent = `❌ Tổng ${total} – ${outcome} – -${fmt(Math.abs(profit))} đ`;
        el.classList.add('result-lose');
    }
}

function flashResult(el, text, cssClass) {
    el.className = 'result-display' + (cssClass ? ' ' + cssClass : '');
    el.textContent = text;
}

/* ─────────────────────────────────────────────────
   BALANCE ANIMATION (count-up / count-down)
───────────────────────────────────────────────── */
function animateBalance(target) {
    const el    = document.getElementById('balance');
    const start = currentBalance - 0; // already updated
    const diff  = target - start;
    if (diff === 0) { el.textContent = fmt(target); return; }

    const steps    = 30;
    const interval = 30; // ms
    let   step     = 0;

    const timer = setInterval(() => {
        step++;
        const value = Math.round(start + diff * (step / steps));
        el.textContent = fmt(value);
        if (step >= steps) {
            clearInterval(timer);
            el.textContent = fmt(target);
        }
    }, interval);
}

/* ─────────────────────────────────────────────────
   HISTORY PANEL
───────────────────────────────────────────────── */
async function loadHistory() {
    try {
        const res  = await fetch('/api/history');
        const data = await res.json();
        if (!data.success || !data.rounds.length) return;

        const list = document.getElementById('history-list');
        list.innerHTML = '';
        data.rounds.forEach(r => appendHistoryItem(list, r, false));
    } catch (e) {
        console.error('History load error:', e);
    }
}

function prependHistory(data) {
    const list = document.getElementById('history-list');

    // Remove the "no rounds yet" placeholder if present
    const placeholder = list.querySelector('.history-empty');
    if (placeholder) placeholder.remove();

    // Build a round object in the same shape as /api/history
    const round = {
        dice1: data.dices[0], dice2: data.dices[1], dice3: data.dices[2],
        total: data.total,
        outcome: data.outcome,
        choice: data.choice,
        bet: parseInt(document.getElementById('bet-amount').value, 10),
        profit: data.profit,
    };

    appendHistoryItem(list, round, true);

    // Keep only the 10 most recent items
    while (list.children.length > 10) list.lastChild.remove();
}

function appendHistoryItem(list, round, prepend) {
    const isWin    = round.profit > 0;
    const isTriple = round.outcome === 'TRIPLE';
    const dices    = `${DICE_FACES[round.dice1-1]}${DICE_FACES[round.dice2-1]}${DICE_FACES[round.dice3-1]}`;
    const profitStr = round.profit > 0
        ? `+${fmt(round.profit)} đ`
        : `${fmt(round.profit)} đ`;  // profit is already negative

    const li = document.createElement('li');
    li.className = `history-item ${isTriple ? 'lose' : (isWin ? 'win' : 'lose')}`;
    li.innerHTML = `
        <span class="h-outcome">${dices} &nbsp;Tổng ${round.total} – ${round.outcome}</span>
        <span class="h-detail">Chọn: ${round.choice} &nbsp;|&nbsp; Cược: ${fmt(round.bet)} đ</span>
        <span class="h-profit ${round.profit > 0 ? 'pos' : 'neg'}">${profitStr}</span>
    `;

    if (prepend && list.firstChild) {
        list.insertBefore(li, list.firstChild);
    } else {
        list.appendChild(li);
    }
}

/* ─────────────────────────────────────────────────
   UI HELPERS
───────────────────────────────────────────────── */
function unlockUI(btnTai, btnXiu) {
    isRolling = false;
    btnTai.disabled = false;
    btnXiu.disabled = false;
}

// Format numbers with thousands separators
function fmt(n) {
    return Number(n).toLocaleString('vi-VN');
}
