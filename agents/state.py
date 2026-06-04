"""Pipeline state dataclasses for the reconciliation workflow."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class MatchResult:
    """A reconciliation match between bank transaction(s) and invoice(s)."""

    match_id: str
    case_type: str  # perfect | skonto | batch | partial | cross_entity | vague | duplicate
    bank_tx_ids: list[str]
    invoice_ids: list[str]
    bank_amount: float
    invoice_amount: float
    difference: float = 0.0
    confidence: float = 1.0
    explanation: str = ""
    flags: list[str] = field(default_factory=list)


@dataclass
class Anomaly:
    """An anomaly discovered during reconciliation."""

    anomaly_id: str
    anomaly_type: str  # ghost_payment | no_invoice | duplicate_payment | late_payment | name_mismatch
    severity: Literal["info", "warning", "critical"]
    related_ids: list[str]
    description: str
    suggested_action: str = ""


@dataclass
class ReconciliationState:
    """Full pipeline state passed between agents via LangGraph."""

    run_id: str = ""

    # Raw data
    bank_transactions: list[dict] = field(default_factory=list)
    invoices: list[dict] = field(default_factory=list)

    # Cognee knowledge graph
    kg_ingested: bool = False
    kg_node_count: int = 0
    kg_edge_count: int = 0

    # Matching results
    matches: list[MatchResult] = field(default_factory=list)
    unmatched_bank_txs: list[str] = field(default_factory=list)
    unmatched_invoices: list[str] = field(default_factory=list)

    # Anomalies
    anomalies: list[Anomaly] = field(default_factory=list)

    # Report
    report: str = ""
    summary_stats: dict = field(default_factory=dict)

    # Tracking
    current_agent: str = ""
    errors: list[str] = field(default_factory=list)
    completed: bool = False
