"""Phase 1 end-to-end demo.

Proves the Phase 1 goal (roadmap §29): execution → structured experience.

  1. A naive agent plays the tool-selection simulator for N episodes.
  2. Every episode is captured as a structured experience (doc 03 schema),
     evaluated by the deterministic ground-truth channel, signed, chained.
  3. Merkle checkpoints anchor the history; a checkpoint is sealed into a
     signed grafomem .gfm evidence object.
  4. The audit path runs: chain verification, inclusion proof, seal
     verification, tamper detection.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ccr.simulator import ToolSelectionSimulator, NaiveAgent
from ccr.evaluator import SimulatorGroundTruthEvaluator
from ccr.capture import ExperienceCapture
from ccr.ledger import ExperienceLedger, LocalLedgerBackend, CompositeBackend, generate_keypair
from ccr.gmp_bridge import GMPInMemoryBackend, GMPFactBridge
from ccr.grafomem_seal import GrafomemSealer

TOOLS = ["search_api", "code_runner", "db_query", "web_fetch"]
REGIONS = ["api-interaction", "data-processing", "web-research"]
EPISODES = 48


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="ccr-phase1-"))
    priv, pub = generate_keypair()

    # --- wiring: local ledger + GMP bridge fan-out -------------------------
    gmp_store = GMPInMemoryBackend(tenant_id="ccr:demo")
    gmp_bridge = GMPFactBridge(gmp_store)
    backend = CompositeBackend(LocalLedgerBackend(tmp / "ledger.jsonl"),
                               gmp_bridge)
    ledger = ExperienceLedger(backend, priv, key_id="ccr-demo", checkpoint_every=16,
                              agent_ref="did:gns:ccr-demo-agent")

    # --- agent + environment ----------------------------------------------
    sim = ToolSelectionSimulator(TOOLS, REGIONS, seed=7)
    agent = NaiveAgent(TOOLS)
    capture = ExperienceCapture(ledger, SimulatorGroundTruthEvaluator(),
                                agent_ref="did:gns:ccr-demo-agent",
                                environment_ref="env:tool-selection-sim")

    # --- run: every episode becomes a signed, evaluated experience --------
    for ep in range(EPISODES):
        region = REGIONS[ep % len(REGIONS)]
        tool = agent.select_tool(region)
        result = sim.run_episode(tool, region, ep)
        capture.capture(
            state_summary=f"task in region '{region}'",
            goal=f"complete task in {region}",
            tool=tool, args={"region": region}, result=result,
            outcome_observed=("succeeded" if result["success"] else "failed")
                             + f" with {tool} in {region}",
            signals={"success": result["success"], "optimal": result["optimal"]},
            policy_region=region, goal_source="delegation",
        )

    # --- seal: anchor a checkpoint into grafomem signed state -------------
    cp = ledger.checkpoint()
    sealer = GrafomemSealer(priv)
    gfm = sealer.seal_checkpoint(cp)

    # --- audit path ---------------------------------------------------------
    chain_ok = ledger.verify_chain()
    proof = ledger.inclusion_proof(seq=5)
    inclusion_ok = ledger.verify_inclusion(proof)
    seal_ok = sealer.verify_seal(gfm)
    cp_ok = cp.verify(pub)

    # tamper test: flip one outcome, chain must break
    tampered = ledger.get(10)
    original = tampered.outcome.observed
    tampered.outcome.observed = "tampered"
    tamper_detected = not ledger.verify_chain()
    tampered.outcome.observed = original          # restore in-memory copy

    # --- report -------------------------------------------------------------
    evals = ledger.evaluated()
    successes = sum(1 for e in evals if e.evaluation.verdict == "success")
    optimal = sum(1 for e in ledger if e.outcome.signals.get("optimal"))

    print("=" * 68)
    print("CCR PHASE 1 — EXPERIENCE ENGINE DEMO")
    print("=" * 68)
    print(f"episodes captured ........... {len(ledger)}")
    print(f"evaluated ................... {len(evals)} (channel: simulator-ground-truth)")
    print(f"successes / optimal ......... {successes} / {optimal}")
    print(f"sim bounds (uniform/optimal)  {sim.uniform_rate():.3f} / {sim.optimal_rate():.3f}")
    print(f"checkpoints anchored ........ {len(ledger.checkpoints())}")
    print(f"GMP facts written ........... {gmp_bridge.facts_written}")
    print(f"GMP evaluation facts ........ {len(gmp_store.retrieve(predicate='ccr:evaluation'))}")
    print("-" * 68)
    print(f"hash chain verifies ......... {chain_ok}")
    print(f"Merkle inclusion (seq=5) .... {inclusion_ok}")
    print(f"checkpoint signature ........ {cp_ok}")
    print(f"grafomem .gfm seal verifies . {seal_ok}  ({len(gfm)} bytes, GFM1)")
    print(f"tamper detected ............. {tamper_detected}")
    print("-" * 68)
    sample = ledger.get(3)
    print("sample experience (seq=3):")
    print(f"  id        {sample.exp_id[:38]}…")
    print(f"  goal      {sample.goal.statement}")
    print(f"  action    {sample.action.steps[0].tool}  region={sample.action.policy_region}")
    print(f"  outcome   {sample.outcome.observed}")
    print(f"  eval      {sample.evaluation.verdict} (score={sample.evaluation.score}, "
          f"conf={sample.evaluation.confidence})")
    print(f"  prev_hash {sample.provenance.prev_hash[:38]}…")
    print("=" * 68)
    ok = all([chain_ok, inclusion_ok, seal_ok, cp_ok, tamper_detected,
              len(ledger) == EPISODES, gmp_bridge.facts_written > 0])
    print("PHASE 1 RESULT:", "PASS ✔" if ok else "FAIL ’")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
