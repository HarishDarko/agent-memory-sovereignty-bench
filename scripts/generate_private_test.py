"""Hidden TEST split generator - intentionally a stub until Phase 1 design freeze."""

from __future__ import annotations

import sys


def main() -> None:
    print(
        "Hidden TEST split is NOT generated yet.\n"
        "It is frozen only after the benchmark design stabilizes (post Phase 1 "
        "design freeze), then written to datasets/private_test/ and "
        "scorer_private/ground_truth/ - both gitignored until release."
    )
    raise SystemExit(0)


if __name__ == "__main__":
    main()
