# Decision Log — Skylark Drones BI Agent

## 1. Key Assumptions

| Assumption | Rationale |
|---|---|
| **Join key = Deal Name** | Work Orders have a "Deal name masked" field that matches deal names in the Deals board. This is the primary cross-reference key. Customer Name Codes (WOCOMPANY_XXX vs COMPANYXXX) use different formats across boards. |
| **Calendar quarter, not fiscal** | "This quarter" defaults to calendar Q unless the founder specifies otherwise. Skylark's fiscal year is not documented; calendar is a safe default. |
| **"Dead" = "Lost"** | The Deals board uses "Dead" as a deal status. We normalize this to "Lost" for cleaner analysis and consistent terminology. |
| **Won stages** include G through K | Stages "G. Project Won", "H. Work Order Received", "J. Invoice sent", "K. Amount Accrued", and "Project Completed" all represent successfully won deals. "A. Lead Generated" for Won-status deals appears to be a data entry issue (stage not updated after status change). |
| **Sector taxonomy** | The 10 primary sectors (Mining, Renewables, Powerline, Railways, Construction, DSP, Tender, Security & Surveillance, Aviation, Manufacturing) plus "Others" are used. Fuzzy matching handles variants like "energy" → "Renewables". |
| **All monetary values in INR** | The work orders explicitly use Indian Rupees. Deal values appear to follow the same convention. No currency conversion needed. |
| **"Executed until current month"** means ongoing | Work orders with this execution status are treated as actively running recurring contracts. |

## 2. Trade-offs

| Decision | Chosen | Why |
|---|---|---|
| **Frontend** | Streamlit | Zero frontend code needed; built-in chat UI; free hosting on Streamlit Community Cloud. A custom React app would take 3+ extra hours. |
| **LLM access** | OpenRouter API (not direct OpenAI/Anthropic) | Keeps model swappable via one env var. The user requested OpenRouter specifically. |
| **Monday.com access** | GraphQL API via `requests` (not MCP) | Simplest implementation; no MCP server hosting needed; read-only is sufficient. MCP would add complexity for a 6-hour build. |
| **Caching** | In-memory dict with TTL (5 min) | Avoids re-fetching on every chat turn within a conversation. A real DB (Redis, SQLite) would be overkill for a prototype. |
| **Data cleaning** | pandas + rapidfuzz | General-purpose cleaners that work across boards without hardcoding. The rapidfuzz approach handles the messy sector and status labels gracefully. |
| **Tool-calling agent** | OpenAI-compatible function calling via OpenRouter | Standard pattern; works with GPT-4o-mini, Claude, and other tool-calling models. Simple agent loop (~40 lines) rather than LangChain/AutoGen abstraction. |
| **CSV files stored in repo** | Only for manual monday.com import | The agent never reads CSVs at runtime; it always queries the monday.com API. CSVs are reference data for the setup step. |

## 3. Data Quality Issues Observed

From inspecting the real CSVs:
- **Deals**: ~15% of deals have no deal value; ~20% have no closure probability; some rows contain embedded header rows (data entry errors); multiple duplicate rows for the same deal
- **Work Orders**: Some rows have missing dates, missing execution status, or `#VALUE!` errors in financial columns; inconsistent invoice status labels ("BIlled" typo, "Update Required", "Not Billable")
- Both datasets have missing owner codes and some completely empty rows

The agent transparently reports these via the `data_quality_notes` mechanism.

## 4. "Leadership Updates" Interpretation

**Interpretation:** An on-demand, structured brief generated in the chat when the founder asks for a "leadership update", "exec summary", or clicks the sidebar button.

**Scope:** Company-wide by default, or filtered to a specific sector. Includes:
- Headline metrics (pipeline value, win rate, total billed, total collected, outstanding AR)
- Pipeline breakdown by stage
- Sector performance summary
- Work order execution status distribution
- Top 5 data quality caveats
- Generated as copy-paste-ready Markdown

**Why on-demand, not scheduled:** With a 6-hour build window, a scheduled email digest requires email service integration, scheduling infrastructure, and template design. On-demand in-chat is simpler, more flexible, and founders can ask follow-ups immediately.

**Alternative considered:** A dedicated "Dashboard" page in Streamlit with charts. Rejected because the assignment specifically asks for a *conversational* interface, and chart-heavy dashboards don't leverage the LLM's strength in narrative summaries.

## 5. What I'd Do Differently With More Time

1. **Persistent cache** — Use SQLite or Redis so the agent doesn't lose data on Streamlit server restart
2. **MCP server** — Two-way write access so the agent can update deal stages or create follow-up tasks
3. **Automated data quality scoring** — A composite "data health score" per board with trend tracking
4. **Scheduled leadership digests** — Weekly email/Slack summaries pushed to founders
5. **Proper eval harness** — Test the agent's answers against known-correct responses from the CSVs
6. **Streaming responses** — Use OpenRouter streaming for faster perceived response time
7. **Multi-turn context management** — Summarize older conversation turns to stay within token limits
8. **Custom Streamlit components** — Interactive charts (Plotly) embedded in chat responses
9. **Fuzzy join optimization** — Better cross-referencing between boards using client codes + deal names with weighted scoring
10. **Role-based access** — Different views for founders vs. ops managers vs. BD teams
