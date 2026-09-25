"""Sequential, rotated-order storage trials with raw trace verification.

No SDK, hardware, credentials, network or application configuration is used.
Never run this concurrently with another performance experiment or build.
"""
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import statistics
import subprocess
import time


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TraceValidationError(ValueError):
    """A completed process did not produce a valid, internally consistent measurement."""


# Values are the fixed Status enum values in the frozen/current schema-1 harness.
# Keep unexpected failures distinct rather than counting them as generic rejections.
SNAPSHOT_STATUS_FIELDS = {0: "snapshot_ok", 9: "snapshot_not_retained",
                          11: "snapshot_busy", 13: "snapshot_deadline"}
TRACE_COLUMNS = ["kind", "index", "call_us", "wake_late_us", "missed_deadline", "status", "verify_us"]


def require(condition, message):
    if not condition:
        raise TraceValidationError(message)


def result_count(value, name):
    require(type(value) is int and value >= 0, f"{name} must be a nonnegative integer")
    return value


def csv_count(value, name):
    require(isinstance(value, str) and value.isascii() and value.isdigit(),
            f"{name} must be an unsigned integer field")
    return int(value)


def nonnegative_number(value, name):
    require(isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and value >= 0, f"{name} must be finite and nonnegative")
    return value


def checked_trace(path, result, expected_workload=None):
    """Validate raw evidence with explicit exceptions, including under python -O."""
    try:
        require(isinstance(result, dict), "Measurement must be an object")
        require(type(result["schema"]) is int and result["schema"] == 1, "Unknown measurement schema")
        seconds = result_count(result["seconds"], "seconds")
        hz = result_count(result["snapshot_hz"], "snapshot_hz")
        hold = result_count(result["hold_ms"], "hold_ms")
        require(1 <= seconds <= 600 and 1 <= hz <= 100 and hold <= 10000, "Measurement workload outside bounds")
        require(result["variant"] in ("none", "whole", "chunk64", "chunk256"), "Unknown measured variant")
        require(result["format"] in ("cu8", "cf32"), "Unknown measured format")
        if expected_workload is not None:
            for key, value in expected_workload.items():
                require(result[key] == value, f"Measured {key} disagrees with requested workload")
        expected_appends = seconds * 100
        expected_snapshots = 0 if result["variant"] == "none" else seconds * hz
        require(result_count(result["appends"], "appends") == expected_appends, "Incomplete producer workload")
        require(result_count(result["snapshot_attempts"], "snapshot_attempts") == expected_snapshots,
                "Incomplete snapshot-attempt workload")
        for field in SNAPSHOT_STATUS_FIELDS.values():
            result_count(result[field], field)
        result_count(result["finish_after_next_scheduled_block"], "finish_after_next_scheduled_block")
        result_count(result["append_call_over_10ms"], "append_call_over_10ms")

        append, snapshots = [], []
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            require(reader.fieldnames == TRACE_COLUMNS, "Missing, duplicate or unknown trace columns")
            for index, row in enumerate(reader):
                require(index < expected_appends + expected_snapshots, "Trace contains excess rows")
                require(set(row) == set(TRACE_COLUMNS) and all(value is not None for value in row.values()),
                        "Malformed trace row")
                require(row["kind"] in ("append", "snapshot"), "Unknown trace row kind")
                parsed = {"kind": row["kind"]}
                for name in ("index", "missed_deadline", "status"):
                    parsed[name] = csv_count(row[name], name)
                require(parsed["missed_deadline"] in (0, 1), "Invalid missed-deadline flag")
                for name in ("call_us", "wake_late_us", "verify_us"):
                    parsed[name] = nonnegative_number(float(row[name]), name)
                if parsed["kind"] == "append":
                    require(parsed["status"] == 0, "Trace reports a failed append")
                    append.append(parsed)
                else:
                    require(parsed["status"] in SNAPSHOT_STATUS_FIELDS, "Unknown snapshot status")
                    snapshots.append(parsed)

        require(len(append) == expected_appends, "Trace append count disagrees with workload")
        require(len(snapshots) == expected_snapshots, "Trace snapshot count disagrees with workload")
        require([row["index"] for row in append] == list(range(len(append))), "Append indices missing/reordered")
        require([row["index"] for row in snapshots] == list(range(len(snapshots))), "Snapshot indices missing/reordered")
        for status, field in SNAPSHOT_STATUS_FIELDS.items():
            require(sum(row["status"] == status for row in snapshots) == result[field],
                    f"Trace status count disagrees with {field}")
        require(sum(row["missed_deadline"] for row in append) == result["finish_after_next_scheduled_block"],
                "Missed-deadline count disagrees with trace")
        require(sum(row["call_us"] > 10000 for row in append) == result["append_call_over_10ms"],
                "Append budget count disagrees with trace")
        successful = [row for row in snapshots if row["status"] == 0]
        for name, values in (
            ("append_us", [row["call_us"] for row in append]),
            ("wake_lateness_us", [row["wake_late_us"] for row in append]),
            ("snapshot_success_us", [row["call_us"] for row in successful]),
            ("verification_us", [row["verify_us"] for row in successful]),
            ("snapshot_rejected_us", [row["call_us"] for row in snapshots if row["status"] != 0]),
        ):
            if not values:
                require(result[name] is None, f"{name} must be null without observations")
                continue
            values.sort()
            expected = {"n": len(values), "max": values[-1]}
            expected.update({f"p{p}": values[math.ceil(len(values) * p / 100) - 1] for p in (50, 95, 99)})
            require(isinstance(result[name], dict), f"{name} must contain summary statistics")
            require(result_count(result[name]["n"], f"{name}.n") == len(values), f"{name}.n disagrees with trace")
            for key, value in expected.items():
                actual = nonnegative_number(result[name][key], f"{name}.{key}")
                require(abs(actual - value) < 0.00001, f"{name}.{key} disagrees with trace")
    except TraceValidationError:
        raise
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise TraceValidationError(f"Malformed measurement/trace: {exc}") from exc


def output_bytes(value):
    if value is None:
        return b""
    return value if isinstance(value, bytes) else str(value).encode("utf-8", errors="replace")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seconds", type=int, default=60)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--formats", nargs="+", choices=["cu8", "cf32"], default=["cu8", "cf32"])
    parser.add_argument("--holds", nargs="+", type=int, default=[0, 500])
    args = parser.parse_args()
    if not 1 <= args.seconds <= 600 or not 1 <= args.rounds <= 20 or any(not 0 <= h <= 10000 for h in args.holds):
        parser.error("Workload outside documented bounds")
    args.out.mkdir(parents=True, exist_ok=False)
    baseline, candidate = args.baseline.resolve(), args.candidate.resolve()
    variants = [("none", baseline, "none"), ("baseline", baseline, "whole"),
                ("credit_whole", candidate, "whole"), ("chunk64", candidate, "chunk64"),
                ("chunk256", candidate, "chunk256")]
    report = {"schema": 1, "scope": "paced IQ-storage latency screening; not live RF or decoder performance",
              "host": {"platform": platform.platform(), "processor": platform.processor(), "logical_cpus": os.cpu_count()},
              "binary_sha256": {"baseline": digest(baseline), "candidate": digest(candidate)},
              "harness_sha256": digest(Path(__file__).with_name("latency.cpp")),
              "orchestrator_sha256": digest(Path(__file__)),
              "candidate_library_sha256": {n: digest(Path(__file__).with_name(n)) for n in
                  ("iq_history.h", "iq_history.cpp", "credit_history.h", "credit_history.cpp")},
              "baseline_library_sha256": {n: digest(baseline.parent / n) for n in
                  ("iq_history.h", "iq_history.cpp", "credit_history.h", "credit_history.cpp")},
              "seconds_per_trial": args.seconds, "rounds": args.rounds,
              "order": "rotate variants by round; formats and holds in argument order",
              "clock": "std::chrono::steady_clock; per-call timer, separate wake lateness",
              "scheduler_affinity_priority_or_timer_resolution_changed": False,
              "trials": [], "summary": [], "production_promotion": False, "complete": False}
    target = args.out / "report.json"

    def save():
        target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    save()
    for fmt in args.formats:
        for hold in args.holds:
            for round_index in range(args.rounds):
                offset = round_index % len(variants)
                for label, exe, variant in variants[offset:] + variants[:offset]:
                    name = f"{fmt}-hold{hold}-r{round_index}-{label}"
                    csv_path = (args.out / (name + ".csv")).resolve()
                    command = [str(exe), "--variant", variant, "--format", fmt, "--seconds", str(args.seconds),
                               "--snapshot-hz", "10", "--hold-ms", str(hold), "--csv", str(csv_path)]
                    trial = {"name": name, "variant": label, "format": fmt, "hold_ms": hold,
                             "round": round_index, "command": command, "status": "starting",
                             "stdout_file": name + ".stdout", "stderr_file": name + ".stderr"}
                    report["trials"].append(trial)
                    save()
                    begin = time.monotonic()
                    try:
                        run = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=args.seconds + 30)
                    except subprocess.TimeoutExpired as exc:
                        (args.out / trial["stdout_file"]).write_bytes(output_bytes(exc.stdout))
                        (args.out / trial["stderr_file"]).write_bytes(output_bytes(exc.stderr))
                        trial.update(status="timeout", timeout_seconds=args.seconds + 30,
                                     wall_seconds_including_startup=time.monotonic() - begin)
                        save()
                        raise
                    except OSError as exc:
                        diagnostic = f"Trial executable could not start: {type(exc).__name__}: {exc}\n"
                        (args.out / trial["stdout_file"]).write_bytes(b"")
                        (args.out / trial["stderr_file"]).write_bytes(diagnostic.encode("utf-8", errors="replace"))
                        trial.update(status="launch_failed", stage="launch", exception_type=type(exc).__name__,
                                     error=str(exc), errno=exc.errno, winerror=getattr(exc, "winerror", None),
                                     wall_seconds_including_startup=time.monotonic() - begin)
                        save()
                        raise
                    (args.out / trial["stdout_file"]).write_bytes(output_bytes(run.stdout))
                    (args.out / trial["stderr_file"]).write_bytes(output_bytes(run.stderr))
                    trial.update(exit_code=run.returncode, wall_seconds_including_startup=time.monotonic() - begin)
                    if run.returncode:
                        trial["status"] = "failed"; save()
                        raise RuntimeError(f"Trial failed; retained outputs for {name}")
                    try:
                        trial["measurements"] = json.loads(run.stdout)
                        checked_trace(csv_path, trial["measurements"],
                                      {"variant": variant, "format": fmt, "seconds": args.seconds,
                                       "snapshot_hz": 10, "hold_ms": hold})
                    except Exception as exc:
                        trial.update(status="invalid_measurement", error=str(exc)); save()
                        raise
                    trial.update(status="passed", trace_sha256=digest(csv_path))
                    save()
                    m = trial["measurements"]
                    print(f"{name}: append p99 {m['append_us']['p99']:.3f} us; snapshots {m['snapshot_ok']}/{m['snapshot_attempts']}", flush=True)
    for fmt in args.formats:
        for hold in args.holds:
            for label, _, _ in variants:
                trials = [t["measurements"] for t in report["trials"] if t["format"] == fmt and t["hold_ms"] == hold and t["variant"] == label]
                report["summary"].append({"format": fmt, "hold_ms": hold, "variant": label, "trials": len(trials),
                    "median_run_append_p99_us": statistics.median(t["append_us"]["p99"] for t in trials),
                    "median_run_append_max_us": statistics.median(t["append_us"]["max"] for t in trials),
                    "snapshot_ok": sum(t["snapshot_ok"] for t in trials),
                    "snapshot_attempts": sum(t["snapshot_attempts"] for t in trials),
                    "append_calls_over_10ms": sum(t["append_call_over_10ms"] for t in trials),
                    "scheduled_deadlines_missed": sum(t["finish_after_next_scheduled_block"] for t in trials)})
    report["complete"] = True
    save()
    print(f"Completed {len(report['trials'])} trials; no production-promotion verdict.", flush=True)


if __name__ == "__main__":
    main()
