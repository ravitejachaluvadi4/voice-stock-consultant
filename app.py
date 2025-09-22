# app.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
from pydantic import BaseModel
from typing import List, Dict, Any
import uvicorn, sqlite3, time, csv, os

# ============ CONFIG ============
DB = "mvp.db"
PATHWAY_CSV = "pathway_mock.csv"
ADVICE_PRICE = 0.20        # demo per-advice charge
PORTFOLIO_PRICE = 0.50     # demo per-portfolio analysis charge

# ============ APP ============
app = FastAPI(title="Voice Stock Consultant - MVP")

# Allow CORS for local/dev. Fine for hackathon demo; be stricter in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files from /static (so API routes under /api/* keep working)
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Serve index.html at root
@app.get("/", include_in_schema=False)
def root_index():
    index_path = static_dir / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"error": "index.html not found in static/ folder."}

# ============ DB Helpers ============
def init_db():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS usage (id INTEGER PRIMARY KEY, key TEXT, count INTEGER)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS bills (id INTEGER PRIMARY KEY, type TEXT, amount REAL, ts INTEGER, meta TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS portfolios (id INTEGER PRIMARY KEY, name TEXT, data TEXT, ts INTEGER)""")
    conn.commit()
    conn.close()

def inc_usage(key, amt=1):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("SELECT count FROM usage WHERE key=?", (key,))
    r = cur.fetchone()
    if r:
        cur.execute("UPDATE usage SET count = count + ? WHERE key=?", (amt, key))
    else:
        cur.execute("INSERT INTO usage (key, count) VALUES (?,?)", (key, amt))
    conn.commit(); conn.close()

def get_usages():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("SELECT key, count FROM usage")
    out = {k: v for k, v in cur.fetchall()}
    conn.close()
    return out

def add_bill(btype, amount, meta=""):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("INSERT INTO bills (type, amount, ts, meta) VALUES (?,?,?,?)", (btype, amount, int(time.time()), meta))
    conn.commit(); conn.close()

# ============ Pathway mock loader ============
def load_pathway_prices():
    """Return dict ticker-> {price, pe, sector}. If CSV missing, create sample."""
    if not os.path.exists(PATHWAY_CSV):
        with open(PATHWAY_CSV, "w", newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["ticker","price","pe","sector"])
            writer.writerow(["TCS","3300","28","IT"])
            writer.writerow(["INFY","1550","22","IT"])
            writer.writerow(["HDFC","2700","18","Finance"])
            writer.writerow(["RELIANCE","2400","30","Energy"])
    data = {}
    with open(PATHWAY_CSV) as f:
        reader = csv.DictReader(f)
        for r in reader:
            try:
                data[r["ticker"].upper()] = {"price": float(r["price"]), "pe": float(r["pe"]), "sector": r["sector"]}
            except Exception:
                # skip bad rows
                continue
    return data

# ============ Pydantic models ============
class PortfolioItem(BaseModel):
    ticker: str
    qty: int

class Portfolio(BaseModel):
    name: str
    items: List[PortfolioItem]

class QueryIn(BaseModel):
    portfolio: Portfolio
    question: str  # e.g., "How is my portfolio?"
    voice: bool = False

# ============ Advice engine (simple & explainable) ============
def analyze_portfolio(portfolio: Dict[str,Any], market_data: Dict[str,Any]) -> Dict[str,Any]:
    items = portfolio["items"]
    total_value = 0.0
    exposures = {}
    details = []
    not_found = []
    for it in items:
        tk = it["ticker"].upper()
        qty = it["qty"]
        m = market_data.get(tk)
        if not m:
            not_found.append(tk)
            details.append({"ticker":tk, "note":"No market data found."})
            continue
        value = m["price"] * qty
        total_value += value
        sector = m.get("sector","OTHER")
        exposures.setdefault(sector, 0)
        exposures[sector] += value
        details.append({"ticker":tk, "price": m["price"], "value": value, "pe": m.get("pe"), "sector": sector})
    sector_pct = {s: round(v/total_value*100,1) if total_value>0 else 0 for s,v in exposures.items()}
    advices = []
    # concentration rules
    for d in details:
        if "value" in d and total_value>0:
            pct = d["value"]/total_value*100
            if pct > 40:
                advices.append(f"You hold {d['ticker']} which is {pct:.0f}% of portfolio — concentration risk; consider reducing position.")
            elif d.get("pe") and d["pe"] > 40:
                advices.append(f"{d['ticker']}'s P/E ({d['pe']}) is high; consider trimming exposure.")
            else:
                advices.append(f"{d['ticker']}: no immediate concern — hold.")
    if len(sector_pct) < 2:
        advices.append("Your portfolio is not diversified across sectors — consider adding non-IT stocks like Finance or Pharma.")
    if not_found:
        advices.append("Note: data for " + ", ".join(not_found) + " not found in data source.")
    summary = " ".join(advices[:4]) if advices else "No strong signals — portfolio looks balanced based on available data."
    return {"summary": summary, "details": details, "sector_pct": sector_pct}

# Optional LLM polish placeholder
def polish_with_llm(summary_text):
    # For MVP we return summary as-is. If you add OpenAI or other LLM, call it here to rephrase.
    return summary_text

# ============ FastAPI endpoints ============
@app.on_event("startup")
def startup():
    init_db()

@app.post("/api/voice-query")
async def voice_query(q: QueryIn):
    market = load_pathway_prices()
    portfolio = {"name": q.portfolio.name, "items": [{"ticker":it.ticker, "qty": it.qty} for it in q.portfolio.items]}
    analysis = analyze_portfolio(portfolio, market)
    text = analysis["summary"]
    polished = polish_with_llm(text)
    # billing & usage
    inc_usage("advices_generated", 1)
    add_bill("advice", ADVICE_PRICE, meta=f"portfolio:{portfolio['name']}")
    return {"advice_text": polished, "analysis": analysis, "billed": ADVICE_PRICE}

@app.post("/api/portfolio")
async def add_portfolio(p: Portfolio):
    conn = sqlite3.connect(DB); cur = conn.cursor()
    cur.execute("INSERT INTO portfolios (name, data, ts) VALUES (?,?,?)", (p.name, str([x.dict() for x in p.items]), int(time.time())))
    conn.commit(); conn.close()
    inc_usage("portfolios_analyzed", 1)
    add_bill("portfolio_analysis", PORTFOLIO_PRICE, meta=f"portfolio:{p.name}")
    return {"ok": True}

@app.get("/api/usage")
async def usage():
    return get_usages()

@app.get("/api/bills")
async def bills():
    conn = sqlite3.connect(DB); cur = conn.cursor()
    cur.execute("SELECT id, type, amount, ts, meta FROM bills ORDER BY ts DESC")
    rows = [{"id":r[0],"type":r[1],"amount":r[2],"ts":r[3],"meta":r[4]} for r in cur.fetchall()]
    conn.close()
    return rows

@app.get("/api/health")
async def health():
    return {"ok": True, "note": "Voice Stock Consultant MVP running."}

if __name__ == "__main__":
    uvicorn.run("app:app", port=8000, reload=True)
