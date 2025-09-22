# Voice Stock Consultant — MVP

An intelligent stock market consultant agent built for hackathon submission.  
It simplifies stock investing for beginners by giving **clear, actionable advice** (buy/sell/hold/diversify) in plain English.

---

## ✨ Features
- 📊 **Portfolio input** — Users enter their stock holdings.  
- ⚡ **Live/updated data** — Uses `pathway_mock.csv` (replaceable with real Pathway API).  
- 🧠 **Advice generation** — Explains risks like concentration, diversification, high P/E ratios.  
- 💳 **Billing demo** — Tracks per-advice and per-portfolio charges in SQLite.  
- 📈 **Usage tracking** — Shows how many advices/portfolios analyzed.  
- 🎤 **Voice support** — Ask questions via mic in Chrome.  

---

## 🛠️ Tech Stack
- **Backend**: Python, FastAPI, SQLite  
- **Frontend**: HTML, CSS, JavaScript (served from `/static/index.html`)  
- **Data**: CSV (Pathway mock)  
- **Deployment**: Uvicorn  

---

## 🚀 Run locally

1. **Clone repo**
   ```bash
   git clone https://github.com/ravitejachaluvadi4/voice-stock-consultant.git
   cd voice-stock-consultant
