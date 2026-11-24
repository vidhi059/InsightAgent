# Agentic Conversational Sales Reporting Agent

A conversational AI agent that lets you explore a sales database in plain English
and generate business reports (PowerPoint, email) from live data.

## Architecture

```
User (Streamlit Chat UI)
        │
        ▼
  Orchestrator (orchestrator.py)
  ┌─────────────────────────────────────────┐
  │  Receives message → asks Gemini what    │
  │  tool to call → runs tool → loops until │
  │  answer is complete                     │
  └──────────┬──────────────────────────────┘
             │
    ┌────────┼────────┬──────────────┐
    ▼        ▼        ▼              ▼
query_data  make_chart  analyze_trends  generate_report
(NL→SQL)   (charts)    (trends+anomaly) (PPTX/email)
    │
    ▼
 SQLite DB (superstore.db)
```

## Project Structure

```
project/
├── data/           ← superstore.csv
├── db/             ← superstore.db (SQLite, auto-created)
├── agents/
│   ├── orchestrator.py    ← main agent loop
│   ├── data_agent.py      ← NL→SQL with self-correction
│   ├── analysis_agent.py  ← trends + anomaly detection
│   ├── viz_agent.py       ← chart generation
│   └── report_agent.py    ← PPTX + email templates
├── tools/
│   ├── sql_guard.py       ← read-only SQL enforcement
│   └── schema_loader.py   ← live schema for LLM context
├── templates/
│   └── rep_summary.html   ← Jinja2 email template
├── output/         ← generated reports and charts
├── eval/
│   ├── questions.json     ← 25 test questions
│   └── run_eval.py        ← evaluation runner
├── app/
│   └── main.py            ← Streamlit UI
├── scripts/
│   └── load_data.py       ← CSV → SQLite loader
├── .env                   ← GEMINI_API_KEY (never commit)
└── requirements.txt
```

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set your API key in .env
GEMINI_API_KEY=your_key_here

# 3. Load the database (run once)
python scripts/load_data.py

# 4. Start the app
streamlit run app/main.py
```

## Key Features

| Feature | Description |
|---|---|
| Natural language queries | Ask questions in plain English |
| Self-correction | Retries failed SQL up to 3 times with error context |
| Read-only safety | Blocks INSERT/UPDATE/DELETE/DROP |
| Charts | Bar, line, pie charts from query results |
| Trend analysis | Period-over-period % change + z-score anomalies |
| PPTX reports | Weekly sales, quarterly trends |
| Email reports | HTML rep/segment summaries |
| Human-in-the-loop | Preview + confirm before downloading reports |
| Evaluation suite | 25 test questions with accuracy metrics |

## Running the Evaluation

```bash
python eval/run_eval.py
```

Reports: Accuracy %, self-correction rate, avg latency per question.
