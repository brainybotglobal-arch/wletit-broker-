# WLETIT v7.2 - REAL PRICE FIX - CoinGecko
from flask import Flask, request, redirect, render_template_string, jsonify, session
import random, os, sqlite3, threading, json, urllib.request, hashlib
from datetime import datetime
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "wletit-secret-123")
DATABASE_URL = os.environ.get("DATABASE_URL", "")
USE_PG = bool(DATABASE_URL)
lock = threading.Lock()
# FIXED STARTING PRICES - REAL Nov 2026 prices
market = {"EURUSD": 1.0850, "GBPUSD": 1.2700, "USDJPY": 149.50, "XAUUSD": 2350.00, "BTCUSD": 63700.00, "ETHUSD": 2100.00, "SOLUSD": 120.00, "DOGEUSD": 0.11, "AAPL": 212.00, "TSLA": 250.00, "NVDA": 880.00, "AMZN": 195.00}
history_data = {sym: [price] for sym, price in market.items()}
def get_con():
    if USE_PG:
        import psycopg2
        return psycopg2.connect(DATABASE_URL, sslmode="require")
    else:
        return sqlite3.connect("wletit.db")
def q(sql):
    return sql.replace("?", "%s") if USE_PG else sql
def init_db():
    con = get_con(); cur = con.cursor()
    if USE_PG:
        cur.execute("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, balance FLOAT, portfolio TEXT, history TEXT, full_name TEXT, email TEXT, phone TEXT, country TEXT, kyc_status TEXT, avatar TEXT, created_at TEXT, transactions TEXT)")
    else:
        cur.execute("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, balance REAL, portfolio TEXT, history TEXT, full_name TEXT, email TEXT, phone TEXT, country TEXT, kyc_status TEXT, avatar TEXT, created_at TEXT, transactions TEXT)")
    con.commit()
    for u,p,b in [("wletit","1234",10000),("demo","demo",5000)]:
        cur.execute(q("SELECT username FROM users WHERE username=?"), (u,))
        if not cur.fetchone():
            cur.execute(q("INSERT INTO users VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)"), (u, hashlib.sha256(p.encode()).hexdigest(), b, "{}", "[]", u, "", "", "Nigeria", "Unverified", "", datetime.now().strftime("%Y-%m-%d"), "[]"))
    con.commit(); con.close()
def hash_pw(p): return hashlib.sha256(p.encode()).hexdigest()
def get_user(username):
    con = get_con()
    if USE_PG:
        import psycopg2.extras
        cur = con.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    else:
        con.row_factory = sqlite3.Row
        cur = con.cursor()
    cur.execute(q("SELECT * FROM users WHERE username=?"), (username,))
    row = cur.fetchone(); con.close()
    if not row: return None
    d = dict(row); d["portfolio"] = json.loads(d["portfolio"] or "{}"); d["history"] = json.loads(d["history"] or "[]"); d["transactions"] = json.loads(d["transactions"] or "[]"); return d
def save_user(u):
    with lock:
        con = get_con(); cur = con.cursor()
        cur.execute(q("UPDATE users SET password=?, balance=?, portfolio=?, history=?, full_name=?, email=?, phone=?, country=?, kyc_status=?, avatar=?, transactions=? WHERE username=?"), (u["password"], u["balance"], json.dumps(u["portfolio"]), json.dumps(u["history"]), u.get("full_name",""), u.get("email",""), u.get("phone",""), u.get("country",""), u.get("kyc_status","Unverified"), u.get("avatar",""), json.dumps(u.get("transactions",[])), u["username"]))
        con.commit(); con.close()
def create_user(username, password, full_name="", email=""):
    con = get_con(); cur = con.cursor()
    try:
        cur.execute(q("INSERT INTO users VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)"), (username, hash_pw(password), 10000, "{}", "[]", full_name or username, email, "", "Nigeria", "Unverified", "", datetime.now().strftime("%Y-%m-%d"), "[]"))
        con.commit(); return True
    except: return False
    finally: con.close()
init_db()
def fetch_real_prices():
    # Kraken works on Render US - Binance is blocked (451)
    def get_kraken(pair, kraken_key):
        try:
            url = "https://api.kraken.com/0/public/Ticker?pair=" + pair
            with urllib.request.urlopen(url, timeout=6) as r:
                data = json.loads(r.read())
                # Kraken returns e.g. XXBTZUSD
                result = data.get("result", {})
                for k, v in result.items():
                    # v['c'] = last trade closed price [price, lot]
                    return float(v["c"][0])
        except Exception as e:
            print("Kraken fail", pair, e)
            return None
        return None

    def get_coinbase(sym):
        # Backup: Coinbase spot price
        try:
            url = "https://api.coinbase.com/v2/prices/" + sym + "-USD/spot"
            with urllib.request.urlopen(url, timeout=5) as r:
                data = json.loads(r.read())
                return float(data["data"]["amount"])
        except Exception as e:
            print("Coinbase fail", sym, e)
            return None

    # BTC
    btc = get_kraken("XBTUSD", "")
    if not btc:
        btc = get_coinbase("BTC")
    if btc:
        market["BTCUSD"] = round(btc, 2)
        print("PRICE OK - BTC:", market["BTCUSD"])

    # ETH
    eth = get_kraken("ETHUSD", "")
    if not eth:
        eth = get_coinbase("ETH")
    if eth:
        market["ETHUSD"] = round(eth, 2)

    # SOL
    sol = get_kraken("SOLUSD", "")
    if not sol:
        sol = get_coinbase("SOL")
    if sol:
        market["SOLUSD"] = round(sol, 2)

    # DOGE
    doge = get_kraken("DOGEUSD", "")
    if not doge:
        doge = get_coinbase("DOGE")
    if doge:
        market["DOGEUSD"] = round(doge, 4)

    # Small random for non-crypto only - NO SPACE in 【entity-AMZN¦canonical_name=AMZN】
    for sym in ["EURUSD","GBPUSD","USDJPY","XAUUSD","AAPL","TSLA","NVDA","AMZN"]:
        if sym in market:
            market[sym] = round(market[sym] * (1 + random.uniform(-0.0005, 0.0005)), 4)
    for sym, price in list(market.items()):
        history_data.setdefault(sym, []).append(price)
        if len(history_data[sym]) > 40:
            history_data[sym].pop(0)
def get_pnl(user_obj):
    total = 0
    rows = []
    try:
        portfolio = user_obj.get("portfolio") or {}
        for sym, pos in portfolio.items():
            try:
                if not isinstance(pos, dict):
                    continue
                entry = pos.get("entry", 0) or 0
                qty = pos.get("qty", 0) or 0
                side = pos.get("side", "buy") or "buy"
                cur = market.get(sym, entry)
                if side == "sell":
                    pnl = round((entry - cur) * qty * 100, 2)
                else:
                    pnl = round((cur - entry) * qty * 100, 2)
                total += pnl
                sl_val = pos.get("sl", 0) or 0
                tp_val = pos.get("tp", 0) or 0
                rows.append({"sym": sym, "qty": qty, "entry": entry, "cur": cur, "pnl": pnl, "sl": sl_val, "tp": tp_val, "side": side})
            except:
                continue
    except:
        pass
    return rows, round(total, 2)
CSS = "body{font-family:Arial;background:#0a0e1a;color:white;margin:0;padding:12px} .top{max-width:1100px;margin:auto;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap} .logo{font-size:22px;font-weight:800} .logo span{color:#22c55e} .nav a{color:white;margin-left:12px;text-decoration:none} .card{background:#151c2e;padding:16px;border-radius:16px;max-width:1100px;margin:12px auto;border:1px solid #26314d} .grid{display:grid;grid-template-columns:1fr 1fr;gap:12px} @media(max-width:750px){.grid{grid-template-columns:1fr}} .price-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(125px,1fr));gap:9px} .coin{background:#0f1626;padding:11px;border-radius:12px;cursor:pointer;border:2px solid transparent} .coin.active{border-color:#22c55e} .up{color:#22c55e} .down{color:#ef4444} input,select,button{padding:12px;margin:5px 0;border-radius:10px;border:none;width:100%} button{background:#22c55e;color:white;cursor:pointer;font-weight:800} .sell{background:#ef4444} .row{display:flex;gap:10px} .row button{flex:1} .small{color:#94a3b8;font-size:13px} a{color:#60a5fa}"
HOME = """
<!DOCTYPE html><html><head><title>Wletit Broker PRO</title><meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="manifest" href="/manifest.json">
<script src="https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>
<style>__CSS__</style></head><body>
<div class="top"><div class="logo">WLETIT <span>BROKER</span> PRO</div>
{% if user %}<div class="nav"><a href="/">Trade</a><a href="/wallet">Wallet</a><a href="/leaderboard">Leaderboard</a><a href="/settings">Settings</a><a href="/logout">Logout</a></div><div>Balance: <b>$<span id="balance">{{ balance }}</span></b> | PnL: <b id="totalPnl">${{ total_pnl }}</b></div>{% endif %}</div>
{% if not user %}
<div class="card" style="max-width:420px;text-align:center;"><h2>Trade Like a Pro</h2><p class="small">Paper trading - No real money - 100% Legal - Real Prices via CoinGecko</p>
<form method="POST" action="/login"><input name="username" placeholder="Username" required><input name="password" type="password" placeholder="Password" required><button>Login</button></form>
<p>New? <a href="/register">Create account - Get $10,000 demo</a></p></div>
{% else %}
<div class="card"><h3><span id="chartSym">BTCUSD</span> - Candlestick Live 🕯️</h3><div id="myChart" style="height:300px;background:#0f1626;border-radius:12px;"></div><p class="small">Green = up, Red = down. Real 【entity-Binance¦canonical_name=Binance】 candles. KYC: {{ kyc }} - <a href="/settings">Settings</a></p></div>
<div class="grid"><div class="card"><h3>Markets</h3><div class="price-grid" id="markets"><p>Loading...</p></div></div>
<div class="card"><h3>Trade - <span id="tradeSym">BTCUSD</span></h3><p>Welcome, <b>{{ full_name }}</b></p>
<div><b>Positions:</b><br>{% for p in pnl_rows %}{{ p.side.upper() }} {{ p.sym }}: {{ p.qty }} | Entry ${{ p.entry }} -> Now ${{ p.cur }} | PnL ${{ p.pnl }} | SL ${{ p.sl }} TP ${{ p.tp }}<br>{% else %}No positions yet.{% endfor %}<br><b>Total PnL: ${{ total_pnl }}</b></div>
<form method="POST" action="/trade">
  <input type="hidden" name="symbol" id="symbolInput" value="BTCUSD">
  <input name="lot" type="number" step="0.01" value="0.1" required placeholder="Lot size e.g. 0.1">
  <input name="sl" type="number" step="0.01" placeholder="Stop Loss Price (optional)">
<input name="tp" type="number" step="0.01" placeholder="Take Profit Price (optional)">
  <select name="leverage"><option value="10">x10</option><option value="50">x50</option><option value="100" selected>x100</option><option value="500">x500</option></select>
  <div class="row"><button name="action" value="buy">BUY</button><button name="action" value="sell" class="sell">SELL</button></div>
  <p class="small">SL = Auto-sell if price drops to this. TP = Auto-sell if price rises to this.</p> </form>
{% endif %}
<script>
let selected = "BTCUSD"; let candleChart = null; let candleSeries = null; let prevPrices = {};
async function loadPrices() {
  try { let res = await fetch("/api/prices"); let data = await res.json(); let el = document.getElementById("markets"); if (!el) return; let html = "";
    for (let sym in data.market) { let price = data.market[sym]; let old = prevPrices[sym] || price; let cls = price >= old ? "up" : "down"; let arrow = price >= old ? "▲" : "▼"; let active = sym === selected ? "active" : "";
      html += '<div class="coin ' + active + '" onclick="selectCoin(\\'' + sym + '\\')"><b>' + sym + '</b><p class="' + cls + '">$' + price + ' ' + arrow + '</p></div>'; prevPrices[sym] = price; }
    el.innerHTML = html; let bal = document.getElementById("balance"); if (bal) bal.innerText = data.balance; let pnl = document.getElementById("totalPnl"); if (pnl) pnl.innerText = "$" + data.total_pnl;
  } catch(e) { console.log(e); }
}
function selectCoin(sym) { selected = sym; document.getElementById("chartSym").innerText = sym; document.getElementById("tradeSym").innerText = sym; document.getElementById("symbolInput").value = sym; candleChart = null; candleSeries = null; document.getElementById("myChart").innerHTML = ""; loadChart(); loadPrices(); }
async function loadChart() {
  let el = document.getElementById("myChart"); if (!el) return;
  let map = { "BTCUSD": "BTCUSDT", "ETHUSD": "ETHUSDT", "SOLUSD": "SOLUSDT", "DOGEUSD": "DOGEUSDT" }; let binSym = map[selected] || "BTCUSDT";
  try { let res = await fetch("https://api.binance.com/api/v3/klines?symbol=" + binSym + "&interval=1m&limit=30"); let klines = await res.json();
    let data = klines.map(function(k){ return { time: Math.floor(k[0]/1000), open: parseFloat(k[1]), high: parseFloat(k[2]), low: parseFloat(k[3]), close: parseFloat(k[4]) }; });
    if (!candleChart) { candleChart = LightweightCharts.createChart(el, { layout: { background: { color: "#0f1626" }, textColor: "white" }, grid: { vertLines: { color: "#26314d" }, horzLines: { color: "#26314d" } }, width: el.clientWidth, height: 300 }); candleSeries = candleChart.addCandlestickSeries({ upColor: "#22c55e", downColor: "#ef4444", wickUpColor: "#22c55e", wickDownColor: "#ef4444", borderVisible: false }); }
    candleSeries.setData(data);
  } catch(e) { console.log("candle failed", e); }
}
loadPrices(); loadChart(); setInterval(function(){ loadPrices(); loadChart(); }, 5000);
</script>
</body></html>
"""
HOME = HOME.replace("__CSS__", CSS)
@app.route("/")
def home():
    fetch_real_prices(); u = session.get("user")
    if u:
        obj = get_user(u)
        if obj:
            rows, total = get_pnl(obj)
            return render_template_string(HOME, user=u, full_name=obj.get("full_name") or u, balance=round(obj["balance"],2), history=obj["history"][-10:], pnl_rows=rows, total_pnl=total, kyc=obj.get("kyc_status","Unverified"))
    return render_template_string(HOME, user=None, pnl_rows=[], total_pnl=0, kyc="Unverified")
@app.route("/manifest.json")
def manifest():
    return jsonify({"name": "Wletit Broker", "short_name": "Wletit", "start_url": "/", "display": "standalone", "background_color": "#0a0e1a", "theme_color": "#22c55e", "icons": [{"src": "https://cdn-icons-png.flaticon.com/512/2620/2620538.png", "sizes": "512x512", "type": "image/png"}]})
@app.route("/sw.js")
def sw():
    return "self.addEventListener('install', e=>{self.skipWaiting()});", 200, {"Content-Type": "application/javascript"}
@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        u = request.form["username"]; p = request.form["password"]
        if get_user(u): return "Username exists! <a href='/register'>Try again</a>"
        create_user(u, p, request.form.get("full_name",""), request.form.get("email","")); session["user"] = u; return redirect("/")
    return """<body style="font-family:Arial;background:#0a0e1a;color:white;text-align:center;padding:20px;"><h1>Create Pro Account</h1><form method="POST" style="max-width:400px;margin:auto;background:#151c2e;padding:20px;border-radius:15px;"><input name="full_name" placeholder="Full Name" required style="padding:12px;width:100%;margin:5px;border-radius:8px;"><br><input name="email" placeholder="Email" type="email" required style="padding:12px;width:100%;margin:5px;border-radius:8px;"><br><input name="username" placeholder="Username" required style="padding:12px;width:100%;margin:5px;border-radius:8px;"><br><input name="password" type="password" placeholder="Password" required style="padding:12px;width:100%;margin:5px;border-radius:8px;"><br><button style="padding:12px;width:100%;background:#22c55e;color:white;border:none;border-radius:8px;">Create - Get $10,000 Demo</button></form></body>"""
@app.route("/settings", methods=["GET","POST"])
def settings():
    u = session.get("user")
    if not u: return redirect("/")
    obj = get_user(u)
    if request.method == "POST":
        obj["full_name"] = request.form.get("full_name", obj["full_name"]); obj["email"] = request.form.get("email", obj["email"]); obj["phone"] = request.form.get("phone", obj["phone"]); obj["country"] = request.form.get("country", obj["country"])
        npw = request.form.get("new_password","").strip()
        if npw: obj["password"] = hash_pw(npw)
        if request.form.get("id_type"): obj["kyc_status"] = "Verified"
        save_user(obj); return redirect("/settings")
    return render_template_string(f"""<html><head><meta name="viewport" content="width=device-width, initial-scale=1"><style>{CSS}</style></head><body><div class="top"><div class="logo">WLETIT <span>BROKER</span></div><div class="nav"><a href="/">Trade</a><a href="/wallet">Wallet</a><a href="/leaderboard">Leaderboard</a><a href="/logout">Logout</a></div></div><div class="card"><h2>Settings - @{obj['username']}</h2><p>Balance: ${round(obj['balance'],2)} | KYC: <b>{obj.get('kyc_status')}</b></p><form method="POST"><input name="full_name" value="{obj.get('full_name','')}"><input name="email" value="{obj.get('email','')}"><input name="phone" value="{obj.get('phone','')}" placeholder="Phone +234..."><select name="country"><option>{obj.get('country','Nigeria')}</option><option>Nigeria</option><option>Ghana</option><option>Kenya</option><option>USA</option><option>UK</option></select><input name="new_password" type="password" placeholder="New password (blank = keep old)"><select name="id_type"><option value="">-- KYC ID Type --</option><option>National ID (NIN)</option><option>Passport</option><option>Driver License</option></select><button>Save & Verify KYC</button></form><p class="small">Demo KYC: selecting ID type will instantly set you to Verified.</p></div></body></html>""")
@app.route("/wallet", methods=["GET","POST"])
def wallet():
    u = session.get("user")
    if not u: return redirect("/")
    obj = get_user(u)
    if request.method == "POST":
        typ = request.form.get("type"); amt = float(request.form.get("amount",0))
        if amt>0:
            if typ=="deposit": obj["balance"]+=amt; obj["transactions"].append({"date": datetime.now().strftime("%Y-%m-%d %H:%M"), "type": "Deposit (Demo)", "amount": amt, "status": "Completed"})
            elif typ=="withdraw" and obj["balance"]>=amt: obj["balance"]-=amt; obj["transactions"].append({"date": datetime.now().strftime("%Y-%m-%d %H:%M"), "type": "Withdraw (Demo)", "amount": amt, "status": "Completed"})
            save_user(obj)
        return redirect("/wallet")
    rows, total = get_pnl(obj)
    tx = "".join([f"<tr><td>{t.get('date','')}</td><td>{t.get('type','')}</td><td>${t.get('amount','')}</td><td>{t.get('status','')}</td></tr>" for t in obj.get("transactions",[])[-20:]]) or "<tr><td colspan=4>No transactions</td></tr>"
    return render_template_string(f"""<html><head><meta name="viewport" content="width=device-width, initial-scale=1"><style>{CSS}</style></head><body><div class="top"><div class="logo">WLETIT <span>BROKER</span></div><div class="nav"><a href="/">Trade</a><a href="/settings">Settings</a><a href="/leaderboard">Leaderboard</a></div></div><div class="card"><h2>Wallet - Paper Trading Only</h2><h1>Balance: ${round(obj['balance'],2)}</h1><p>PnL: ${total} | Equity: ${round(obj['balance']+total,2)}</p><div class="grid"><div><form method="POST"><input type="hidden" name="type" value="deposit"><input name="amount" type="number" placeholder="Deposit amount" required><button>Deposit Demo</button></form></div><div><form method="POST"><input type="hidden" name="type" value="withdraw"><input name="amount" type="number" placeholder="Withdraw amount" required><button class="sell">Withdraw Demo</button></form></div></div><table><tr><th>Date</th><th>Type</th><th>Amount</th><th>Status</th></tr>{tx}</table><p class="small">No real money moves. Demo only.</p></div></body></html>""")
@app.route("/leaderboard")
def leaderboard():
    con = get_con()
    if USE_PG:
        import psycopg2.extras
        cur = con.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    else:
        con.row_factory = sqlite3.Row
        cur = con.cursor()
    cur.execute("SELECT username, full_name, balance FROM users ORDER BY balance DESC LIMIT 20")
    rows = cur.fetchall(); con.close()
    html_rows = "".join([f"<tr><td>#{i+1}</td><td>{r['full_name'] or r['username']} (@{r['username']})</td><td>${round(float(r['balance']),2)}</td></tr>" for i,r in enumerate(rows)])
    return render_template_string(f"""<html><head><meta name="viewport" content="width=device-width, initial-scale=1"><style>{CSS}</style></head><body><div class="top"><div class="logo">WLETIT <span>BROKER</span></div><div class="nav"><a href="/">Trade</a><a href="/wallet">Wallet</a><a href="/settings">Settings</a></div></div><div class="card"><h2>Leaderboard</h2><table><tr><th>Rank</th><th>Trader</th><th>Balance</th></tr>{html_rows}</table></div></body></html>""")
@app.route("/api/prices")
@app.route("/api/prices")
def api_prices():
    fetch_real_prices()
    bal = 0
    total = 0
    u = session.get("user")
    if u:
        obj = get_user(u)
        if obj:
            if check_user_sl_tp(obj):
                save_user(obj)
            bal = round(obj["balance"], 2)
            _, total = get_pnl(obj)
    return jsonify({"market": market, "balance": bal, "total_pnl": total})
@app.route("/api/chart/<sym>")
def api_chart(sym):
    return jsonify(history_data.get(sym, []))
@app.route("/login", methods=["POST"])
def login():
    obj = get_user(request.form["username"])
    if obj and (obj["password"] == hash_pw(request.form["password"]) or obj["password"] == request.form["password"]):
        if obj["password"] == request.form["password"]: obj["password"]=hash_pw(request.form["password"]); save_user(obj)
        session["user"] = request.form["username"]
    return redirect("/")
@app.route("/trade", methods=["POST"])
def check_user_sl_tp(user_obj):
    try:
        return _check_sl_tp_real(user_obj)
    except Exception as e:
        print("SL/TP check failed:", e)
        return False

def _check_sl_tp_real(user_obj):
    changed = False
    to_close = []
    for sym, pos in list(user_obj["portfolio"].items()):
        if not isinstance(pos, dict):
            continue
        cur = market.get(sym)
        if not cur:
            continue
        sl = pos.get("sl", 0) or 0
        tp = pos.get("tp", 0) or 0
        side = pos.get("side", "buy") or "buy"
        hit = None
        if side == "sell":
            # SHORT: SL above entry, TP below entry
            if sl > 0 and cur >= sl:
                hit = "STOP LOSS HIT"
            elif tp > 0 and cur <= tp:
                hit = "TAKE PROFIT HIT"
        else:
            # LONG: SL below entry, TP above entry
            if sl > 0 and cur <= sl:
                hit = "STOP LOSS HIT"
            elif tp > 0 and cur >= tp:
                hit = "TAKE PROFIT HIT"
        if hit:
            qty = pos["qty"]
            if side == "sell":
                pnl = round((pos["entry"] - cur) * qty * 100, 2)
            else:
                pnl = round((cur - pos["entry"]) * qty * 100, 2)
            user_obj["balance"] += (qty * pos["entry"] * 100) / 100 + pnl
            to_close.append(sym)
            user_obj["history"].append(f"{hit} - AUTO CLOSE {side.upper()} {qty} {sym} @ {cur} | PnL ${pnl} | SL:{sl} TP:{tp}")
            changed = True
    for sym in to_close:
        del user_obj["portfolio"][sym]
    return changed

@app.route("/trade", methods=["POST"])
def trade():
    u = session.get("user")
    if not u:
        return redirect("/")
    user = get_user(u)
    symbol = request.form["symbol"]
    lot = float(request.form["lot"])
    leverage = int(request.form["leverage"])
    action = request.form["action"]
    price = market[symbol]
    cost = (lot * price * 100) / leverage
    try:
        sl = float(request.form.get("sl", "") or 0)
    except:
        sl = 0
    try:
        tp = float(request.form.get("tp", "") or 0)
    except:
        tp = 0
    if user["balance"] < cost:
        user["history"].append("FAILED TRADE - Not enough balance")
        save_user(user)
        return redirect("/")
    user["balance"] -= cost
    old = user["portfolio"].get(symbol)
    # If no position, open new one in this direction
    if not old:
        user["portfolio"][symbol] = {"qty": round(lot, 4), "entry": round(price, 4), "sl": sl, "tp": tp, "side": action}
        user["history"].append(f"OPEN {action.upper()} {lot} {symbol} @ {price} Lev x{leverage} SL:{sl} TP:{tp}")
    else:
        # If same direction, add to it
        if old.get("side", "buy") == action:
            new_qty = old["qty"] + lot
            if new_qty:
                avg = (old["qty"] * old["entry"] + lot * price) / new_qty
            else:
                avg = price
            old_sl = old.get("sl", 0) or 0
            old_tp = old.get("tp", 0) or 0
            new_sl = sl if sl > 0 else old_sl
            new_tp = tp if tp > 0 else old_tp
            user["portfolio"][symbol] = {"qty": round(new_qty, 4), "entry": round(avg, 4), "sl": new_sl, "tp": new_tp, "side": action}
            user["history"].append(f"ADD {action.upper()} {lot} {symbol} @ {price} Lev x{leverage} SL:{new_sl} TP:{new_tp}")
        else:
            # Opposite direction - close the old position
            old_side = old.get("side", "buy")
            if old_side == "buy":
                pnl = round((price - old["entry"]) * lot * 100, 2)
            else:
                pnl = round((old["entry"] - price) * lot * 100, 2)
            # Use min lot so we don't over-close
            close_qty = min(lot, old["qty"])
            user["balance"] += (close_qty * price * 100) / leverage + pnl
            # Refund remaining cost difference - keep simple: add pnl
            user["balance"] += 0
            remaining = round(old["qty"] - close_qty, 4)
            if remaining <= 0:
                del user["portfolio"][symbol]
                user["history"].append(f"CLOSE {old_side.upper()} {close_qty} {symbol} @ {price} | PnL ${pnl}")
            else:
                old["qty"] = remaining
                user["history"].append(f"PARTIAL CLOSE {old_side.upper()} {close_qty} {symbol} @ {price} | PnL ${pnl}")
    save_user(user)
    return redirect("/")
@app.route("/logout")
def logout():
    session.pop("user", None); return redirect("/")
if __name__ == "__main__":
    port=int(os.environ.get("PORT",5000)); app.run(host="0.0.0.0", port=port)
