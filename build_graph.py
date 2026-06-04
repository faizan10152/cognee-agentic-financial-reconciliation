"""Build the Cognee knowledge graph from bank transactions and invoices.

One-time setup step. The graph is persisted in ./cognee_data/ and reused
across pipeline runs. Costs ~$0.50 in Anthropic API calls.

Usage:
    python build_graph.py           # Build (skips if graph exists)
    python build_graph.py --force   # Rebuild from scratch
"""
import asyncio
import sys
from pathlib import Path

import pandas as pd

from agents.cognee_setup import configure_cognee

configure_cognee()

DATA_DIR = Path(__file__).parent / "data"


def _bank_to_text(row: dict) -> str:
    direction = "received from" if row["credit_debit"] == "CREDIT" else "paid to"
    return (
        f"Bank transaction {row['id']}: {row['amount']} {row['currency']} "
        f"{direction} {row.get('counterparty_name', 'Unknown')} on {row['booking_date']}. "
        f"IBAN: {row.get('counterparty_iban', 'N/A')}. "
        f"Payment reference: {row.get('payment_reference', 'N/A')}. "
        f"Bank account: {row['account_id']}."
    )


def _invoice_to_text(row: dict) -> str:
    inv_type = "Accounts Receivable" if row["invoice_type"] == "ar" else "Accounts Payable"
    return (
        f"Invoice {row['invoice_id']} ({row['invoice_external_reference']}): {inv_type}. "
        f"Counterparty: {row['counterparty_name']} (ID: {row['counterparty_id']}). "
        f"Amount: {row['invoice_amount_gross']} {row['invoice_currency']}. "
        f"Issued: {row['invoice_date']}, due: {row['invoice_due_date']}. "
        f"Status: {row['item_status']}. "
        f"ERP paid: {row['erp_amount_paid']} on {row.get('erp_payment_date', 'N/A')}."
    )


async def main():
    import cognee

    force = "--force" in sys.argv

    # Check for existing graph
    if not force:
        try:
            results = await cognee.search("Bergmann Verpackungen", top_k=1)
            if results and "Bergmann" in str(results[0]):
                print("Knowledge graph already exists. Use --force to rebuild.")
                return
        except Exception:
            pass

    if force:
        print("Pruning existing data...")
        await cognee.prune.prune_data()
        await cognee.prune.prune_system(metadata=True)

    # Load data
    bank_df = pd.read_csv(DATA_DIR / "bank_transactions.csv")
    invoice_df = pd.read_csv(DATA_DIR / "invoices.csv")
    print(f"Loaded {len(bank_df)} bank transactions, {len(invoice_df)} invoices")

    texts = (
        [_bank_to_text(row) for _, row in bank_df.iterrows()]
        + [_invoice_to_text(row) for _, row in invoice_df.iterrows()]
    )

    # Ingest in small batches (avoids max_tokens errors during entity extraction)
    batch_size = 5
    total = (len(texts) + batch_size - 1) // batch_size
    for i in range(0, len(texts), batch_size):
        batch = "\n\n".join(texts[i : i + batch_size])
        await cognee.add(batch, dataset_name="reconciliation_data")
        print(f"  Ingested batch {i // batch_size + 1}/{total}")

    print(f"Building knowledge graph ({len(texts)} records)...")
    await cognee.cognify()

    # Verify
    results = await cognee.search("Bergmann", top_k=1)
    if results:
        print(f"\nKnowledge graph built and verified.")
        print("Stored in ./cognee_data/ — persists across pipeline runs.")
    else:
        print("\nWARNING: Graph built but verification search returned empty.")


if __name__ == "__main__":
    asyncio.run(main())
