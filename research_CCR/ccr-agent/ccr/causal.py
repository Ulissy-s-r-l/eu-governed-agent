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
        "status": "active",                          # active | deprecated (doc 05 §6)
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


# ==========================================================================
# COUNTERFACTUALS — item 12, PR-A (mitigation only; NO admission change).
# The gate does not read any of this yet; it is the machinery PR-B will wire.
# ==========================================================================

REPLAY_EPISODE_OFFSET = 900_000            # deterministic sample range, disjoint from training
REPLAY_TAU = 0.5                            # anomaly-recurrence threshold: the cause must
#                                            reproduce the claimed verdict more often than not


def scope_for_edge(edge: dict) -> list[str]:
    """Minimal Q2 (doc 05 §5): the mechanistically-relevant experiences for one
    stage-1 edge — just its grounded (cited) experience. General subgraph-perturbation
    Q2 is open (multi-hop); PR-A's replay needs only this."""
    return [str(edge["from"]).split("cg:outcome:", 1)[-1]]


def replay_edge(edge: dict, experience, simulator, *,
                samples: int = 25, tau: float = REPLAY_TAU) -> dict:
    """Replay-against-`counterfactual_pattern` (doc 05 §2.3, §6) for a stage-1 local
    edge: hold the `bias` constant (re-run the cited step's tool in its region) and
    check whether the `anomaly` (the claimed verdict) recurs. The edge SURVIVES iff
    the claimed verdict recurs at rate >= tau; otherwise it FAILS — the attribution
    was spurious (doc 05 §3 stage-4, deviation-aware, made executable).

    This works because the simulator is a ground-truth REFERENCE (doc 07 §2.2a);
    in a reference-less domain the replay is unbuildable — the same limit as
    calibration. STATED CEILING (doc 07 laundering row): this tests the cause's
    PROPENSITY for the anomaly, not INSTANCE causation — in a multi-step trajectory a
    genuinely-bad step can survive while the specific failure came from upstream. The
    current single-step simulator cannot construct that case, so a surviving chain
    here is true; the ceiling is latent, closed only by stages 2-4 + data-flow Q2."""
    tool = experience.action.steps[-1].tool
    region = experience.action.policy_region
    claimed = str(edge["counterfactual_pattern"]["anomaly"]).split("verdict=", 1)[-1].strip()
    hits = 0
    for ep in range(REPLAY_EPISODE_OFFSET, REPLAY_EPISODE_OFFSET + samples):
        res = simulator.run_episode(tool, region, ep)
        verdict = "success" if res["success"] else "failure"
        if verdict == claimed:
            hits += 1
    recurrence = hits / samples
    return {"survives": recurrence >= tau, "anomaly_recurrence": round(recurrence, 4),
            "samples": samples, "tau": tau, "tool": tool, "region": region,
            "claimed_verdict": claimed}


def chain_confidence(edges: list[dict]) -> dict:
    """Chain confidence (doc 05 §4): `conf(chain) = ∏ conf(e) · ∏ reliability(n)`.

    Ledger-backed nodes have reliability 1.0; the `cause` node's channel reliability
    is ALREADY folded into `edge["confidence"]` at mint (`insert_edges`:
    stage_reliability × channel_reliability, or the 0.3 prior when uncalibrated), so
    the product is over edge confidences — folding it, not re-applying it, which would
    double-count. The product form penalizes long weak chains (§4).

    UNCALIBRATED GUARANTEE (1B): `uncalibrated = OR(edge.uncalibrated)` — one
    uncalibrated hop taints the chain so a consumer never reads it as calibrated; and
    numerically an uncalibrated factor is ≤ the 0.3 prior, so multiplying it in can
    only LOWER the product. A calibrated neighbour cannot lift it (`0.9 × 0.3 < 0.9`).
    Laundering-upward is arithmetically impossible AND flagged."""
    if not edges:
        return {"confidence": 0.0, "uncalibrated": True}
    conf = 1.0
    uncal = False
    for e in edges:
        conf *= e["confidence"]                 # channel reliability folded in at mint
        uncal = uncal or bool(e.get("uncalibrated", False))
    return {"confidence": round(conf, 6), "uncalibrated": uncal}


def deprecate_failed_edges(state, ledger, simulator, *,
                           samples: int = 25, tau: float = REPLAY_TAU) -> list[str]:
    """Screen every ACTIVE edge by replay (doc 05 §6) and DEPRECATE the ones that
    fail — a spurious/forged attribution does not survive. Mirrors §6's chain-bloat
    discipline: deprecated (not deleted), so it stays auditable. This is graph
    MAINTENANCE, not admission — the gate reads nothing here (that is PR-B). A failed
    edge is dropped from the graph's active set; per the approved decision it does NOT
    auto-reject any candidate — a candidate that cited it is simply judged on its base
    evidence alone (the uplift it would have granted, in PR-B, is withheld)."""
    exp_by_id = {e.exp_id: e for e in ledger}
    deprecated: list[str] = []
    for edge in state.causal_graph.get("edges", []):
        if edge.get("status", "active") != "active":
            continue
        exp = exp_by_id.get(scope_for_edge(edge)[0])
        if exp is None:
            continue
        if not replay_edge(edge, exp, simulator, samples=samples, tau=tau)["survives"]:
            edge["status"] = "deprecated"
            deprecated.append(edge["edge_id"])
    return deprecated
