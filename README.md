# Agentic Financial Reconciliation

An AI-powered financial reconciliation system that uses **Cognee** as a shared knowledge graph memory layer for LLM agents orchestrated by **LangGraph**.

The system ingests bank transactions and invoices into a Cognee knowledge graph, then deploys three LLM agents that query the graph to match transactions, detect anomalies, and generate reports.

## Architecture

```
                        ┌─────────────────────┐
                        │   Cognee Knowledge   │
                        │       Graph          │
                        │  238 nodes, 797 edges│
                        └──────────┬───────────┘
                                   │ search_tool
                    ┌──────────────┼──────────────┐
                    │              │              │
              ┌─────▼─────┐ ┌─────▼─────┐ ┌─────▼─────┐
              │ Matching   │ │ Anomaly   │ │ Reporting │
              │ Agent      │ │ Agent     │ │ Agent     │
              │ (LLM)      │ │ (LLM)    │ │ (LLM)     │
              └─────┬──────┘ └─────┬─────┘ └─────┬─────┘
                    │              │              │
                    └──────────────┼──────────────┘
                                   │
                           LangGraph Pipeline
```

### How Cognee adds value

Cognee builds a knowledge graph from raw financial data, creating entity nodes (counterparties, amounts, references, IBANs) and relationship edges between them. When the matching agent needs to reconcile a bank transaction, it queries Cognee with natural language — e.g., *"Find invoices related to Bergmann Verpackungen GmbH for 4,250 EUR"* — and Cognee returns graph completions that show the full entity relationship:

```
Bank Transaction BT-001 (4,250 EUR)
  ├── counterparty: Bergmann Verpackungen GmbH
  ├── reference: RE-2026-0001
  └── IBAN: DE72500105176412345678
        │
        └── linked to ──> Invoice INV-001 (RE-2026-0001)
                            ├── counterparty: Bergmann Verpackungen GmbH (C1001)
                            ├── amount: 4,250 EUR
                            └── status: completed
```

This enables the LLM to reason about matches using structured relationships rather than pattern matching on raw text.

### Agents

| Agent | Role | Uses Cognee? |
|-------|------|:---:|
| **Matching** | Queries knowledge graph for every bank transaction to find matching invoices | Yes |
| **Anomaly Detection** | Flags ghost payments, duplicates, late payments; LLM investigates critical ones | Yes |
| **Reporting** | Generates structured markdown report for treasury team | No |

### Match types detected

- **Perfect match** — exact reference + exact amount
- **Skonto** — early payment discount (1-3%)
- **Batch payment** — single bank transaction covers multiple invoices
- **Partial payment** — installment / advance payment
- **Cross-entity** — subsidiary pays parent's invoice
- **Duplicate** — same invoice paid twice
- **Vague** — weak reference but counterparty + amount match

## Demo company

**Werkstein Industrietechnik GmbH** — a fictional German industrial packaging company with:
- 50 bank transactions (30 credits, 20 debits) across two bank accounts
- 50 invoices (35 AR, 15 AP) with 12 deliberately designed reconciliation cases

## Results

| Metric | Value |
|--------|-------|
| Matches found | 36 / 50 bank transactions |
| Invoice coverage | 88% |
| Amount reconciled | EUR 153,000+ |
| Critical anomalies | 4 (2 duplicates, 2 ghost payments) |
| Match types | 7 distinct types detected |

## Setup

### Prerequisites

- Python 3.11+
- Anthropic API key

### Installation

```bash
git clone <repo-url>
cd agentic-financial-reconciliation

python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env with your Anthropic API key
```

### Build the knowledge graph (one-time, ~$0.50)

```bash
python build_graph.py
```

This ingests all 100 records into Cognee and builds the entity relationship graph. The graph is persisted in `./cognee_data/` and reused across pipeline runs.

### Run the pipeline

```bash
python run.py
```

The pipeline runs three agents sequentially:
1. **Matching agent** queries Cognee for all 50 bank transactions (~$0.15)
2. **Anomaly agent** detects and investigates anomalies (~$0.05)
3. **Reporting agent** generates the reconciliation report (~$0.02)

Total cost per run: **~$0.25** (using Claude Haiku)

Output is saved to `reconciliation_report.txt`.

## Project structure

```
├── run.py                  # Pipeline entry point
├── build_graph.py          # One-time knowledge graph builder
├── requirements.txt
├── .env.example
├── agents/
│   ├── __init__.py
│   ├── cognee_setup.py     # Cognee storage and LLM configuration
│   ├── pipeline.py         # LangGraph pipeline (3 agents)
│   ├── prompts.py          # Agent system prompts
│   ├── state.py            # Pipeline state dataclasses
│   └── tools.py            # Data loading and anomaly detection utilities
└── data/
    ├── bank_transactions.csv
    ├── invoices.csv
    └── DATASET_DESIGN.md   # Documentation of all 12 reconciliation cases
```

## Tech stack

- **[Cognee](https://github.com/topoteretes/cognee)** v1.1.2 — Knowledge graph memory for AI agents
- **[LangGraph](https://github.com/langchain-ai/langgraph)** — Agent orchestration
- **[Claude Haiku](https://docs.anthropic.com/en/docs/about-claude/models)** — LLM for agent reasoning
- **[Fastembed](https://github.com/qdrant/fastembed)** — Local embeddings (no API key needed)

## License

MIT
