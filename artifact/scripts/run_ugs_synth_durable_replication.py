"""Start or resume one fresh UGS-SYNTH durable replication trajectory."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from self_organizing_engineering_agent.experiments.ugs_synth_interleaved_review.durable_replication import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
