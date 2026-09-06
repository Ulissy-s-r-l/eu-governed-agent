"""Phases 3-4 demo: the gate that refuses to learn.

Three demonstrations (the ones that matter — doc 00 §8's empty columns):

  D1  A poisoned experience arrives; the admission gate rejects it; the
      rejection is in the ledger with its reasoning.
  D2  A candidate passes admission but FAILS REPLAY against held-out history;
      it never commits; behavior is unchanged.
  D3  A harmful update DOES commit (legitimately, on thin early evidence),
      degrades behavior, is detected, and is REVERTED — with the full
      provenance path from bad policy entry -> transaction -> justifying
      experiences still verifiable.

None of this needs the agent to be good at anything. It needs the gate, the
transaction, and the DAG.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ccr.ledger import ExperienceLedger, LocalLedgerBackend, generate_keypair
from ccr.evaluator import SimulatorGroundTruthEvaluator
from ccr.capture import ExperienceCapture
from ccr.simulator import ToolSelectionSimulator
from ccr.state import CognitiveState
from ccr.transaction import LearningEngine, LearningAgent, AdmissionGate
from ccr.experience import EvaluationBlock

TOOLS = ["search_api", "code_runner", "db_query", "web_fetch"]
REGION = "data-processing"


def banner(t: str) -> None:
    print("\n" + "=" * 72 + f"\n{t}\n" + "=" * 72)


def main() -> None:
    priv, pub = generate_keypair()
    tmp = Path(tempfile.mkdtemp(prefix="ccr-tx-"))
    ledger = ExperienceLedger(LocalLedgerBackend(tmp / "ledger.jsonl"), priv,
                              checkpoint_every=32)
    capture = ExperienceCapture(ledger, SimulatorGroundTruthEvaluator())
    engine = LearningEngine(ledger, AdmissionGate(threshold=0.55, min_evidence=3))
    sim = ToolSelectionSimulator(TOOLS, ["api-interaction", REGION, "web-research"], seed=7)

    state = CognitiveState.genesis(
        ["api-interaction", REGION, "web-research"], TOOLS)
    agent = LearningAgent(state, TOOLS)

    # ---- seed honest history: ground-truth-evaluated experiences ----------
    banner("SETUP — honest evaluated history (ground-truth channel)")
    for ep in range(24):
        tool = TOOLS[ep % len(TOOLS)]
        res = sim.run_episode(tool, REGION, ep)
        capture.capture(state_summary=f"task in {REGION}", goal="complete task",
                        tool=tool, args={"region": REGION}, result=res,
                        outcome_observed=str(res["success"]), signals=res,
                        policy_region=REGION)
    best = sim.best_tool(REGION)
    print(f"ledger: {len(ledger)} evaluated experiences; chain ok: {ledger.verify_chain()}")
    print(f"simulator truth: best tool in '{REGION}' = {best}")

    evidence = [e for e in ledger.evaluated() if e.action.policy_region == REGION]

    # ================= D1: poisoned experience rejected at the gate ==========
    banner("D1 — POISONED EVIDENCE: forged self-report experiences")
    # Attacker injects experiences claiming a bad tool succeeds — but only
    # self-reported (no ground-truth channel). Confidence is capped at 0.3.
    bad_tool = min(TOOLS, key=lambda t: sim.reliability(t, REGION))
    forged = []
    for k in range(4):
        exp = capture.emit(state_summary=f"task in {REGION}", goal="complete task",
                           tool=bad_tool, args={"region": REGION},
                           result={"forged": True},
                           outcome_observed="succeeded",
                           signals={"success": True, "agent_claims_success": True},
                           policy_region=REGION)
        exp.evaluation = EvaluationBlock(           # self-report only: no ground truth
            verdict="success", score=1.0, confidence=0.3,
            channels=["agent-self-report"], evaluator_ref="eval:agent-self-report")
        forged.append(ledger.append(exp))
    tx1, state = engine.commit(state, REGION, forged)
    print(f"poisoned tool: {bad_tool} (true reliability "
          f"{sim.reliability(bad_tool, REGION):.3f})")
    print(f"gate: V={tx1.admission['V']} threshold={tx1.admission['threshold']} "
          f"trust={tx1.admission['trust']}  -> ADMIT: {tx1.admission['admit']}")
    print(f"transaction status: {tx1.status}")
    print(f"policy unchanged:   {agent.state.policy_for(REGION).best()} "
          f"(still genesis-uniform best)")
    # rejection is auditable in the ledger
    import json
    gate_records = [json.loads(l) for l in ledger.backend.read_all()
                    if json.loads(l)["kind"] == "gate_decision"]
    print(f"rejection recorded in ledger: {gate_records[-1]['payload']['status']}")
    d1 = tx1.status == "rejected" and gate_records[-1]["payload"]["status"] == "rejected"

    # ============== D2: admitted candidate fails replay, never commits =======
    banner("D2 — REGRESSION ATTEMPT: admitted, killed by replay")
    # First commit an HONEST update. Held-out replay (doc 04 §2.2) requires the
    # justification and the replay set to be DISJOINT, so the honest commit
    # cites a TRAINING SUBSET and leaves the rest as held-out — otherwise
    # citing all region evidence leaves nothing to replay against and the
    # commit self-rejects for "no held-out evidence".
    train = evidence[: len(evidence) // 2]           # half cited; half held out
    tx0, state = engine.commit(state, REGION, train)
    agent.on_state(state)
    print(f"honest commit: cited {len(train)} of {len(evidence)} (rest held out); "
          f"tx0 status={tx0.status}; state v{state.version} now prefers "
          f"'{state.policy_for(REGION).best()}' in '{REGION}'")

    mediocre = [t for t in TOOLS if t != best][1]
    thin = [e for e in evidence if e.action.steps[-1].tool == mediocre][:3]
    tx2, state2 = engine.commit(state, REGION, thin)
    v2 = tx2.validation
    print(f"candidate tool: {mediocre} on {tx2.admission['n']} experiences "
          f"(V={tx2.admission['V']}, admitted={tx2.admission['admit']})")
    print(f"replay verdict: {v2.get('verdict')} — {v2.get('reason', '')}")
    print(f"transaction status: {tx2.status}")
    print(f"state version still: {state2.version}; "
          f"agent still prefers '{agent.state.policy_for(REGION).best()}'")
    d2 = (tx2.status == "rejected" and v2.get("verdict") == "reject"
          and state2.version == state.version)

    # ======== D3: harmful commit -> detection -> revert, provenance intact ===
    banner("D3 — HARMFUL COMMIT, DETECTION, FORWARD-ONLY REVERT")
    # Craft a scenario where validation legitimately passes on thin data:
    # restrict replay history by using a FRESH region with planted early luck.
    bad_region = "api-interaction"
    lucky_tool = min(TOOLS, key=lambda t: sim.reliability(t, bad_region))
    luck = []
    ep = 100
    # plant 4 "successes" for the bad tool via ground truth (simulate luck by
    # scanning episodes until the bad tool succeeds 4 times)
    while len(luck) < 4 and ep < 400:
        res = sim.run_episode(lucky_tool, bad_region, ep)
        e = capture.capture(state_summary=f"task in {bad_region}", goal="g",
                            tool=lucky_tool, args={"region": bad_region},
                            result=res, outcome_observed=str(res["success"]),
                            signals=res, policy_region=bad_region)
        if res["success"]:
            luck.append(e)
        ep += 1
    # pad with one more success from another tool so admission has support
    res = sim.run_episode(lucky_tool, bad_region, ep)
    luck.append(capture.capture(state_summary="s", goal="g", tool=lucky_tool,
                                args={}, result={"success": True},
                                outcome_observed="True",
                                signals={"success": True}, policy_region=bad_region))
    state_before = agent.state
    tx3, state_harmed = engine.commit(agent.state, bad_region, luck)
    agent.on_state(state_harmed)
    chosen = agent.select_tool(bad_region)
    v3 = tx3.validation
    print(f"committed tx {tx3.tx_id} -> state v{state_harmed.version}")
    # HONEST NARRATIVE — why did a harmful update pass validation?
    # NOT because replay judged it safe: it committed because the incumbent has
    # no history in this fresh region (inc_rate is None), so do-no-harm had
    # nothing to compare against. Held-out replay even saw the candidate's true
    # (poor) rate and could not act on it. This is the cold-start limitation:
    # replay cannot protect a region it has never seen.
    print(f"WHY IT COMMITTED (cold start): inc_rate={v3.get('inc_rate')} "
          f"(no incumbent history in '{bad_region}') → do-no-harm vacuous; "
          f"cold_start_no_incumbent={v3.get('cold_start_no_incumbent')}; "
          f"held_out_n={v3.get('held_out_n')}, candidate held-out "
          f"rate={v3.get('cand_rate')} — replay saw it but could not compare.")
    print(f"BEHAVIOR CHANGED: agent now selects '{chosen}' in {bad_region} "
          f"(true reliability {sim.reliability(chosen, bad_region):.3f}, "
          f"best is {sim.best_tool(bad_region)} at "
          f"{sim.reliability(sim.best_tool(bad_region), bad_region):.3f})")

    # detection: monitor sees the committed policy prefers a low-reliability tool
    detected = sim.reliability(chosen, bad_region) < 0.5
    print(f"detection (drift monitor): policy prefers sub-0.5 tool -> {detected}")

    # revert: forward-only, new commit with ancestor content
    tx4, state_restored = engine.revert(agent.state, state_before,
                                        incident_evidence=f"tx {tx3.tx_id} promoted "
                                        f"low-reliability tool {chosen}")
    agent.on_state(state_restored)
    print(f"revert tx {tx4.tx_id} -> state v{state_restored.version} "
          f"(content == v{state_before.version})")
    print(f"behavior restored: agent selects '{agent.select_tool(bad_region)}' "
          f"(genesis uniform)")
    print(f"harmful tx still in ledger: {any(t.tx_id == tx3.tx_id for t in engine.transactions)}"
          f"  (history never rewritten)")
    print(f"restored state's parent chain: {state_restored.parent_commitment[:26]}… "
          f"= harmed state's commitment: "
          f"{state_restored.parent_commitment == state_harmed.commitment}")
    d3 = (tx3.status == "committed" and detected
          and agent.state.policy_for(bad_region).best() != chosen
          and state_restored.parent_commitment == state_harmed.commitment)

    # ---- final audit --------------------------------------------------------
    banner("AUDIT")
    print(f"hash chain verifies after everything: {ledger.verify_chain()}")
    print(f"ledger size: {len(ledger)} experiences + "
          f"{sum(1 for l in ledger.backend.read_all() if json.loads(l)['kind']=='gate_decision')}"
          f" gate decisions")
    ok = d1 and d2 and d3 and ledger.verify_chain()
    print(f"\nD1 poison rejected: {d1} | D2 replay killed: {d2} | "
          f"D3 commit->detect->revert: {d3}")
    print("RESULT:", "PASS ✔ — the gate refuses, the replay protects, "
          "the DAG recovers" if ok else "FAIL ✗")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
