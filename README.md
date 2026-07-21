# Skylark Drones — Monday.com Business Intelligence Agent Suite 🛰️

A modern, full-stack **FastAPI + React Glassmorphism Web Application** that acts as an AI-powered BI Analyst for Skylark Drones. It dynamically queries live **monday.com** boards (Deals & Work Orders) via GraphQL API v2, performs data normalization/aggregation, and synthesizes founder-level business intelligence answers with live data source traces.

---

## 🌐 Live Hosted Prototype & Repository

* **Public Web Prototype**: **[https://skylark-assesment-mwoh.onrender.com](https://skylark-assesment-mwoh.onrender.com)** *(Testable online with zero local setup)*
* **GitHub Repository**: **[https://github.com/AnirudhY-025/SkyLark_Assesment](https://github.com/AnirudhY-025/SkyLark_Assesment)**
* **Database & Auth**: Supabase PostgreSQL & Auth

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          REACT GLASSMORPHISM FRONTEND                           │
│  • Executive KPI Cards  • Quick Prompt Chips  • Supabase Standalone Auth Portal  │
│  • Markdown Chat Thread • 📡 Live GraphQL Data Source Trace Cards                │
└─────────────────────────────────────────────────────────────────────────────────┘
                                       │
                         HTTP REST API (Relative Route)
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            FASTAPI BACKEND (server.py)                          │
│  • GET /api/status          • GET /api/metrics                                 │
│  • POST /api/chat           • POST /api/refresh-cache                          │
│  • GET /{full_path:path}    (SPA Static File Handler & Cache Busting Headers)   │
└─────────────────────────────────────────────────────────────────────────────────┘
                   │                                         │
        Tool-Calling Agent Loop                     GraphQL Queries
                   ▼                                         ▼
┌──────────────────────────────────────┐  ┌──────────────────────────────────────┐
│       OPENROUTER LLM CLIENT          │  │       MONDAY.COM GRAPHQL V2          │
│   • Model: openai/gpt-4o-mini        │  │   • Deals Board (5030095777)         │
│   • Autonomous Tool Execution        │  │   • Work Orders Board (5030094413)   │
└──────────────────────────────────────┘  └──────────────────────────────────────┘
```

---

## 🌟 Key Features

1. **Executive KPI Header Summary Bar**:
   - **Open Pipeline Value**: `₹68.71 Cr` across 49 active deals.
   - **Revenue Billed**: `₹2.19 Cr` across 41 work orders.
   - **Overall Win Rate**: `5.9%` (6 Won vs 95 Lost).
   - **Outstanding AR**: `₹1.19 Cr` receivables monitored.

2. **Standalone Supabase Authentication Portal**:
   - Work email registration and login with Supabase Auth.
   - 1-click **"Continue as Demo Guest Executive"** mode for instant testability without local setup.

3. **📡 Data Source Trace**:
   - Every AI response features an expandable trace card detailing exact tool names, filter parameters, and raw monday.com GraphQL JSON previews.

4. **Resilient Data Cleaning Layer**:
   - Automatic currency parsing (`₹`, `$`, Lakhs, Crores, suffix multipliers).
   - Case-insensitive fuzzy categorical matching (`normalize_sector`, `normalize_deal_status`).
   - Dynamic candidate-based column matching (`_find_col`) handling board title variations.

---

## 📁 Repository Directory Structure

```
monday-bi-agent/
├── server.py                   # FastAPI REST server & SPA static file handler
├── agent/                      # Core AI Agent Package
│   ├── __init__.py
│   ├── llm_client.py           # OpenRouter wrapper & tool-calling loop
│   ├── monday_client.py        # monday.com GraphQL API v2 client
│   ├── tools.py                # BI analysis tools & aggregation functions
│   ├── data_cleaning.py        # Currency, date, and categorical normalization
│   └── prompts.py              # System prompt & leadership update template
├── frontend/                   # React + Vite Glassmorphism Frontend
│   ├── src/
│   │   ├── components/         # AuthModal component
│   │   ├── lib/                # Supabase client helper
│   │   ├── App.jsx             # Main Dashboard UI & chat state
│   │   └── index.css           # Glassmorphism Design System CSS
│   ├── dist/                   # Compiled production static build
│   ├── package.json
│   └── vite.config.js
├── tests/                      # Automated Unit Test Suite
│   └── test_data_cleaning.py   # 18 passing unit tests
├── requirements.txt            # Python dependencies (FastAPI, Uvicorn, Pandas)
├── .env.example                # Template for required environment variables
└── README.md
```

---

## ⚙️ Environment Variables

Create a `.env` file in the root directory (or configure via cloud platform dashboard):

```env
# monday.com GraphQL API Credentials & Board IDs
MONDAY_API_TOKEN=your_monday_personal_token_here
MONDAY_WORK_ORDERS_BOARD_ID=5030094413
MONDAY_DEALS_BOARD_ID=5030095777

# OpenRouter LLM Configuration
OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENROUTER_MODEL=openai/gpt-4o-mini

# Supabase Auth Configuration
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your_supabase_anon_key_here
```

---

## 🚀 Running Locally

### 1. Install Dependencies & Build Frontend
```bash
# Install Python requirements
pip install -r requirements.txt

# Build Frontend Bundle
cd frontend
npm install
npm run build
cd ..
```

### 2. Run Test Suite
```bash
python -m pytest tests/
```

### 3. Launch Server
```bash
python server.py
```

Open **[http://localhost:8000](http://localhost:8000)** in your browser.

---

## ☁️ Deployment on Render

1. Create a **Web Service** on Render connected to `https://github.com/AnirudhY-025/SkyLark_Assesment`.
2. Configure settings:
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt && cd frontend && npm install && npm run build`
   - **Start Command**: `python server.py`
3. Add the required environment variables in the Render **Environment** tab.

---

## 🧪 Sample BI Queries to Try

- *"Give me a breakdown of deal pipeline value by sector."*
- *"What is our overall win rate and win rate by sector?"*
- *"What is our total outstanding accounts receivable from work orders?"*
- *"Which work orders are currently stuck or paused?"*
- *"Give me a leadership update on overall performance."*
