"""Fill a SEPARATE demo data dir with synthetic captures, mine, evaluate — so the dashboard can be shown and tested
without touching the real library.

    python -m radbrain.demo --n 600            # data dir: <normal data dir>-demo (or --data <path>)
    python -m radbrain.web --demo              # (sets RADBRAIN_DATA to the demo dir)
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def demo_dir() -> Path:
    os.environ.pop("RADBRAIN_DATA", None)
    from . import config
    return Path(str(config.data_dir()) + "-demo")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=600)
    ap.add_argument("--seed", type=int, default=5)
    ap.add_argument("--data", default=None)
    ap.add_argument("--llm-eval", action="store_true")
    a = ap.parse_args(argv)
    target = Path(a.data) if a.data else demo_dir()
    os.environ["RADBRAIN_DATA"] = str(target)
    from . import config, evaluate, library, miner, pipeline, synth
    d = config.data_dir()
    if (d / "library.sqlite").exists():
        con = library.connect()
        real = con.execute("SELECT COUNT(*) FROM captures WHERE synthetic=0").fetchone()[0]
        con.close()
        if real:
            print("refusing: this data dir contains real captures", file=sys.stderr)
            return 2
    synth.write_test_signers(d / "signers.json")
    con = library.connect()
    st = {}
    for doc in synth.corpus(a.n, seed=a.seed):
        r = pipeline.ingest(doc.kind, doc.draft, doc.final, source="synthetic", synthetic=True, con=con, remine=False)
        st[r["status"]] = st.get(r["status"], 0) + 1
    m = miner.mine(con)
    ev = evaluate.run(con, llm=a.llm_eval)
    con.close()
    print(f"demo data dir: {d}\ncaptures: {st}\nrules: {m}\neval (synthetic): "
          + ", ".join(f"{k} chrF {v['chrf_draft']}→{v['chrf_engine']}" for k, v in ev["by_signer"].items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
