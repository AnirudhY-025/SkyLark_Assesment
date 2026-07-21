# Skylark Drones — Monday.com BI Agent

A conversational AI agent that answers founder-level business intelligence queries by dynamically querying two monday.com boards (Work Orders and Deals) via the monday.com GraphQL API.

## Architecture

```
┌──────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│   Streamlit   │────▶│  OpenRouter LLM   │────▶│  monday.com API     │
│   Chat UI     │◀────│  (tool-calling    │◀────│  (GraphQL v2)       │
│  (app.py)     │     │   agent loop)     │     │                     │
└──────────────┘     └──────────────────┘     └─────────────────────┘
       │                      │
       │               ┌──────┴──────┐
       │               │  Data        │
       │               │  Cleaning    │
       │               │  Layer       │
       │               └─────────────┘
       │
       ▼
  User asks questions → LLM decides which tools to call →
  Tools fetch/clean/aggregate data from monday.com →
  LLM synthesizes answer with caveats
```

## Setup Instructions

### 1. monday.com Board Setup (~15 min)

1. Sign up for a free monday.com account
2. Create a workspace (e.g. "Skylark BI Demo")
3. Create board **"Work Orders"**:
   - Import `data/work_orders.csv` via "Import from Excel/CSV"
   - Set column types: Dates → Date, Status fields → Status, Monetary → Numbers
4. Create board **"Deals"** the same way from `data/deals.csv`
5. Go to **Admin → Developers → My Access Tokens** and generate a Personal API Token
6. Note the board IDs from each board's URL (`monday.com/boards/<BOARD_ID>`)

### 2. OpenRouter API Key

1. Sign up at https://openrouter.ai
2. Go to **Keys** and create an API key

### 3. Environment Variables

Create a `.env` file (or use Streamlit secrets in production):

```bash
MONDAY_API_TOKEN=your_token_here
OPENROUTER_API_KEY=your_key_here
MONDAY_WORK_ORDERS_BOARD_ID=1234567890
MONDAY_DEALS_BOARD_ID=0987654321
OPENROUTER_MODEL=openai/gpt-4o-mini
```

### 4. Run Locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

### 5. Deploy to Streamlit Cloud

1. Push to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your repo, set `app.py` as entrypoint
4. Add secrets in the Streamlit Cloud dashboard

## Changing Board IDs

To point the agent at different monday.com boards, update the environment variables:

```bash
MONDAY_WORK_ORDERS_BOARD_ID=<new_id>
MONDAY_DEALS_BOARD_ID=<new_id>
```

No code changes needed — the agent dynamically discovers the board schema.

## Directory Structure

```
monday-bi-agent/
├── app.py                     # Streamlit chat UI, entrypoint
├── agent/
│   ├── __init__.py
│   ├── llm_client.py          # OpenRouter wrapper, tool-calling loop
│   ├── monday_client.py       # GraphQL calls to monday.com
│   ├── tools.py               # Tool definitions for the LLM
│   ├── data_cleaning.py       # Normalization helpers
│   └── prompts.py             # System prompt
├── data/
│   ├── work_orders.csv        # Sample data (for monday.com import only)
│   └── deals.csv
├── tests/
│   └── test_data_cleaning.py
├── requirements.txt
├── .env.example
├── README.md
└── DECISION_LOG.md
```

## Known Limitations

1. **No persistent cache** — In-memory cache resets on Streamlit server restart (~15-30 min idle timeout)
2. **Read-only** — Cannot create or update monday.com items
3. **Single user** — Session state is per-browser; concurrent users get independent sessions
4. **LLM costs** — Each query costs ~$0.001-0.01 depending on model and data volume
5. **Cross-board joins** — Fuzzy matching between boards is best-effort; some deals may not link to work orders
6. **Date parsing** — Some exotic date formats may not parse correctly
7. **Board schema coupling** — If monday.com column names change, tools will return "column not found" errors

## Sample Queries

- "How's our pipeline looking for the energy sector this quarter?"
- "What's our win rate by sector?"
- "Which work orders are overdue or at risk?"
- "Give me a leadership update on this month's performance."
- "How are we doing in Mining vs Renewables?"
- "What's our total outstanding accounts receivable?"
