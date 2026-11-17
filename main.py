# WLETIT BROKER v6 - MATURE - FIXED MARKETS + SETTINGS + WALLET + KYC
from flask import Flask, request, redirect, render_template_string, jsonify, session
import random, os, sqlite3, threading, json, urllib.request, hashlib
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "wletit-secret-123")

DB = "wletit.db"
lock = threading.Lock()

market = {
    "EURUSD": 1.0850, "GBPUSD": 1.2700, "USDJPY": 149.50,
    "XAUUSD": 2350.00, "BTCUSD": 97000.00, "ETHUSD": 3400.00,
    "SOLUSD": 170.00, "DOGEUSD": 0.16,
    "AAPL": 210.50, "TSLA": 250.00, "NVDA": 880.00, "AMZN": 195.00,
}
history_data = {sym: [price] for sym, price in market.items()}

def init_db():
    con = sqlite3.connect(DB)
    con.execute("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, balance REAL, portfolio TEXT, history TEXT, full_name TEXT, email TEXT, phone TEXT, country TEXT, kyc_status TEXT, avatar TEXT, created_at TEXT, transactions TEXT)")
    con.commit()
    for u,p,b in [("wletit","1234",10000),("demo","demo",5000)]:
        cur = con.execute("SELECT username FROM users WHERE username=?", (u,))
        if not cur.fetchone():
            con.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (u, hashlib.sha256(p.encode()).hexdigest(), b, "{}", "[]", u, "", "", "Nigeria", "Unverified", "", datetime.now().strftime("%Y-%m-%d"), "[]"))
    con.commit(); con.close()

def hash_pw(p): return hashlib.sha256(p.encode()).hexdigest()

def get_user(username):
    con = sqlite3.connect(DB); con.row_factory = sqlite3.Row
    cur = con.execute("SELECT * FROM users WHERE username=?", (username,))
    row = cur.fetchone(); con.close()
    if not row: return None
    d = dict(row)
    d["portfolio"] = json.loads(d["portfolio"] or "{}")
    d["history"] = json.loads(d["history"] or "[]")
    d["transactions"] = json.loads(d["transactions"] or "[]")
    return d

def save_user(u):
    with lock:
        con = sqlite3.connect(DB)
        con.execute("UPDATE users SET password=?, balance=?, portfolio=?, history=?, full_name=?, email=?, phone=?, country=?, kyc_status=?, avatar=?, transactions=? WHERE username=?",
            (u["password"], u["balance"], json.dumps(u["portfolio"]), json.dumps(u["history"]), u.get("full_name",""), u.get("email",""), u.get("phone",""), u.get("country",""), u.get("kyc_status","Unverified"), u.get("avatar",""), json.dumps(u.get("transactions",[])), u["username"]))
        con.commit(); con.close()

def create_user(username, password, full_name="", email=""):
    con = sqlite3.connect(DB)
    try:
        con.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (username, hash_pw(password), 10000, "{}", "[]", full_name or username, email, "", "Nigeria", "Unverified", "", datetime.now().strftime("%Y-%m-%d"), "[]"))
        con.commit(); return True
    except: return False
    finally: con.close()

init_db()

def fetch_real_prices():
    try:
        with urllib.request.urlopen("https://api.binance.com/api/v3/ticker/price?symbols=%5B%22BTCUSDT%22,%22ETHUSDT%22,%22SOLUSDT%22,%22DOGEUSDT%22%5D", timeout=5) as r:
            data = json.loads(r.read())
            mp = {d["symbol"]: float(d["price"]) for d in data}
            market["BTCUSD"] = round(mp.get("BTCUSDT", market["BTCUSD"]), 2)
            market["ETHUSD"] = round(mp.get("ETHUSDT", market["ETHUSD"]), 2)
            market["SOLUSD"] = round(mp.get("SOLUSDT", market["SOLUSD"]), 2)
            market["DOGEUSD"] = round(mp.get("DOGEUSDT", market["DOGEUSD"]), 4)
    except Exception as e:
        print("Binance failed:", e)
        for sym in market:
            market[sym] = round(market[sym] * (1 + random.uniform(-0.001, 0.001)), 4)
    for sym, price in market.items():
        history_data[sym].append(price)
        if len(history_data[sym]) > 40: history_data[sym].pop(0)

def get_pnl(user_obj):
    total=0; rows=[]
    for sym, pos in user_obj["portfolio"].items():
        cur = market.get(sym, pos["entry"])
        pnl = round((cur - pos["entry"]) * pos["qty"] * 100, 2)
        total+=pnl
        rows.append({"sym": sym, "qty": pos["qty"], "entry": pos["entry"], "cur": cur, "pnl": pnl})
    return rows, round(total,2)

BASE_CSS = """
* { box-sizing: border-box; } body { font-family: 'Segoe UI', Arial; background: #0a0e1a; color: white; margin: 0; padding: 12px; }
.top { max-width: 1100px; margin: auto; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap:10px; }
.logo { font-size: 22px; font-weight: 800; } .logo span { color: #22c55e; }
.nav a { color: white; text-decoration: none; margin-left: 14px; font-size: 14px; } .nav a:hover { color: #22c55e; }
.card { background: #151c2e; padding: 16px; border-radius: 16px; max-width: 1100px; margin: 12px auto; border: 1px solid #26314d; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; } @media(max-width:750px){ .grid{ grid-template-columns: 1fr; } }
.price-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(125px, 1fr)); gap: 9px; }
.coin { background: #0f1626; padding: 11px; border-radius: 12px; cursor: pointer; border: 2px solid transparent; } .coin.active { border-color: #22c55e; }
.up { color: #22c55e; } .down { color: #ef4444; }
input, select, button { padding: 12px; margin: 5px 0; border-radius: 10px; border: none; width: 100%; font-size: 15px; }
button { background: #22c55e; color: white; cursor: pointer; font-weight: 800; } .sell { background: #ef4444; } .gray { background: #334155; } .blue { background: #2563eb; }
.row { display: flex; gap: 10px; } .row button { flex: 1; } .small { color: #94a3b8; font-size: 13px; }
canvas { background: #0f1626; border-radius: 12px; padding: 8px; } .pnl-box { background: #0f1626; padding: 12px; border-radius: 12px; margin: 10px 0; } a { color: #60a5fa; }
.badge { padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: 700; } .badge-verified { background: #22c55e; } .badge-pending { background: #f59e0b; color: black; } .badge-unverified { background: #64748b; }
table { width: 100%; border-collapse: collapse; font-size: 14px; } td, th { padding: 8px; border-bottom: 1px solid #26314d; text-align: left; }
"""

HOME_HTML = """
<!DOCTYPE html><html><head><title>Wletit Broker - Mature</title><meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="manifest" href="/manifest.json"><meta name="theme-color" content="#22c55e">
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script>if('serviceWorker' in navigator){navigator.serviceWorker.register('/sw.js')}</script>
<style>""" + BASE_CSS + """</style></head><body>
<div class="top"><div class="logo">WLETIT <span>BROKER</span> <span style="font-size:11px;background:#22c55e;color:white;padding:3px 8px;border-radius:20px;">PRO</span></div>
{% if user %}<div class="nav"><a href="/">Trade</a><a href="/wallet">Wallet</a><a href="/leaderboard">Leaderboard</a><a href="/settings">⚙️ {{ user }}</a><a href="/logout">Logout</a></div>
<div>Balance: <b style="color:#22c55e;">$<span id="balance">{{ balance }}</span></b> | PnL: <b id="totalPnl">${{ total_pnl }}</b></div>{% endif %}</div>
{% if not user %}
<div class="card" style="max-width:420px;text-align:center;"><h2>Trade Like a Pro 📈</h2><p class="small">Real market data • Paper trading • Secure accounts</p>
<form method="POST" action="/login"><input name="username" placeholder="Username" required><input name="password" type="password" placeholder="Password" required><button>Login</button></form>
<p>New? <a href="/register">Create account - Get $10,000 demo</a></p><p class="small">Demo: wletit / 1234</p></div>
{% else %}
<div class="card"><div style="display:flex;justify-content:space-between;align-items:center;"><h3>🟢 <span id="chartSym">BTCUSD</span> - Live</h3><button onclick="toggleSound()" id="soundBtn" class="gray" style="width:auto;padding:8px 14px;">🔔 Sound: OFF</button></div><canvas id="myChart" height="110"></canvas><p class="small">Click a market to change chart. KYC: <span class="badge badge-{{ 'verified' if kyc=='Verified' else 'pending' if kyc=='Pending' else 'unverified' }}">{{ kyc }}</span> <a href="/settings">Complete verification →</a></p></div>
<div class="grid"><div class="card"><h3>Markets</h3><div class="price-grid" id="markets"><p class="small">Loading markets...</p></div></div>
<div class="card"><h3>Trade - <span id="tradeSym">BTCUSD</span></h3><p>Welcome, <b>{{ full_name }}</b> (@{{ user }})</p>
<div class="pnl-box"><b>💰 Positions & PnL</b><br>{% for p in pnl_rows %}{{ p.sym }}: {{ p.qty }} lot | Entry ${{ p.entry }} → Now ${{ p.cur }} | <b>PnL ${{ p.pnl }}</b><br>{% else %}<span class="small">No positions yet.</span>{% endfor %}<br><b>Total PnL: ${{ total_pnl }}</b></div>
<form method="POST" action="/trade"><input type="hidden" name="symbol" id="symbolInput" value="BTCUSD"><input name="lot" type="number" step="0.01" value="0.1" required><select name="leverage"><option value="10">x10</option><option value="50">x50</option><option value="100" selected>x100</option><option value="500">x500 🔥</option></select><div class="row"><button name="action" value="buy">BUY ▲</button><button name="action" value="sell" class="sell">SELL ▼</button></div></form>
<h3>Recent Trades</h3>{% for t in history %}<p style="font-size:13px;">{{ t }}</p>{% endfor %}</div></div>
{% endif %}
<script>
let selected="BTCUSD", chart, prevPrices={}, soundOn=false, audioCtx=null;
function toggleSound(){soundOn=!soundOn;let b=document.getElementById("soundBtn");if(b) b.innerText=soundOn?"🔔 Sound: ON":"🔔 Sound: OFF";if(soundOn)audioCtx=new (window.AudioContext||window.webkitAudioContext)();}
function beep(f){if(!soundOn||!audioCtx)return;let o=audioCtx.createOscillator(),g=audioCtx.createGain();o.connect(g);g.connect(audioCtx.destination);o.frequency.value=f;o.type='sine';g.gain.value=0.15;o.start();o.stop(audioCtx.currentTime+0.15);}
async function loadPrices(){
  try{
    let res=await fetch("/api/prices");let data=await res.json();
    let el=document.getElementById("markets"); if(!el) return;
    let html="";for(let sym in data.market){let price=data.market[sym];let old=prevPrices[sym]||price;let cls=price>=old?"up":"down";let arrow=price>=old?"▲":"▼";html+=`<div class="coin ${sym===selected?'active':''}" onclick="selectCoin('${sym}')"><b>${sym}</b><p class="${cls}">$${price} ${arrow}</p></div>`;if(sym==="BTCUSD"&&prevPrices[sym]){if(price>old)beep(880);if(price<old)beep(440);}prevPrices[sym]=price;}
    el.innerHTML=html;
    let bal=document.getElementById("balance"); if(bal) bal.innerText=data.balance;
    let pnl=document.getElementById("totalPnl"); if(pnl) pnl.innerText="$"+data.total_pnl;
  }catch(e){ console.log("price load failed", e); }
}
function selectCoin(sym){selected=sym;document.getElementById("chartSym").innerText=sym;document.getElementById("tradeSym").innerText=sym;document.getElementById("symbolInput").value=sym;loadChart();loadPrices();}
async function loadChart(){let c=document.getElementById("myChart"); if(!c) return; let res=await fetch("/api/chart/"+selected);let data=await res.json();if(chart)chart.destroy();chart=new Chart(c,{type:'line',data:{labels:data.map((_,[STRIPPED]
loadPrices();loadChart();setInterval(()=>{loadPrices();loadChart();},5000);
</script></body></html>
"""

@app.route("/")
def home():
    fetch_real_prices()
    u = session.get("user")
    if u:
        obj = get_user(u)
        if obj:
            rows, total = get_pnl(obj)
            return render_template_string(HOME_HTML, user=u, full_name=obj.get("full_name") or u, balance=round(obj["balance"],2), market=market, portfolio=obj["portfolio"], history=obj["history"][-10:], pnl_rows=rows, total_pnl=total, kyc=obj.get("kyc_status","Unverified"))
    return render_template_string(HOME_HTML, user=None, market=market, pnl_rows=[], total_pnl=0, kyc="Unverified")

@app.route("/manifest.json")
def manifest():
    return jsonify({"name": "Wletit Broker", "short_name": "Wletit", "start_url": "/", "display": "standalone", "background_color": "#0a0e1a", "theme_color": "#22c55e", "icons": [{"src": "https://cdn-icons-png.flaticon.com/512/2620/2620538.png", "sizes": "512x512", "type": "image/png"}]})

@app.route("/sw.js")
def sw():
    return "self.addEventListener('install', e=>{self.skipWaiting()}); self.addEventListener('fetch', e=>{e.respondWith(fetch(e.request).catch(()=>caches.match(e.request)))});", 200, {"Content-Type": "application/javascript"}

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        u = request.form["username"]; p = request.form["password"]; fn = request.form.get("full_name",""); em = request.form.get("email","")
        if get_user(u): return "Username exists! <a href='/register'>Try again</a>"
        create_user(u, p, fn, em); session["user"] = u; return redirect("/")
    return f"""<body style="font-family:Arial;background:#0a0e1a;color:white;text-align:center;padding:20px;"><h1>Create Pro Account</h1><form method="POST" style="max-width:400px;margin:auto;background:#151c2e;padding:20px;border-radius:15px;">
    <input name="full_name" placeholder="Full Name - e.g. Clinton Oserei" required style="padding:12px;width:100%;margin:5px;border-radius:8px;"><br>
    <input name="email" placeholder="Email" type="email" required style="padding:12px;width:100%;margin:5px;border-radius:8px;"><br>
    <input name="username" placeholder="Username" required style="padding:12px;width:100%;margin:5px;border-radius:8px;"><br>
    <input name="password" type="password" placeholder="Password (min 6 chars)" required style="padding:12px;width:100%;margin:5px;border-radius:8px;"><br>
    <button style="padding:12px;width:100%;background:#22c55e;color:white;border:none;border-radius:8px;font-weight:bold;">Create - Get $10,000 Demo</button></form><br><a href="/" style="color:#60a5fa;">Back</a></body>"""

@app.route("/settings", methods=["GET","POST"])
def settings():
    u = session.get("user")
    if not u: return redirect("/")
    obj = get_user(u)
    if request.method == "POST":
        obj["full_name"] = request.form.get("full_name", obj["full_name"])
        obj["email"] = request.form.get("email", obj["email"])
        obj["phone"] = request.form.get("phone", obj["phone"])
        obj["country"] = request.form.get("country", obj["country"])
        new_pw = request.form.get("new_password","").strip()
        if new_pw: obj["password"] = hash_pw(new_pw)
        # KYC
        if request.form.get("id_type"):
            obj["kyc_status"] = "Pending"
        save_user(obj)
        return redirect("/settings")
    return render_template_string(f"""
    <!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"><title>Settings</title><style>{BASE_CSS}</style></head><body>
    <div class="top"><div class="logo">WLETIT <span>BROKER</span></div><div class="nav"><a href="/">Trade</a><a href="/wallet">Wallet</a><a href="/leaderboard">Leaderboard</a><a href="/logout">Logout</a></div></div>
    <div class="card"><h2>⚙️ Account Settings - @{obj['username']}</h2>
    <p>Member since: {obj.get('created_at','')} | Balance: ${round(obj['balance'],2)} | KYC: <span class="badge badge-{'verified' if obj.get('kyc_status')=='Verified' else 'pending' if obj.get('kyc_status')=='Pending' else 'unverified'}">{obj.get('kyc_status')}</span></p>
    <form method="POST">
    <label>Full Name</label><input name="full_name" value="{obj.get('full_name','')}">
    <label>Email</label><input name="email" value="{obj.get('email','')}">
    <label>Phone (e.g. +234...)</label><input name="phone" value="{obj.get('phone','')}" placeholder="+234 800 000 0000">
    <label>Country</label><select name="country"><option>{obj.get('country','Nigeria')}</option><option>Nigeria</option><option>Ghana</option><option>Kenya</option><option>USA</option><option>UK</option><option>Other</option></select>
    <label>New Password (leave blank to keep old)</label><input name="new_password" type="password" placeholder="New password">
    <h3>🪪 KYC Verification</h3><p class="small">For demo: select ID type to submit for review. In real broker, admin would approve.</p>
    <select name="id_type"><option value="">-- Select ID Type --</option><option>National ID (NIN)</option><option>Passport</option><option>Driver's License</option><option>Voter's Card</option></select>
    <input name="id_number" placeholder="ID Number">
    <button>Save Settings & Submit KYC</button>
    </form>
    <h3>Transaction History</h3>
    <table><tr><th>Date</th><th>Type</th><th>Amount</th><th>Status</th></tr>{''.join([f"<tr><td>{t.get('date','')}</td><td>{t.get('type','')}</td><td>${t.get('amount','')}</td><td>{t.get('status','')}</td></tr>" for t in obj.get('transactions',[])[-20:]]) or '<tr><td colspan=4>No transactions yet</td></tr>'}</table>
    </div></body></html>
    """)

@app.route("/wallet", methods=["GET","POST"])
def wallet():
    u = session.get("user")
    if not u: return redirect("/")
    obj = get_user(u)
    if request.method == "POST":
        typ = request.form.get("type"); amt = float(request.form.get("amount",0))
        if amt > 0:
            if typ == "deposit":
                obj["balance"] += amt
                obj["transactions"].append({"date": datetime.now().strftime("%Y-%m-%d %H:%M"), "type": "Deposit (Demo)", "amount": amt, "status": "Completed"})
            elif typ == "withdraw" and obj["balance"] >= amt:
                obj["balance"] -= amt
                obj["transactions"].append({"date": datetime.now().strftime("%Y-%m-%d %H:%M"), "type": "Withdraw (Demo)", "amount": amt, "status": "Completed"})
            save_user(obj)
        return redirect("/wallet")
    rows, total = get_pnl(obj)
    return render_template_string(f"""
    <!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"><title>Wallet</title><style>{BASE_CSS}</style></head><body>
    <div class="top"><div class="logo">WLETIT <span>BROKER</span></div><div class="nav"><a href="/">Trade</a><a href="/settings">Settings</a><a href="/leaderboard">Leaderboard</a><a href="/logout">Logout</a></div></div>
    <div class="card"><h2>💼 Wallet</h2><h1>Balance: ${round(obj['balance'],2)}</h1><p>Unrealized PnL: ${total} | Equity: ${round(obj['balance']+total,2)}</p>
    <div class="grid"><div><h3>Deposit (Demo)</h3><form method="POST"><input type="hidden" name="type" value="deposit"><input name="amount" type="number" placeholder="Amount e.g. 1000" required><button>Deposit Demo Funds</button></form></div>
    <div><h3>Withdraw (Demo)</h3><form method="POST"><input type="hidden" name="type" value="withdraw"><input name="amount" type="number" placeholder="Amount" required><button class="sell">Withdraw</button></form></div></div>
    <h3>Recent Transactions</h3><table><tr><th>Date</th><th>Type</th><th>Amount</th><th>Status</th></tr>{''.join([f"<tr><td>{t.get('date','')}</td><td>{t.get('type','')}</td><td>${t.get('amount','')}</td><td>{t.get('status','')}</td></tr>" for t in obj.get('transactions',[])[-20:]]) or '<tr><td colspan=4>No transactions</td></tr>'}</table>
    <p class="small">Note: This is paper trading. No real money moves. Real deposits require licensed payment provider.</p></div></body></html>
    """)

@app.route("/leaderboard")
def leaderboard():
    con = sqlite3.connect(DB); con.row_factory = sqlite3.Row
    rows = con.execute("SELECT username, full_name, balance FROM users ORDER BY balance DESC LIMIT 20").fetchall()
    con.close()
    html_rows = "".join([f"<tr><td>#{i+1}</td><td>{r['full_name'] or r['username']} (@{r['username']})</td><td>${round(r['balance'],2)}</td></tr>" for i,r in enumerate(rows)])
    return render_template_string(f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"><title>Leaderboard</title><style>{BASE_CSS}</style></head><body>
    <div class="top"><div class="logo">WLETIT <span>BROKER</span></div><div class="nav"><a href="/">Trade</a><a href="/wallet">Wallet</a><a href="/settings">Settings</a></div></div>
    <div class="card"><h2>🏆 Leaderboard - Top Traders</h2><table><tr><th>Rank</th><th>Trader</th><th>Balance</th></tr>{html_rows}</table></div></body></html>""")

@app.route("/api/prices")
def api_prices():
    fetch_real_prices()
    bal=0; total=0
    u = session.get("user")
    if u:
        obj = get_user(u)
        if obj: bal=round(obj["balance"],2); _, total = get_pnl(obj)
    return jsonify({"market": market, "balance": bal, "total_pnl": total})

@app.route("/api/chart/<sym>")
def api_chart(sym):
    return jsonify(history_data.get(sym, []))

@app.route("/login", methods=["POST"])
def login():
    username = request.form["username"]; password = request.form["password"]
    obj = get_user(username)
    if obj and obj["password"] == hash_pw(password): session["user"] = username
    elif obj and obj["password"] == password: # old plain passwords
        obj["password"] = hash_pw(password); save_user(obj); session["user"] = username
    return redirect("/")

@app.route("/trade", methods=["POST"])
def trade():
    u = session.get("user")
    if not u: return redirect("/")
    user = get_user(u)
    symbol = request.form["symbol"]; lot=float(request.form["lot"]); leverage=int(request.form["leverage"]); action=request.form["action"]
    price=market[symbol]; cost=(lot*price*100)/leverage
    if action=="buy":
        if user["balance"]<cost: user["history"].append("FAILED BUY - Not enough balance")
        else:
            user["balance"]-=cost
            old=user["portfolio"].get(symbol,{"qty":0,"entry":price}); new_qty=old["qty"]+lot; avg=(old["qty"]*old["entry"]+lot*price)/new_qty if new_qty else price
            user["portfolio"][symbol]={"qty":round(new_qty,4),"entry":round(avg,4)}
            user["history"].append(f"BUY {lot} {symbol} @ {price} Lev x{leverage}")
    else:
        pos=user["portfolio"].get(symbol)
        if not pos or pos["qty"]<lot: user["history"].append("FAILED SELL - No position")
        else:
            pnl=round((price-pos["entry"])*lot*100,2); user["balance"]+=cost+pnl; pos["qty"]=round(pos["qty"]-lot,4)
            if pos["qty"]<=0: del user["portfolio"][symbol]
            user["history"].append(f"SELL {lot} {symbol} @ {price} Lev x{leverage} | PnL ${pnl}")
    save_user(user)
    return redirect("/")

@app.route("/logout")
def logout():
    session.pop("user", None); return redirect("/")

if __name__ == "__main__":
    port=int(os.environ.get("PORT",5000)); app.run(host="0.0.0.0", port=port)
