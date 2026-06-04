"""Entry point for the agentic financial reconciliation pipeline.

Usage:
    python run.py              # Full pipeline (requires Cognee knowledge graph)
    python build_graph.py      # Build the knowledge graph first (one-time)
"""
import asyncio

from agents.cognee_setup import configure_cognee

configure_cognee()


async def main():
    from agents.pipeline import run_pipeline

    print("=" * 60)
    print("  Agentic Financial Reconciliation")
    print("  Powered by Cognee + LangGraph")
    print("=" * 60)

    recon = await run_pipeline()

    if recon.report:
        with open("reconciliation_report.txt", "w") as f:
            f.write(recon.report)
        print("\nReport saved to reconciliation_report.txt")

    stats = recon.summary_stats
    if stats:
        print(f"\nResults: {stats.get('total_matches', 0)} matches | "
              f"Bank: {stats.get('bank_match_rate', 0)}% | "
              f"Invoice: {stats.get('invoice_match_rate', 0)}% | "
              f"Anomalies: {stats.get('total_anomalies', 0)}")


if __name__ == "__main__":
    asyncio.run(main())
