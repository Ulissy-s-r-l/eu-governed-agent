"""Causal graph — attributed (not discovered) edges (doc 02 §3.7, doc 05).

ATTRIBUTED, NOT DISCOVERED. An edge records the attribution the *evaluator already
produced* (`experience.evaluation.attribution`, doc 03 §2.2; doc 05 §3). There is NO
causal inference from observational data here — the graph does not learn structure,
it transcribes claims that came with a source.

WHAT THIS EMITTER PRODUCES TODAY — stage 1 (local) ONLY. Doc 05 §3 defines four
attribution stages; today only `SimulatorGroundTruthEvaluator` emits a usable
attribution, and only a *local* one (`attribution.load_bearing` → the action step).
So every edge this module mints carries `attribution_stage == "local"`. A graph of
exclusively local edges reflects the EMITTER'S LIMIT (stage 1 is all any evaluator
emits), NOT a property of the domain — when an evaluator emits stage 2–4 attributions
(see `STAGE_*` below) they light up without a schema change.

BORN-FALSIFIABLE. Every edge carries a `counterfactual_pattern` (doc 05 §2.3) — the
bias/anomaly the edge claims are linked. It is stored with NO consumer until the
counterfactuals item (the replay that holds the bias constant and checks the anomaly
fails to recur — doc 05 §4/§6). **Do not prune it as unused: an edge born falsifiable
differs from one retrofitted with a test hook later** — the falsifiability is a fact
about how the edge was minted, not a feature bolted on.

attributed_by IS DERIVED, NEVER SUPPLIED (doc 07 C-plus decision). `causal_edge` takes
`(experience, tx)` and derives `attributed_by` from the cited experience's SIGNED
evaluation channel — a caller-supplied `attributed_by` is *structurally
unrepresentable* (no parameter accepts one), so an agent-trace source cannot be
labelled `evaluator` at edge-creation time. The claim is still only as trustworthy as
the experience's channel label, which is self-reported-but-signed (the D1
experience-poisoning shape); an edge whose source channel has no committed calibration
is flagged `uncalibrated` and a consumer MUST NOT read it as calibrated (doc 02 §3.8 /
doc 07 §2.2a — reference-relative treatment is the deferred remedy).
"""
from __future__ import annotations

from typing import Optional

from .experience import Experience, content_hash

# doc 05 §3 attribution stages. Only STAGE_LOCAL is emitted today; the rest are named
# so the schema visibly anticipates them (see module docstring).
STAGE_LOCAL = "local"                       # anomaly originates at the action step itself
STAGE_PLANNING_CONTROL = "planning-control"  # control-flow failure (loop structure)
STAGE_DATA_FLOW = "data-flow"               # upstream data corruption propagated
STAGE_DEVIATION_AWARE = "deviation-aware"   # reversible / self-corrected → discounted

STAGE_LOCAL_RELIABILITY = 0.9               # §3: local is "cheapest and most confident"
UNCALIBRATED_PRIOR = 0.3                    # confidence for an edge from an uncalibrated channel


def _source_type(channel: str) -> str:
    """doc 02 §3.7 `attributed_by` ∈ {evaluator|agent-trace|human}, DERIVED from the
    channel that produced the attribution. The agent's own self-report is agent-trace;
    it cannot be dressed as an evaluator here."""
    if channel == "agent-self-report":
        return "agent-trace"
    if channel.startswith("human"):
        return f"human:{channel}"
    return f"evaluator:{channel}"


def _outcome_node(exp_id: str) -> dict:
    return {"id": f"cg:outcome:{exp_id}", "type": "outcome", "ref": exp_id}


def _cause_node(exp_id: str) -> dict:
    return {"id": f"cg:cause:{exp_id}", "type": "cause", "ref": exp_id}


def causal_edge(experience: Experience, tx) -> Optional[dict]:
    """Mint the `attributed-to` edge for one experience's LOCAL attribution, or None
    if it carries no local attribution. Derives everything from `(experience, tx)`;
    there is deliberately NO `attributed_by` parameter.

    I4-FOR-CAUSES: an edge cannot exist without a source and a committing tx. If the
    experience has a load-bearing attribution but no evaluation channel to derive
    `attributed_by` from, or the tx has no id, this raises — an unprovenanced causal
    edge is never produced."""
    ev = experience.evaluation
    if ev is None:
        return None
    load_bearing = (ev.attribution or {}).get("load_bearing") or []
    if not load_bearing:
        return None                                  # no local attribution → no edge
    if not ev.channels:
        raise ValueError("causal edge: attribution present but no evaluation channel "
                         "to derive attributed_by from (violates I4-for-causes)")
    if not getattr(tx, "tx_id", None):
        raise ValueError("causal edge: no committing tx (violates I4-for-causes)")

    exp_id = experience.exp_id
    step = load_bearing[0]
    tool = experience.action.steps[-1].tool if experience.action.steps else "?"
    pattern = {                                      # born-falsifiable (doc 05 §2.3)
        "bias": f"{step} ({tool}) executed",
        "anomaly": f"outcome '{experience.outcome.observed}' verdict={ev.verdict}",
    }
    body = {"rel": "attributed-to", "from": f"cg:outcome:{exp_id}",
            "to": f"cg:cause:{exp_id}", "created_tx": tx.tx_id}
    return {
        "edge_id": "cg-edge:" + content_hash(body).split(":", 1)[1],
        "rel": "attributed-to",
        "from": f"cg:outcome:{exp_id}",
        "to": f"cg:cause:{exp_id}",
        "confidence": UNCALIBRATED_PRIOR,            # set precisely at insertion
        "attributed_by": _source_type(ev.channels[0]),
        "attribution_stage": STAGE_LOCAL,
        "counterfactual_pattern": pattern,
        "uncalibrated": True,                        # set precisely at insertion
        "created_tx": tx.tx_id,
        "created_at": tx.created_at,
    }


def insert_edges(state, experiences, tx) -> list[dict]:
    """Insert the attributed edges for `experiences` into `state.causal_graph`
    (mutating it), pricing each edge by the COMMITTED calibration of its source
    channel (doc 02 §3.8): a channel with a committed reliability yields a calibrated
    edge; one without is flagged `uncalibrated` and kept at a low prior. Returns the
    inserted edge records (for `tx.causal` and the durable-tier mirror)."""
    channels = (state.evaluation_history or {}).get("channels", {})
    nodes = state.causal_graph["nodes"]
    edges = state.causal_graph["edges"]
    node_ids = {n["id"] for n in nodes}
    edge_ids = {e["edge_id"] for e in edges}
    inserted: list[dict] = []
    for exp in experiences:
        edge = causal_edge(exp, tx)
        if edge is None or edge["edge_id"] in edge_ids:
            continue
        # price by committed calibration of the derived source channel
        src = exp.evaluation.channels[0]
        rel = (channels.get(src) or {}).get("reliability")
        if rel is not None:
            edge["uncalibrated"] = False
            edge["confidence"] = round(STAGE_LOCAL_RELIABILITY * rel, 4)
        for node in (_outcome_node(exp.exp_id), _cause_node(exp.exp_id)):
            if node["id"] not in node_ids:
                nodes.append(node)
                node_ids.add(node["id"])
        edges.append(edge)
        edge_ids.add(edge["edge_id"])
        inserted.append(edge)
    return inserted


def why_believed(causal_graph: dict, outcome_exp_id: str) -> list[dict]:
    """Q3 (doc 05 §5): the attributed-cause chain for an outcome — the "why did the
    agent do that?" walk. Returns the edges from this outcome, each carrying its
    `attributed_by` and `counterfactual_pattern` so the explanation is inspectable,
    not asserted. Closes doc 03 §6's `causal_basis → cg-edge` hop. (Confidence
    propagation and multi-hop chains are the counterfactuals item.)"""
    src = f"cg:outcome:{outcome_exp_id}"
    return [e for e in causal_graph.get("edges", []) if e["from"] == src]
