"""
Sweeps the (S, AR, margin) design grid and precomputes optimizer
results for every combination, saving them to a single JSON file.

This lets the frontend become a fully static site: instead of
calling a backend, it looks up (and interpolates between) these
precomputed results.

Run this LOCALLY (not on Render) — it needs your existing
optimizer.py, wing_deflection.py, and naca2412_polar.csv in the
same folder.

    python generate_lookup.py

Output: lookup_table.json
"""

import json
import time

import numpy as np

from optimizer import optimize_aircraft


# ============================================================
# GRID RESOLUTION
#
# These do NOT need to match your slider step sizes exactly.
# A coarser grid here + interpolation on the frontend gives
# near-identical results with far fewer optimizer calls and a
# much smaller JSON file.
#
# Tune n_S / n_AR / n_margin up or down depending on how long
# you're willing to let this run, and how large a JSON file
# you're okay bundling into your site.
# ============================================================

S_MIN, S_MAX, N_S = 0.10, 0.20, 11        # step ~0.010
AR_MIN, AR_MAX, N_AR = 4.0, 8.0, 17       # step ~0.25
MARGIN_MIN, MARGIN_MAX, N_MARGIN = 0.02, 0.10, 9  # step ~0.010

S_VALUES = np.linspace(S_MIN, S_MAX, N_S)
AR_VALUES = np.linspace(AR_MIN, AR_MAX, N_AR)
MARGIN_VALUES = np.linspace(MARGIN_MIN, MARGIN_MAX, N_MARGIN)

TOTAL = len(S_VALUES) * len(AR_VALUES) * len(MARGIN_VALUES)


# ============================================================
# TRIM RESULT
#
# Keep only the fields the frontend actually renders, to keep
# the JSON file small. Add fields back in if App.tsx needs them.
# ============================================================

def trim_result(result: dict) -> dict:

    def g(d, *path):
        """Safe nested getter, returns None on any missing key."""
        for key in path:
            if d is None:
                return None
            d = d.get(key)
        return d

    return {
        "success": result.get("success"),
        "status": result.get("status"),

        "constraints": {
            "feasible": g(result, "constraints", "feasible"),
            "n_violated": g(result, "constraints", "n_violated"),
            "n_satisfied": g(result, "constraints", "n_satisfied"),
            "violations": g(result, "constraints", "violations") or [],
        },

        "wing": result.get("wing"),
        "horizontal_tail": result.get("horizontal_tail"),
        "vertical_tail": result.get("vertical_tail"),
        "performance": result.get("performance"),
        "stability": result.get("stability"),
        "locations": result.get("locations"),
        "structural": result.get("structural"),
    }


# ============================================================
# SWEEP
# ============================================================

def main():

    table = {}

    start = time.time()
    count = 0
    failures = 0

    for S in S_VALUES:
        for AR in AR_VALUES:
            for margin in MARGIN_VALUES:

                count += 1

                key = f"{S:.4f}_{AR:.4f}_{margin:.4f}"

                try:
                    result = optimize_aircraft(
                        S=float(S),
                        AR=float(AR),
                        margin=float(margin),
                    )
                    table[key] = trim_result(result)

                except Exception as error:
                    failures += 1
                    table[key] = {
                        "success": False,
                        "status": "error",
                        "error": str(error),
                    }

                if count % 25 == 0 or count == TOTAL:
                    elapsed = time.time() - start
                    rate = count / elapsed if elapsed > 0 else 0
                    remaining = (TOTAL - count) / rate if rate > 0 else 0
                    print(
                        f"[{count}/{TOTAL}] "
                        f"{elapsed:.0f}s elapsed, "
                        f"~{remaining:.0f}s remaining, "
                        f"{failures} failures"
                    )

    output = {
        "axes": {
            "S": S_VALUES.tolist(),
            "AR": AR_VALUES.tolist(),
            "margin": MARGIN_VALUES.tolist(),
        },
        "results": table,
    }

    with open("lookup_table.json", "w") as f:
        json.dump(output, f)

    print(f"\nDone. Wrote lookup_table.json ({len(table)} entries, {failures} failures).")


if __name__ == "__main__":
    main()