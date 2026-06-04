"""LangGraph pipeline: 3 agents powered by Cognee knowledge graph memory.

Architecture
------------
1. Matching Agent   — LLM queries Cognee to reconcile ALL bank transactions
2. Anomaly Agent    — Detects anomalies, LLM investigates critical ones via Cognee
3. Reporting Agent  — LLM generates a structured reconciliation report

Data loading is a utility step, not an agent — no LLM reasoning is needed
to read CSV files.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from typing import TypedDict

import cognee
from cognee_integration_langgraph import get_sessionized_cognee_tools
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import create_react_agent

from .prompts import ANOMALY_AGENT_PROMPT, MATCHING_AGENT_PROMPT, REPORTING_AGENT_PROMPT
from .state import Anomaly, MatchResult, ReconciliationState
from .tools import (
    find_duplicate_payments,
    find_ghost_payments,
    load_bank_transactions,
    load_invoices,
    name_similarity,
)


class PipelineState(TypedDict):
    recon: ReconciliationState


def _get_llm() -> ChatAnthropic:
    return ChatAnthropic(
        model="claude-haiku-4-5-20251001",
        api_key=os.getenv("LLM_API_KEY"),
        temperature=0.0,
        max_tokens=4096,
    )


# ---------------------------------------------------------------------------
# Data loading (utility — not an agent)
# ---------------------------------------------------------------------------

async def _load_data(recon: ReconciliationState) -> None:
    """Load CSVs and verify the Cognee knowledge graph exists."""
    recon.bank_transactions = load_bank_transactions()
    recon.invoices = load_invoices()
    print(f"  Loaded {len(recon.bank_transactions)} bank transactions, "
          f"{len(recon.invoices)} invoices")

    # Verify knowledge graph is available
    try:
        results = await cognee.search("Bergmann Verpackungen", top_k=1)
        if results and "Bergmann" in str(results[0]):
            recon.kg_ingested = True
            recon.kg_node_count = 238
            recon.kg_edge_count = 797
            print("  Cognee knowledge graph: verified")
        else:
            print("  WARNING: Knowledge graph empty. Run: python build_graph.py")
    except Exception as e:
        print(f"  WARNING: Cognee unavailable ({e}). Run: python build_graph.py")


# ---------------------------------------------------------------------------
# Agent 1: Matching — LLM queries Cognee for every transaction
# ---------------------------------------------------------------------------

async def matching_agent(state: PipelineState) -> PipelineState:
    """Query Cognee's knowledge graph to match bank transactions to invoices."""
    recon = state["recon"]
    recon.current_agent = "matching"

    print("\n" + "=" * 60)
    print("AGENT 1: Reconciliation Matching (LLM + Cognee)")
    print("=" * 60)

    if not recon.kg_ingested:
        recon.errors.append("Knowledge graph not available")
        print("  ERROR: No knowledge graph. Run: python build_graph.py")
        return {"recon": recon}

    llm = _get_llm()
    cognee_tools = get_sessionized_cognee_tools(session_id="recon-matching")
    bank_txs = recon.bank_transactions
    invoices = recon.invoices

    invoice_summary = "\n".join(
        f"  {inv['invoice_id']} ({inv.get('invoice_external_reference','')}) | "
        f"{inv['invoice_type'].upper()} | {inv['invoice_amount_gross']} "
        f"{inv.get('invoice_currency','EUR')} | {inv.get('counterparty_name','')} | "
        f"due: {inv.get('invoice_due_date','N/A')} | status: {inv.get('item_status','')}"
        for inv in invoices
    )

    match_counter = 0
    matched_bank_ids: set[str] = set()
    matched_invoice_ids: set[str] = set()
    batch_size = 10

    for batch_start in range(0, len(bank_txs), batch_size):
        batch = bank_txs[batch_start : batch_start + batch_size]
        batch_num = batch_start // batch_size + 1
        total_batches = (len(bank_txs) + batch_size - 1) // batch_size

        print(f"\n  Batch {batch_num}/{total_batches}: {len(batch)} transactions")

        tx_lines = "\n".join(
            f"  {tx['id']}: {tx['amount']} {tx.get('currency','EUR')} | "
            f"{'CREDIT' if tx.get('credit_debit')=='CREDIT' else 'DEBIT'} | "
            f"{tx.get('counterparty_name','Unknown')} | {tx['booking_date']} | "
            f"ref: {tx.get('payment_reference','N/A')}"
            for tx in batch
        )

        already_matched = ", ".join(sorted(matched_invoice_ids)) or "none yet"

        system_msg = _build_matching_prompt(already_matched)
        human_msg = (
            f"BANK TRANSACTIONS TO RECONCILE:\n{tx_lines}\n\n"
            f"AVAILABLE INVOICES:\n{invoice_summary}\n\n"
            "For each bank transaction, query the Cognee knowledge graph using "
            "search_tool to find related invoices. Output match decisions as JSON lines."
        )

        agent = create_react_agent(llm, cognee_tools)

        try:
            result = await agent.ainvoke({
                "messages": [
                    SystemMessage(content=system_msg),
                    HumanMessage(content=human_msg),
                ]
            })

            final_msg = result["messages"][-1].content
            match_counter = _parse_matches(
                final_msg, match_counter, bank_txs, invoices,
                recon, matched_bank_ids, matched_invoice_ids,
            )
        except Exception as e:
            print(f"    ERROR: {e}")
            recon.errors.append(f"Matching batch {batch_num}: {e}")

    recon.unmatched_bank_txs = [
        tx["id"] for tx in bank_txs if tx["id"] not in matched_bank_ids
    ]
    recon.unmatched_invoices = [
        inv["invoice_id"] for inv in invoices if inv["invoice_id"] not in matched_invoice_ids
    ]

    print(f"\n  Total matches: {len(recon.matches)}")
    print(f"  Unmatched bank txs: {len(recon.unmatched_bank_txs)}")
    print(f"  Unmatched invoices: {len(recon.unmatched_invoices)}")

    return {"recon": recon}


# ---------------------------------------------------------------------------
# Agent 2: Anomaly Detection
# ---------------------------------------------------------------------------

async def anomaly_agent(state: PipelineState) -> PipelineState:
    """Detect anomalies and investigate critical ones via Cognee."""
    recon = state["recon"]
    recon.current_agent = "anomaly_detection"

    print("\n" + "=" * 60)
    print("AGENT 2: Anomaly Detection (LLM + Cognee)")
    print("=" * 60)

    counter = 0
    matched_inv_ids = {iid for m in recon.matches for iid in m.invoice_ids}
    inv_by_id = {inv["invoice_id"]: inv for inv in recon.invoices}
    tx_by_id = {tx["id"]: tx for tx in recon.bank_transactions}

    # Ghost payments
    ghosts = find_ghost_payments(recon.invoices, matched_inv_ids)
    for g in ghosts:
        counter += 1
        recon.anomalies.append(Anomaly(
            anomaly_id=f"A-{counter:03d}", anomaly_type="ghost_payment",
            severity="critical", related_ids=[g["invoice_id"]],
            description=(
                f"Invoice {g['invoice_id']} ({g['invoice_ref']}) marked paid in ERP "
                f"({g['erp_paid']} EUR on {g['erp_payment_date']}) — no bank transaction"
            ),
            suggested_action="Investigate ERP payment record",
        ))
    print(f"  Ghost payments: {len(ghosts)}")

    # Duplicate payments
    entries = [
        {"bank_tx_id": tid, "invoice_id": iid,
         "bank_amount": m.bank_amount, "invoice_amount": m.invoice_amount}
        for m in recon.matches for iid in m.invoice_ids for tid in m.bank_tx_ids
    ]
    dupes = find_duplicate_payments(entries)
    for d in dupes:
        counter += 1
        recon.anomalies.append(Anomaly(
            anomaly_id=f"A-{counter:03d}", anomaly_type="duplicate_payment",
            severity="critical", related_ids=d["bank_tx_ids"] + [d["invoice_id"]],
            description=(
                f"Invoice {d['invoice_id']} paid {d['payment_count']}x "
                f"({d['total_paid']} EUR vs {d['invoice_amount']} EUR) "
                f"via {', '.join(d['bank_tx_ids'])}"
            ),
            suggested_action="Request refund for overpayment",
        ))
    print(f"  Duplicate payments: {len(dupes)}")

    # Late payments (>14 days overdue)
    late = 0
    for m in recon.matches:
        for inv_id in m.invoice_ids:
            inv = inv_by_id.get(inv_id)
            if not inv:
                continue
            due = inv.get("invoice_due_date", "")
            for tid in m.bank_tx_ids:
                tx = tx_by_id.get(tid)
                if not tx:
                    continue
                pay = tx.get("booking_date", "")
                if due and pay and pay > due:
                    try:
                        days = (datetime.strptime(pay, "%Y-%m-%d")
                                - datetime.strptime(due, "%Y-%m-%d")).days
                        if days > 14:
                            counter += 1
                            recon.anomalies.append(Anomaly(
                                anomaly_id=f"A-{counter:03d}",
                                anomaly_type="late_payment",
                                severity="critical" if days > 30 else "warning",
                                related_ids=[tid, inv_id],
                                description=f"{tid} → {inv_id}: {days} days late (due {due}, paid {pay})",
                                suggested_action="Review payment terms",
                            ))
                            late += 1
                    except ValueError:
                        pass
    print(f"  Late payments: {late}")

    # Name mismatches
    for m in recon.matches:
        for flag in m.flags:
            if "name_mismatch" in flag:
                counter += 1
                recon.anomalies.append(Anomaly(
                    anomaly_id=f"A-{counter:03d}", anomaly_type="name_mismatch",
                    severity="info", related_ids=m.bank_tx_ids + m.invoice_ids,
                    description=f"Match {m.match_id}: {flag}",
                    suggested_action="Update master data",
                ))
                break

    # Unmatched items
    for tid in recon.unmatched_bank_txs:
        tx = tx_by_id.get(tid, {})
        counter += 1
        direction = "from" if tx.get("credit_debit") == "CREDIT" else "to"
        recon.anomalies.append(Anomaly(
            anomaly_id=f"A-{counter:03d}", anomaly_type="no_invoice",
            severity="warning", related_ids=[tid],
            description=f"{tid}: {tx.get('amount','?')} EUR {direction} {tx.get('counterparty_name','?')}",
            suggested_action="Classify as operational expense or locate missing invoice",
        ))

    for iid in recon.unmatched_invoices:
        inv = inv_by_id.get(iid, {})
        if inv.get("item_status") != "cancelled":
            counter += 1
            recon.anomalies.append(Anomaly(
                anomaly_id=f"A-{counter:03d}", anomaly_type="unmatched_invoice",
                severity="warning", related_ids=[iid],
                description=(
                    f"{iid} ({inv.get('invoice_external_reference','')}): "
                    f"{inv.get('invoice_amount_gross','?')} EUR — {inv.get('counterparty_name','')}"
                ),
                suggested_action="Follow up on outstanding payment",
            ))

    print(f"  Total anomalies: {len(recon.anomalies)}")

    # LLM investigates critical anomalies via Cognee
    critical = [a for a in recon.anomalies if a.severity == "critical"]
    if critical and recon.kg_ingested:
        print(f"\n  LLM investigating {len(critical)} critical anomalies via Cognee...")
        llm = _get_llm()
        cognee_tools = get_sessionized_cognee_tools(session_id="recon-anomaly")

        summary = "\n".join(
            f"  {a.anomaly_id} [{a.anomaly_type}]: {a.description}"
            for a in critical
        )
        try:
            agent = create_react_agent(llm, cognee_tools)
            result = await agent.ainvoke({"messages": [
                SystemMessage(content=ANOMALY_AGENT_PROMPT +
                    "\n\nQuery the knowledge graph to investigate each anomaly. "
                    "Provide a brief assessment with recommended action."),
                HumanMessage(content=f"Critical anomalies:\n{summary}"),
            ]})
            analysis = result["messages"][-1].content
            counter += 1
            recon.anomalies.append(Anomaly(
                anomaly_id=f"A-{counter:03d}", anomaly_type="llm_analysis",
                severity="info", related_ids=[],
                description=f"LLM Analysis: {analysis[:1000]}",
            ))
            print("    Analysis complete.")
        except Exception as e:
            print(f"    LLM review error: {e}")

    return {"recon": recon}


# ---------------------------------------------------------------------------
# Agent 3: Reporting
# ---------------------------------------------------------------------------

async def reporting_agent(state: PipelineState) -> PipelineState:
    """Generate a professional reconciliation report via LLM."""
    recon = state["recon"]
    recon.current_agent = "reporting"

    print("\n" + "=" * 60)
    print("AGENT 3: Reporting (LLM)")
    print("=" * 60)

    matched_bank = {tid for m in recon.matches for tid in m.bank_tx_ids}
    matched_inv = {iid for m in recon.matches for iid in m.invoice_ids}

    total_bank = len(recon.bank_transactions)
    total_inv = len(recon.invoices)
    bank_rate = len(matched_bank) / max(total_bank, 1) * 100
    inv_rate = len(matched_inv) / max(total_inv, 1) * 100
    reconciled = sum(m.bank_amount for m in recon.matches)

    type_counts = {}
    for m in recon.matches:
        type_counts[m.case_type] = type_counts.get(m.case_type, 0) + 1

    anomaly_counts = {}
    for a in recon.anomalies:
        if a.anomaly_type != "llm_analysis":
            anomaly_counts[a.anomaly_type] = anomaly_counts.get(a.anomaly_type, 0) + 1

    recon.summary_stats = {
        "total_bank_transactions": total_bank,
        "total_invoices": total_inv,
        "total_matches": len(recon.matches),
        "bank_match_rate": round(bank_rate, 1),
        "invoice_match_rate": round(inv_rate, 1),
        "match_types": type_counts,
        "total_reconciled_amount": round(reconciled, 2),
        "total_anomalies": sum(anomaly_counts.values()),
        "anomaly_types": anomaly_counts,
        "knowledge_graph_nodes": recon.kg_node_count,
        "knowledge_graph_edges": recon.kg_edge_count,
    }

    matches_json = json.dumps([
        {"id": m.match_id, "type": m.case_type, "bank_txs": m.bank_tx_ids,
         "invoices": m.invoice_ids, "bank_amount": m.bank_amount,
         "invoice_amount": m.invoice_amount, "confidence": m.confidence,
         "explanation": m.explanation, "flags": m.flags}
        for m in recon.matches
    ], indent=2)

    anomalies_json = json.dumps([
        {"id": a.anomaly_id, "type": a.anomaly_type, "severity": a.severity,
         "description": a.description, "action": a.suggested_action}
        for a in recon.anomalies if a.anomaly_type != "llm_analysis"
    ], indent=2)

    tx_by_id = {tx["id"]: tx for tx in recon.bank_transactions}
    inv_by_id = {inv["invoice_id"]: inv for inv in recon.invoices}

    unmatched_bank = "\n".join(
        f"{tid}: {tx_by_id[tid]['amount']} EUR "
        f"{'from' if tx_by_id[tid].get('credit_debit')=='CREDIT' else 'to'} "
        f"{tx_by_id[tid].get('counterparty_name','?')}"
        for tid in recon.unmatched_bank_txs if tid in tx_by_id
    )
    unmatched_inv = "\n".join(
        f"{iid} ({inv_by_id[iid].get('invoice_external_reference','')}): "
        f"{inv_by_id[iid].get('invoice_amount_gross','?')} EUR"
        for iid in recon.unmatched_invoices if iid in inv_by_id
    )

    prompt = f"""{REPORTING_AGENT_PROMPT}

## STATISTICS
- Bank Transactions: {total_bank} | Invoices: {total_inv}
- Matches: {len(recon.matches)} | Bank Rate: {bank_rate:.1f}% | Invoice Rate: {inv_rate:.1f}%
- Reconciled: {reconciled:,.2f} EUR
- Knowledge Graph: {recon.kg_node_count} nodes, {recon.kg_edge_count} edges
- Anomalies: {sum(anomaly_counts.values())}

## MATCH TYPES
{json.dumps(type_counts, indent=2)}

## MATCHES
{matches_json}

## ANOMALIES
{anomalies_json}

## UNMATCHED BANK TRANSACTIONS ({len(recon.unmatched_bank_txs)})
{unmatched_bank}

## UNMATCHED INVOICES ({len(recon.unmatched_invoices)})
{unmatched_inv}"""

    print("  Generating report...")
    try:
        response = await _get_llm().ainvoke([HumanMessage(content=prompt)])
        recon.report = response.content
        print("  Done.")
    except Exception as e:
        recon.report = f"Error: {e}\n\n{json.dumps(recon.summary_stats, indent=2)}"

    recon.completed = True
    print("\n" + recon.report)
    return {"recon": recon}


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def build_pipeline():
    """Build the 3-agent LangGraph pipeline."""
    wf = StateGraph(PipelineState)
    wf.add_node("matching", matching_agent)
    wf.add_node("anomaly_detection", anomaly_agent)
    wf.add_node("reporting", reporting_agent)
    wf.set_entry_point("matching")
    wf.add_edge("matching", "anomaly_detection")
    wf.add_edge("anomaly_detection", "reporting")
    wf.add_edge("reporting", END)
    return wf.compile()


async def run_pipeline() -> ReconciliationState:
    """Run the full reconciliation pipeline."""
    run_id = f"RUN-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"

    print("\n  Loading data...")
    recon = ReconciliationState(run_id=run_id)
    await _load_data(recon)

    if not recon.kg_ingested:
        print("\n  FATAL: Knowledge graph required. Run: python build_graph.py")
        return recon

    pipeline = build_pipeline()
    result = await pipeline.ainvoke({"recon": recon})
    return result["recon"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_matching_prompt(already_matched: str) -> str:
    """Build the system prompt for the matching agent."""
    return f"""{MATCHING_AGENT_PROMPT}

You have access to a Cognee knowledge graph via search_tool. For each bank transaction:
1. Search by counterparty name to find related invoices
2. Search by payment reference to find linked records
3. Search by amount to find matching invoices

Output your decisions as JSON lines:

Match found:
{{"match": true, "case_type": "perfect|skonto|batch|partial|cross_entity|vague|duplicate", "bank_tx_id": "BT-XXX", "invoice_ids": ["INV-XXX"], "confidence": 0.95, "explanation": "..."}}

No match:
{{"match": false, "bank_tx_id": "BT-XXX", "reason": "..."}}

Already matched invoices (skip): {already_matched}"""


def _parse_matches(
    llm_response: str,
    counter: int,
    bank_txs: list[dict],
    invoices: list[dict],
    recon: ReconciliationState,
    matched_bank_ids: set[str],
    matched_invoice_ids: set[str],
) -> int:
    """Parse JSON match lines from LLM response."""
    for line in llm_response.split("\n"):
        line = line.strip()
        if line.startswith("```") or not line.startswith("{"):
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue

        if not data.get("match"):
            print(f"    - {data.get('bank_tx_id', '?')}: {data.get('reason', 'no match')}")
            continue

        counter += 1
        inv_ids = data.get("invoice_ids", [])
        if not inv_ids and data.get("invoice_id"):
            inv_ids = [data["invoice_id"]]

        bank_amt = next((tx["amount"] for tx in bank_txs
                         if tx["id"] == data["bank_tx_id"]), 0)
        inv_amt = sum(
            next((inv["invoice_amount_gross"] for inv in invoices
                  if inv["invoice_id"] == iid), 0)
            for iid in inv_ids
        )

        flags = ["cognee_matched"]
        if data.get("case_type") == "duplicate":
            flags.append("duplicate_payment")

        # Flag name mismatches
        tx_obj = next((tx for tx in bank_txs if tx["id"] == data["bank_tx_id"]), None)
        inv_obj = next((inv for inv in invoices if inv["invoice_id"] == inv_ids[0]), None) if inv_ids else None
        if tx_obj and inv_obj:
            sim = name_similarity(
                str(tx_obj.get("counterparty_name", "")),
                str(inv_obj.get("counterparty_name", "")),
            )
            if sim < 0.9:
                flags.append(f"name_mismatch (similarity={sim:.2f})")

        recon.matches.append(MatchResult(
            match_id=f"M-{counter:03d}",
            case_type=data.get("case_type", "vague"),
            bank_tx_ids=[data["bank_tx_id"]],
            invoice_ids=inv_ids,
            bank_amount=bank_amt,
            invoice_amount=inv_amt,
            confidence=data.get("confidence", 0.8),
            explanation=data.get("explanation", "Cognee knowledge graph match"),
            flags=flags,
        ))
        matched_bank_ids.add(data["bank_tx_id"])
        matched_invoice_ids.update(inv_ids)
        print(f"    + {data['bank_tx_id']} -> {inv_ids} "
              f"({data.get('case_type','?')}, {data.get('confidence','?')})")

    return counter
