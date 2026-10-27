"""Replay an input script in Dolphin and save the RAM trace and screenshots.

    python3 -m oracle.replay INPUTS --out DIR [--watch FILE] [--shots DIR] [--state FILE]
                             [--disc PATH] [--dolphin EXE] [--repeat N]

Each run starts Dolphin with a fresh, empty user folder (or a copy of --user-template) and the
settings in SETTINGS, so nothing from your everyday Dolphin setup leaks in. The run writes
`trace.csv` and `run.json` to --out, and screenshots to --shots. It refuses to write into a
folder that already has files, so a golden trace is never overwritten.

With --repeat N it replays N times and checks that every trace and screenshot is identical.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any

from . import __version__, inputs, watch
from .recorder import RESULT, TRACE, sha256_file

PACKAGE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(PACKAGE_DIR, "oracle", "dolphin_script.py")

# Passed to Dolphin as -C overrides. Single-core emulation and a fixed clock make runs repeatable;
# the rest stop prompts and focus changes from interfering, and match the brief's 1x resolution.
SETTINGS = (
    "Dolphin.Core.CPUThread=False",
    "Dolphin.Core.EnableCustomRTC=True",
    "Dolphin.Core.CustomRTCValue=946684800",
    "Dolphin.Core.EnableCheats=False",
    "Dolphin.Core.EmulationSpeed=0",
    "Dolphin.Interface.PauseOnFocusLost=False",
    "Dolphin.Analytics.PermissionAsked=True",
    "Dolphin.Analytics.Enabled=False",
    "Graphics.Settings.InternalResolution=1",
)


class RunError(RuntimeError):
    pass


def _need_file(path: str | None, what: str) -> str:
    if not path:
        raise RunError(f"no {what} given")
    if not os.path.isfile(path):
        raise RunError(f"{what} not found: {path}")
    return os.path.abspath(path)


def _empty_dir(path: str, what: str) -> str:
    path = os.path.abspath(path)
    if os.path.exists(path) and os.listdir(path):
        raise RunError(f"{what} {path} already has files; pick a new folder")
    return path


def build_command(
    dolphin: str, user_dir: str, disc: str, state: str | None, extra: list[str]
) -> list[str]:
    command = [dolphin, "--batch", "--user", user_dir, "--exec", disc, "--script", SCRIPT]
    for setting in SETTINGS:
        command += ["--config", setting]
    if state:
        command += ["--save_state", state]
    return command + extra


def run_once(args: argparse.Namespace, out_dir: str, shots_dir: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="oracle-") as temp:
        user_dir = os.path.join(temp, "dolphin-user")
        if args.user_template:
            shutil.copytree(args.user_template, user_dir)
        else:
            os.makedirs(user_dir)
        config = {
            "package_dir": PACKAGE_DIR,
            "inputs": args.inputs,
            "watch": args.watch,
            "out_dir": out_dir,
            "shots_dir": shots_dir,
            "port": args.port,
        }
        config_path = os.path.join(temp, "run.json")
        with open(config_path, "w", encoding="utf-8") as handle:
            json.dump(config, handle)
        command = build_command(args.dolphin, user_dir, args.disc, args.state, args.dolphin_arg)
        env = dict(os.environ, ORACLE_RUN=config_path)
        started = time.time()
        log_path = os.path.join(out_dir, "dolphin.log")
        os.makedirs(out_dir, exist_ok=True)
        with open(log_path, "wb") as log:
            process = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT)
            try:
                result = _wait(process, os.path.join(out_dir, RESULT), args.timeout)
            finally:
                _stop(process)
        result["seconds"] = round(time.time() - started, 1)
        result["command"] = command
        return result


def _wait(process: subprocess.Popen[bytes], result_path: str, timeout: float) -> dict[str, Any]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if os.path.exists(result_path):
            with open(result_path, encoding="utf-8") as handle:
                return json.load(handle)
        if process.poll() is not None:
            raise RunError(f"Dolphin exited with code {process.returncode} before the run finished")
        time.sleep(0.5)
    raise RunError(f"the run did not finish within {timeout:g} seconds")


def _stop(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def fingerprint(result: dict[str, Any]) -> dict[str, Any]:
    """What must match between repeats of the same replay."""
    return {
        "trace": result["trace_sha256"],
        "shots": {frame: shot["sha256"] for frame, shot in result["shots"].items()},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m oracle.replay", description=__doc__.split("\n")[0]
    )
    parser.add_argument("inputs", help="input script to replay")
    parser.add_argument("--out", required=True, help="new folder for trace.csv and run.json")
    parser.add_argument("--watch", help="watch list of RAM values to trace")
    parser.add_argument(
        "--shots", help="new folder for screenshots; required if the script has shots"
    )
    parser.add_argument("--state", help="Dolphin savestate to start from instead of booting")
    parser.add_argument(
        "--disc", default=os.environ.get("ORACLE_DISC"), help="disc image (or $ORACLE_DISC)"
    )
    parser.add_argument(
        "--dolphin",
        default=os.environ.get("ORACLE_DOLPHIN"),
        help="Dolphin executable (or $ORACLE_DOLPHIN)",
    )
    parser.add_argument("--user-template", help="Dolphin user folder to copy for each run")
    parser.add_argument(
        "--port", type=int, default=0, choices=range(4), help="controller port, 0 to 3"
    )
    parser.add_argument("--repeat", type=int, default=1, help="replay N times and check they match")
    parser.add_argument("--timeout", type=float, help="seconds per run before giving up")
    parser.add_argument(
        "--dolphin-arg", action="append", default=[], help="extra argument for Dolphin"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="check everything and print the command"
    )
    args = parser.parse_args(argv)

    try:
        args.inputs = _need_file(args.inputs, "input script")
        with open(args.inputs, encoding="utf-8") as handle:
            plan = inputs.parse(handle.read())
        if args.watch:
            args.watch = _need_file(args.watch, "watch list")
            with open(args.watch, encoding="utf-8") as handle:
                watches = watch.parse(handle.read())
        else:
            watches = []
        if plan.shots and not args.shots:
            raise RunError("the script takes screenshots, so give --shots")
        if args.state:
            args.state = _need_file(args.state, "savestate")
        if args.user_template and not os.path.isdir(args.user_template):
            raise RunError(f"user template not found: {args.user_template}")
        if args.repeat < 1:
            raise RunError("--repeat must be at least 1")
        out_dir = _empty_dir(args.out, "--out")
        shots_dir = (
            _empty_dir(args.shots, "--shots") if args.shots else os.path.join(out_dir, "shots")
        )
        if args.timeout is None:
            args.timeout = 120 + plan.frames / 60 * 4
        if args.dry_run:
            args.dolphin = args.dolphin or "DOLPHIN"
            args.disc = args.disc or "DISC"
            print(
                f"{plan.frames} frames, {len(plan.spans)} input ranges, {len(plan.shots)} screenshots,"
            )
            print(f"{len(watches)} watches. Dolphin would run as:")
            print(
                " ".join(
                    build_command(args.dolphin, "USER_DIR", args.disc, args.state, args.dolphin_arg)
                )
            )
            return 0
        args.dolphin = _need_file(args.dolphin, "Dolphin executable (--dolphin or $ORACLE_DOLPHIN)")
        args.disc = _need_file(args.disc, "disc image (--disc or $ORACLE_DISC)")

        result = run_once(args, out_dir, shots_dir)
        repeats = []
        for _ in range(args.repeat - 1):
            with tempfile.TemporaryDirectory(prefix="oracle-repeat-") as temp:
                again = run_once(args, os.path.join(temp, "out"), os.path.join(temp, "shots"))
            repeats.append(fingerprint(again) if not again["error"] else {"error": again["error"]})
    except (RunError, inputs.InputError, watch.WatchError) as exc:
        print(f"oracle: {exc}", file=sys.stderr)
        return 1

    record: dict[str, Any] = dict(result)
    record["host"] = {
        "rig_version": __version__,
        "inputs": {"file": os.path.basename(args.inputs), "sha256": sha256_file(args.inputs)},
        "watch": {"file": os.path.basename(args.watch), "sha256": sha256_file(args.watch)}
        if args.watch
        else None,
        "state": {"file": os.path.basename(args.state), "sha256": sha256_file(args.state)}
        if args.state
        else None,
        "disc": {"file": os.path.basename(args.disc), "bytes": os.path.getsize(args.disc)},
        "settings": list(SETTINGS),
        "user_template": bool(args.user_template),
    }
    identical = all(rep == fingerprint(result) for rep in repeats) if not result["error"] else False
    record["repeat"] = {"runs": args.repeat, "identical": identical, "others": repeats}
    with open(os.path.join(out_dir, "run.json"), "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.remove(os.path.join(out_dir, RESULT))

    if result["error"]:
        print(f"oracle: run failed: {result['error']}", file=sys.stderr)
        return 1
    print(
        f"{TRACE}: {result['trace_sha256']}, {len(result['shots'])} screenshots, {result['seconds']}s"
    )
    if args.repeat > 1:
        print(
            f"{args.repeat} runs "
            + ("identical" if identical else "DIFFER: replay is not deterministic")
        )
        if not identical:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
