# Deep Research Agent

An autonomous research agent built on **LangGraph** that plans a research
query into sub-questions, dispatches them for **parallel** web research,
**critiques its own findings** for gaps, loops back to refine the plan if
needed, and synthesizes a final, cited report — with an optional
**human-in-the-loop** approval step before research begins.

Runs entirely on free-tier infrastructure: **Groq** (Llama 3.3 70B) for
inference, **Tavily** or **DuckDuckGo** for search (no key required for the
latter), and an in-memory LangGraph checkpointer.

## Why this project

Unlike crew/agent-framework demos, this is built as an explicit,
inspectable state machine — every transition, retry, and parallel branch is
a visible node and edge in the graph, not hidden inside a framework
abstraction. It's designed to showcase LangGraph specifically:

- **Dynamic parallel fan-out** via the `Send` API (branch count = number of sub-questions, decided at runtime)
- **Human-in-the-loop** via `interrupt()` / `Command(resume=...)`
- **Checkpointing** for pausable, resumable execution across HTTP requests
- **A bounded reflection loop** (critique → replan, capped at N retries) so termination is always guaranteed
- **Structured outputs** at every LLM boundary (Pydantic schemas, not string parsing)
- **Per-branch error isolation** so one failed search doesn't kill the run

## Architecture

```
                              ┌────────────────┐
                              │     START        │
                              └────────┬────────┘
                                       ▼
                              ┌────────────────┐
                              │  plan_research    │ (LLM → structured
                              │                    │  SubQuestionList)
                              └────────┬────────┘
                                       ▼
                              ┌────────────────┐
                              │  human_approval    │ interrupt() — skipped
                              │                     │ entirely if HITL disabled
                              └────────┬────────┘
                        approved ──────┴────── rejected
                              ▼                    │
                 Send() fan-out (N branches)        │
                    ┌─────┬─────┬─────┐             │
                    ▼     ▼     ▼     ▼              │
                 ┌─────┐┌─────┐┌─────┐               │
                 │ r1  ││ r2  ││ rN  │  (parallel:    │
                 │search+summarize│    search→LLM)    │
                 └──┬──┘└──┬──┘└──┬──┘               │
                    └──────┴──────┘                   │
                           ▼                           │
                 ┌────────────────┐                    │
                 │ aggregate_findings│ (fan-in barrier)  │
                 └────────┬────────┘                    │
                           ▼                             │
                 ┌────────────────┐                      │
                 │  critique_node    │ (LLM → sufficient? │
                 └────────┬────────┘   gaps?)             │
             insufficient │  sufficient                    │
        (retries < max)   │                                 │
                 ┌─────────┐    ▼                            │
                 │increment_│ ┌────────────────┐              │
                 │  retry   │ │ synthesize_report │             │
                 └────┬─────┘ └────────┬────────┘              │
                      └───────────────►│◄─────────────────────┘
                                       ▼  (replan target)
                              ┌────────────────┐
                              │       END         │
                              └────────────────┘
```

## Project structure

```
deep-research-agent/
├── src/
│   ├── config.py          # env-based settings
│   ├── logging_config.py   # shared logging setup
│   ├── state.py             # TypedDict + Pydantic schemas
│   ├── llm.py                 # Groq client + retry-wrapped structured/text calls
│   ├── tools.py                # Tavily / DuckDuckGo search
│   ├── nodes.py                 # all graph node functions
│   └── graph.py                  # StateGraph assembly + routing
├── backend/
│   ├── main.py             # FastAPI app (start / poll / approve endpoints)
│   ├── schemas.py            # API request/response models
│   └── job_store.py            # in-memory job status store
├── frontend/
│   └── index.html            # single-file UI (polls the API, no build step)
├── tests/
│   ├── test_nodes.py       # node-level unit tests (mocked LLM/search)
│   └── test_graph_e2e.py     # full graph run incl. HITL interrupt/resume
├── cli.py                     # terminal entrypoint (no server needed)
├── requirements.txt
├── .env.example
└── README.md
```

## Setup

```bash
cd deep-research-agent
python -m venv venv && source venv/bin/activate   # or venv\Scripts\activate on Windows
pip install -r requirements.txt

cp .env.example .env
# Edit .env and set GROQ_API_KEY (free at https://console.groq.com)
# TAVILY_API_KEY is optional — DuckDuckGo is used automatically if unset.
```

## Run it

**Web app (recommended — full frontend + HITL approval in-browser):**

```bash
uvicorn backend.main:app --reload --port 8000
```

Then open `http://localhost:8000`.

**CLI (quick terminal demo, HITL approval via prompt):**

```bash
python cli.py "What are the trade-offs between LangGraph and CrewAI for production multi-agent systems?"

# Skip human approval entirely:
python cli.py "Your query here" --no-hitl
```

## Tests

```bash
pytest tests/ -v
```

All tests mock the LLM and search calls, so they run offline without API
keys and complete in seconds.

## Deployment notes (free tier)

- **Backend**: deploy `backend.main:app` to Render or Railway (both have
  free tiers suitable for a portfolio demo). Set `GROQ_API_KEY` and
  optionally `TAVILY_API_KEY` as environment variables there.
- **Frontend**: served directly by FastAPI (`StaticFiles` mount in
  `backend/main.py`), so no separate deployment is needed — one service
  serves both.
- **State**: `MemorySaver` is process-local, so job state resets on
  redeploy/restart. For a persistent demo, swap in
  `langgraph.checkpoint.sqlite.SqliteSaver` (one-line change in
  `src/graph.py`) backed by a small persistent disk on Render/Railway.

## Extension ideas (documented, not built, to keep scope honest)

- Cross-session memory: cache completed reports by topic so repeat queries
  don't re-research from scratch.
- Streaming: swap polling for Server-Sent Events so the frontend trace
  updates in real time instead of every 1.5s.
- Swap `SqliteSaver` in for durable checkpoints across restarts.
