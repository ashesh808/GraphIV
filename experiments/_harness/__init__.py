"""Shared evaluation harness for the experiments (ported from the pre-rewrite kg_rag_lab).

Each experiment imports from here so the measurement instruments — the metric vector, the
LLM-as-judge, the faithfulness tripwire, the gold topics, and the plot helper — are identical
across experiments. Nothing here imports from `.legacy`; the logic was re-homed.
"""
