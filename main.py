# WLETIT BROKER v4 - DEPLOY READY - MULTI USER
from flask import Flask, request, redirect, render_template_string, jsonify, session
import random, os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "wletit-secret-123-change-this")

market = {
    "EURUSD": 1.0850, "GBPUSD": 1.2700, "USDJPY": 149.50,
    "XAUUSD": 2350.00, "BTCUSD": 65000.00, "ETHUSD": 3500.00,
    "SOLUSD": 170.00, "DOGEUSD": 0.16,
    "AAPL": 210.50, "TSLA": 250.00, "NVDA": 880.00, "【entity-AMZN¦canonical_name=AMZN】": 195.00,
}
history_data = {sym: [price] for sym, price in market.items()}

def update_prices():
    for sym in market:
        change = random.uniform(-0.003, 0.003)
        market[sym] = round(market[sym] * (1 + change), 4)
        history_data[sym].append(market[sym])
        if len(history_data[sym]) > 40:
            history_data[sym].pop(0)

users = {
    "wletit": {"password": "1234", "balance": 10000, "portfolio": {}, "history": []},
    "demo": {"password": "demo", "balance": 5000, "portfolio": {}, "history": []}
}

def get_pnl(user_obj):
    total_pnl = 0
    rows = []
    for sym, pos in user_obj["portfolio"].items():
        cur = market[sym]
        pnl = round((cur - pos["entry"]) * pos["qty"] * 100, 2)
        total_pnl += pnl
        rows.append({"sym": sym, "qty": pos["qty"], "entry": pos["entry"], "cur": cur, "pnl": pnl})
    return rows, round(total_pnl, 2)

HTML = """
<!DOCTYPE html>
<html>
<head>
<title>Wletit Broker v4</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
* { box-sizing: border-box; }
body { font-family: 'Segoe UI', Arial; background: #0a0e1a; color: white; margin: 0; padding: 12px; }
.top { max-width: 1000px; margin: auto; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; }
.logo { font-size: 22px; font-weight: 800; } .logo span { color: #22c55e; }
.card { background: #151c2e; padding: 16px; border-radius: 16px; max-width: 1000px; margin: 12px auto; border: 1px solid #26314d; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
@media(max-width: 750px){ .grid{ grid-template-columns: 1fr; } }
.price-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(125px, 1fr)); gap: 9px; }
.coin { background: #0f1626; padding: 11px; border-radius: 12px; cursor: pointer; border: 2px solid transparent; }
.coin.active { border-color: #22c55e; }
.coin b { font-size: 13px; } .coin p { margin: 4px 0 0; font-weight: 700; }
.up { color: #22c55e; } .down { color: #ef4444; }
input, select, button { padding: 12px; margin: 5px 0; border-radius: 10px; border: none; width: 100%; font-size: 15px; }
button { background: #22c55e; color: white; cursor: pointer; font-weight: 800; }
.sell { background: #ef4444; } .gray { background: #334155; }
.row { display: flex; gap: 10px; } .row button { flex: 1; }
.small { color: #94a3b8; font-size: 13px; }
canvas { background: #0f1626; border-radius: 12px; padding: 8px; }
.pnl-box { background: #0f1626; padding: 12px; border-radius: 12px; margin: 10px 0; }
a { color: #60a5fa; }
</style>
</head>
<body>
<div class="top">
  <div class="logo">WLETIT <span>BROKER</span> <span style="font-size:11px; background:#22c55e; color:white; padding:3px 8px; border-radius:20px;">v4 LIVE</span></div>
  {% if user %}<div>Balance: <b style="color:#22c55e; font-size:19px;">$<span id="balance">{{ balance }}</span></b> | PnL: <b id="totalPnl">${{ total_pnl }}</b> <a href="/logout">Logout</a></div>{% endif %}
</div>

{% if not user %}
<div class="card" style="max-width:400px; text-align:center;">
<h2>Welcome back 👋</h2>
<p class="small">Demo: wletit / 1234</p>
<form method="POST" action="/login">
<input name="username" placeholder="Username" required>
<input name="password" type="password" placeholder="Password" required>
<button>Login</button>
</form>
<p>New here? <a href="/register">Create account - Get $10,000</a></p>
</div>
{% else %}

<div class="card">
<div style="display:flex; justify-content:space-between; align-items:center;">
<h3>📊 <span id="chartSym">BTCUSD</span> Chart</h3>
<button onclick="toggleSound()" id="soundBtn" class="gray" style="width:auto; padding:8px 14px;">🔔 Sound: OFF</button>
</div>
<canvas id="myChart" height="120"></canvas>
<p class="small">Click a market below to change chart. Prices update every 2 seconds.</p>
</div>

<div class="grid">
<div class="card">
<h3>Markets</h3>
<div class="price-grid" id="markets"></div>
</div>

<div class="card">
<h3>Trade - <span id="tradeSym">BTCUSD</span></h3>
<p>Welcome, <b>{{ user }}</b></p>
<div class="pnl-box">
<b>💰 Your Positions & Profit/Loss</b><br>
{% for p in pnl_rows %}
{{ p.sym }}: {{ p.qty }} lot | Entry ${{ p.entry }} → Now ${{ p.cur }} | <b style="color:{{ '#22c55e' if p.pnl>=0 else '#ef4444' }};">PnL ${{ p.pnl }}</b><br>
{% else %}<span class="small">No positions yet.</span>{% endfor %}
<br><b>Total PnL: ${{ total_pnl }}</b>
</div>
<form method="POST" action="/trade">
<input type="hidden" name="symbol" id="symbolInput" value="BTCUSD">
<input name="lot" type="number" step="0.01" value="0.1" required>
<select name="leverage"><option value="10">x10</option><option value="50">x50</option><option value="100" selected>x100</option><option value="500">x500 🔥</option></select>
<div class="row"><button name="action" value="buy">BUY ▲</button><button name="action" value="sell" class="sell">SELL ▼</button></div>
</form>
<h3>History</h3>
{% for t in history %}<p style="font-size:13px;">{{ t }}</p>{% endfor %}
</div>
</div>
{% endif %}

<script>
let selected = "BTCUSD";
let chart;
let prevPrices = {};
let soundOn = false;
let audioCtx = null;
function toggleSound(){
  soundOn = !soundOn;
  document.getElementById("soundBtn").innerText = soundOn ? "🔔 Sound: ON" : "🔔 Sound: OFF";
  if(soundOn){ audioCtx = new (window.AudioContext||window.webkitAudioContext)(); }
}
function beep(freq){
  if(!soundOn || !audioCtx) return;
  let o = audioCtx.createOscillator(); let g = audioCtx.createGain();
  o.connect(g); g.connect(audioCtx.destination);
  o.frequency.value = freq; o.type = 'sine'; g.gain.value = 0.15;
  o.start(); o.stop(audioCtx.currentTime + 0.15);
}
async function loadPrices(){
  let res = await fetch("/api/prices");
  let data = await res.json();
  let html = "";
  for(let sym in data.market){
    let price = data.market[sym];
    let old = prevPrices[sym] || price;
    let cls = price >= old ? "up" : "down";
    let arrow = price >= old ? "▲" : "▼";
    html += `<div class="coin ${sym===selected?'active':''}" onclick="selectCoin('${sym}')"><b>${sym}</b><p class="${cls}">$${price} ${arrow}</p></div>`;
    if(sym==="BTCUSD" && prevPrices[sym]){
      if(price > old) beep(880);
      if(price < old) beep(440);
    }
    prevPrices[sym] = price;
  }
  document.getElementById("markets").innerHTML = html;
  if(document.getElementById("balance")) document.getElementById("balance").innerText = data.balance;
  if(document.getElementById("totalPnl")){ document.getElementById("totalPnl").innerText = "$"+data.total_pnl; document.getElementById("totalPnl").style.color = data.total_pnl>=0 ? "#22c55e" : "#ef4444"; }
}
function selectCoin(sym){
  selected = sym;
  document.getElementById("chartSym").innerText = sym;
  document.getElementById("tradeSym").innerText = sym;
  document.getElementById("symbolInput").value = sym;
  loadChart(); loadPrices();
}
async function loadChart(){
  let res = await fetch("/api/chart/" + selected);
  let data = await res.json();
  if(chart) chart.destroy();
  chart = new Chart(document.getElementById("myChart"), {
    type: 'line',
    data: { labels: data.map((_,i)=>i+1), datasets: [{ label: selected, data: data, borderColor: '#22c55e', backgroundColor: 'rgba(34,197,94,0.15)', fill: true, tension: 0.4, pointRadius: 0 }] },
    options: { plugins:{legend:{labels:{color:'white'}}}, scales:{ x:{ticks:{color:'#94a3b8'}}, y:{ticks:{color:'white'}} } }
  });
}
loadPrices(); loadChart();
setInterval(()=>{ loadPrices(); loadChart(); }, 2000);
</script>
</body>
</html>
"""

@app.route("/")
def home():
    update_prices()
    u = session.get("user")
    if u and u in users:
        user_obj = users[u]
        rows, total = get_pnl(user_obj)
        return render_template_string(HTML, user=u, balance=round(user_obj["balance"],2), market=market, portfolio=user_obj["portfolio"], history=user_obj["history"][-10:], pnl_rows=rows, total_pnl=total)
    return render_template_string(HTML, user=None, market=market, pnl_rows=[], total_pnl=0)

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        u = request.form["username"]; p = request.form["password"]
        if u in users:
            return "Username already exists! <a href='/register'>Try again</a>"
        users[u] = {"password": p, "balance": 10000, "portfolio": {}, "history": []}
        session["user"] = u
        return redirect("/")
    return """
    <body style="font-family:Arial; background:#0a0e1a; color:white; text-align:center; padding:40px;">
    <h1>Create Account</h1>
    <form method="POST" style="max-width:350px; margin:auto; background:#151c2e; padding:20px; border-radius:15px;">
    <input name="username" placeholder="Choose username" required style="padding:12px; width:100%; margin:5px; border-radius:8px;"><br>
    <input name="password" type="password" placeholder="Choose password" required style="padding:12px; width:100%; margin:5px; border-radius:8px;"><br>
    <button style="padding:12px; width:100%; background:#22c55e; color:white; border:none; border-radius:8px; font-weight:bold;">Create - Get $10,000 Demo</button>
    </form><br><a href="/" style="color:#60a5fa;">Back to Login</a></body>
    """

@app.route("/api/prices")
def api_prices():
    update_prices()
    bal = 0; total = 0
    u = session.get("user")
    if u and u in users:
        bal = round(users[u]["balance"],2)
        _, total = get_pnl(users[u])
    return jsonify({"market": market, "balance": bal, "total_pnl": total})

@app.route("/api/chart/<sym>")
def api_chart(sym):
    return jsonify(history_data.get(sym, []))

@app.route("/login", methods=["POST"])
def login():
    username = request.form["username"]; password = request.form["password"]
    if username in users and users[username]["password"] == password:
        session["user"] = username
    return redirect("/")

@app.route("/trade", methods=["POST"])
def trade():
    u = session.get("user")
    if not u or u not in users: return redirect("/")
    symbol = request.form["symbol"]; lot = float(request.form["lot"]); leverage = int(request.form["leverage"]); action = request.form["action"]
    price = market[symbol]; cost = (lot * price * 100) / leverage
    user = users[u]
    if action == "buy":
        if user["balance"] < cost:
            user["history"].append(f"FAILED BUY - Not enough balance")
        else:
            user["balance"] -= cost
            old = user["portfolio"].get(symbol, {"qty":0, "entry":price})
            new_qty = old["qty"] + lot
            avg = (old["qty"]*old["entry"] + lot*price) / new_qty if new_qty else price
            user["portfolio"][symbol] = {"qty": round(new_qty,4), "entry": round(avg,4)}
            user["history"].append(f"BUY {lot} {symbol} @ {price} Lev x{leverage}")
    else:
        pos = user["portfolio"].get(symbol)
        if not pos or pos["qty"] < lot:
            user["history"].append(f"FAILED SELL - No position")
        else:
            pnl = round((price - pos["entry"]) * lot * 100, 2)
            user["balance"] += cost + pnl
            pos["qty"] = round(pos["qty"] - lot, 4)
            if pos["qty"] <= 0: del user["portfolio"][symbol]
            user["history"].append(f"SELL {lot} {symbol} @ {price} Lev x{leverage} | PnL ${pnl}")
    return redirect("/")

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect("/")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)