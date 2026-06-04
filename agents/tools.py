"""Utility functions for data loading and anomaly detection.

Matching is handled entirely by the LLM agent querying Cognee's knowledge graph.
These utilities support data loading and post-match anomaly analysis.
"""
from __future__ import annotations

from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).parent.parent / "data"


def load_bank_transactions() -> list[dict]:
    """Load bank transactions from CSV."""
    return pd.read_csv(DATA_DIR / "bank_transactions.csv").to_dict("records")


def load_invoices() -> list[dict]:
    """Load invoices from CSV."""
    return pd.read_csv(DATA_DIR / "invoices.csv").to_dict("records")


def name_similarity(name1: str, name2: str) -> float:
    """Fuzzy match score between two company names (0.0–1.0)."""
    n1 = _normalize_name(name1)
    n2 = _normalize_name(name2)
    if n1 == n2:
        return 1.0
    return SequenceMatcher(None, n1, n2).ratio()


def find_duplicate_payments(matches: list[dict]) -> list[dict]:
    """Detect invoices that were paid more than once."""
    invoice_payments: dict[str, list[dict]] = {}
    for m in matches:
        inv_id = m.get("invoice_id", "")
        if inv_id:
            invoice_payments.setdefault(inv_id, []).append(m)

    return [
        {
            "invoice_id": inv_id,
            "payment_count": len(payments),
            "bank_tx_ids": [p["bank_tx_id"] for p in payments],
            "total_paid": sum(p["bank_amount"] for p in payments),
            "invoice_amount": payments[0]["invoice_amount"],
        }
        for inv_id, payments in invoice_payments.items()
        if len(payments) > 1
    ]


def find_ghost_payments(
    invoices: list[dict], matched_invoice_ids: set[str]
) -> list[dict]:
    """Find invoices marked as paid in ERP but with no matching bank transaction."""
    return [
        {
            "invoice_id": inv["invoice_id"],
            "invoice_ref": inv.get("invoice_external_reference", ""),
            "counterparty": inv.get("counterparty_name", ""),
            "invoice_amount": inv["invoice_amount_gross"],
            "erp_paid": inv.get("erp_amount_paid", 0),
            "erp_payment_date": inv.get("erp_payment_date", ""),
        }
        for inv in invoices
        if inv.get("erp_amount_paid", 0) > 0
        and inv["invoice_id"] not in matched_invoice_ids
    ]


def _normalize_name(name: str) -> str:
    """Normalize a company name for fuzzy comparison."""
    import re

    name = name.lower().strip()
    for old, new in [("ü", "u"), ("ö", "o"), ("ä", "a"), ("&", ""), ("+", "")]:
        name = name.replace(old, new)
    for suffix in ["gmbh", "ag", "co. kg", "co.kg", "sp. z o.o.", "a/s", "ab",
                    "b.v.", "e.k.", "s.a.", "gbr"]:
        name = name.replace(suffix, "")
    return re.sub(r"[^a-z0-9 ]", "", re.sub(r"\s+", " ", name)).strip()
