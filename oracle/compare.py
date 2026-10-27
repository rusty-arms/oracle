"""Compare two RAM traces column by column and report where they first diverge.

    python3 -m oracle.compare EXPECTED ACTUAL [--tol NAME=AMOUNT ...] [--tol-all AMOUNT]

EXPECTED is normally a golden trace from Dolphin. Both files must have the same columns. Values
match when they are equal, both empty, or within the tolerance given for that column. Exit code
0 means every column matches on every shared frame.
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from typing import Sequence, Tuple

from .watch import parse_value

Mismatch = Tuple[str, int, str, str]


def _load(path: str) -> tuple[list[str], dict[int, list[str]]]:
    with open(path, newline="", encoding="ascii") as handle:
        rows = list(csv.reader(handle))
    if not rows or rows[0][:1] != ["frame"]:
        raise ValueError(f"{path} is not a trace: it has no 'frame' header")
    header, body = rows[0], rows[1:]
    return header, {int(row[0]): row for row in body}


def _close(a: str, b: str, tol: float) -> bool:
    if a == b:
        return True
    if a == "" or b == "":
        return False
    x, y = parse_value(a), parse_value(b)
    if isinstance(x, float) and isinstance(y, float) and math.isnan(x) and math.isnan(y):
        return True
    return abs(x - y) <= tol  # type: ignore[operator]


def compare(
    expected: str, actual: str, tolerances: dict[str, float], default: float = 0.0
) -> tuple[list[Mismatch], list[str]]:
    """Return the first mismatch per column, and notes on frames or columns that don't line up."""
    head_e, rows_e = _load(expected)
    head_a, rows_a = _load(actual)
    notes: list[str] = []
    if head_e != head_a:
        raise ValueError(f"columns differ: {head_e[1:]} vs {head_a[1:]}")
    unknown = sorted(set(tolerances) - set(head_e[1:]))
    if unknown:
        raise ValueError(f"tolerance for unknown column(s): {', '.join(unknown)}")
    frames = sorted(set(rows_e) & set(rows_a))
    only = len(set(rows_e) ^ set(rows_a))
    if only:
        notes.append(f"{only} frame(s) appear in only one trace and were skipped")
    first: dict[str, Mismatch] = {}
    for frame in frames:
        for index, name in enumerate(head_e[1:], 1):
            if name in first:
                continue
            a, b = rows_e[frame][index], rows_a[frame][index]
            if not _close(a, b, tolerances.get(name, default)):
                first[name] = (name, frame, a, b)
    return [first[name] for name in head_e[1:] if name in first], notes


def _tolerance(text: str) -> tuple[str, float]:
    name, sep, amount = text.partition("=")
    if not sep:
        raise argparse.ArgumentTypeError(f"expected NAME=AMOUNT, got {text!r}")
    return name, float(amount)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m oracle.compare", description=__doc__.split("\n")[0]
    )
    parser.add_argument("expected")
    parser.add_argument("actual")
    parser.add_argument(
        "--tol", type=_tolerance, action="append", default=[], metavar="NAME=AMOUNT"
    )
    parser.add_argument("--tol-all", type=float, default=0.0, metavar="AMOUNT")
    args = parser.parse_args(argv)
    try:
        mismatches, notes = compare(args.expected, args.actual, dict(args.tol), args.tol_all)
    except (OSError, ValueError) as exc:
        print(f"compare: {exc}", file=sys.stderr)
        return 2
    for note in notes:
        print(f"note: {note}")
    for name, frame, a, b in mismatches:
        print(
            f"{name}: first differs at frame {frame}: expected {a or 'empty'}, got {b or 'empty'}"
        )
    print("match" if not mismatches else f"{len(mismatches)} column(s) differ")
    return 0 if not mismatches else 1


if __name__ == "__main__":
    sys.exit(main())
