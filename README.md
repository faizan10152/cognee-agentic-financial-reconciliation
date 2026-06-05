# Agentic Financial Reconciliation

> **[Read the full use case report (PDF)](./Cognee-finance-use-case.pdf)** — a detailed walkthrough of how Cognee's knowledge graph solves financial reconciliation, including architecture, results, and lessons learned.

An AI-powered financial reconciliation system that uses **Cognee** as a shared knowledge graph memory layer for LLM agents orchestrated by **LangGraph**.

The system ingests bank transactions and invoices into a Cognee knowledge graph, then deploys three LLM agents that query the graph to match transactions, detect anomalies, and generate reports.

## The problem: why financial reconciliation needs knowledge graphs

Financial reconciliation is fundamentally a **cross-source entity resolution** problem. Bank statements and ERP invoices describe the same real-world events — payments — but through different lenses, with different naming conventions, different granularity, and frequent inconsistencies.

### Why traditional approaches fall short

**Relational databases** require predefined schemas and manual join conditions. But financial data is messy — counterparty names differ between systems (*"Müller Display GmbH + Co. KG"* vs *"Mueller Display GmbH & Co. KG"*), payment references follow no universal standard, and a single bank transaction can map to multiple invoices (batch payments), a fraction of an invoice (partial payments), or no invoice at all (operational expenses). Every edge case needs a new rule, a new column, a new join — and the system becomes brittle and expensive to maintain.

**Semantic search / vector embeddings** can find similar text, but similarity alone doesn't constitute a match. A bank transaction for €3,724 and an invoice for €3,800 are 98% similar in embedding space, but the €76 difference is a deliberate 2% early payment discount (Skonto) — something that requires understanding the *relationship* between the amounts, not just their proximity. Embeddings also can't represent structured facts like "BT-004 and BT-026 both reference RE-2026-0004, meaning the same invoice was paid twice."

### Why knowledge graphs solve this

Financial reconciliation requires **structured relationships across heterogeneous data sources** — the ability to traverse from a bank IBAN to a counterparty, to their invoices, to payment references, to other transactions from the same entity. A knowledge graph naturally represents these multi-hop relationships:

```
Bergmann Verpackungen GmbH
  ├── IBAN: DE72500105176412345678
  ├── Bank Transaction BT-001 (4,250 EUR, RE-2026-0001)
  ├── Bank Transaction BT-009 (6,860 EUR, RE-2026-0007, Skonto 140 EUR)
  ├── Invoice INV-001 (4,250 EUR, RE-2026-0001)
  ├── Invoice INV-007 (7,000 EUR, RE-2026-0007)
  └── Related entity: Bergmann Packaging Danmark A/S (subsidiary)
```

The graph preserves provenance and auditability — every match decision can be traced back through the exact entity relationships that justified it. This is critical in financial contexts where reconciliation results feed into regulatory reporting.

### What Cognee provides

Building and maintaining knowledge graphs from heterogeneous data sources — different formats, schemas, naming conventions — traditionally requires significant engineering effort: graph database setup, entity extraction pipelines, embedding infrastructure, query interfaces, and ongoing maintenance.

**Cognee reduces this to four commands:**

```python
await cognee.add(data)          # Ingest raw data
await cognee.cognify()          # Build knowledge graph (entity extraction + linking)
await cognee.search(query)      # Query with natural language
# + search_tool for LangGraph   # Agent-ready tool interface
```

Cognee handles entity extraction, relationship inference, embedding generation, graph storage, and natural language querying — letting the developer focus on the agent logic rather than the infrastructure.

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
