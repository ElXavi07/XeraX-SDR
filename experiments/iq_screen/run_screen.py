"""Run one preregistered nine-trial screen; preserve every attempt, never retry.

Fresh Release builds, correctness checks and untimed calibration precede the
frozen manifest. No radio, application, or decoder is launched by this driver.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import re
import statistics
import subprocess
import sys
import time

from inspect_screen import analyze, require

ORDER = (("none", "whole", "coordinator"), ("whole", "coordinator", "none"),
         ("coordinator", "none", "whole"))
FROZEN_REVISION = "274677a"
FROZEN_FILES = ("iq_history.h", "iq_history.cpp", "credit_history.h", "credit_history.cpp")
GATES = {"duration_ms": 30000, "scheduled_requests": 300,
         "minimum_completion_fraction": .95, "maximum_median_p99_ratio": .75,
         "minimum_winning_rounds": 2, "maximum_added_over_10ms_per_round": 0}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def failed_decision(runs, reason):
    result = decide(runs)
    result["passes_screen"] = False
    result["reasons"].append("experiment_integrity_failure: " + reason)
    return result


def normalized_compilation(build, source, repo):
    """Compare actual compiler invocations, allowing only source/build paths."""
    def normalized(value):
        value = value.replace("\\", "/")
        for path, replacement in ((source, "<whole>"), (build, "<build>"), (repo, "<repo>")):
            value = value.replace(str(path).replace("\\", "/"), replacement)
        return value
    entries = json.loads((build / "compile_commands.json").read_bytes())
    result = []
    for entry in entries:
        # CMake hashes long object paths differently for different build roots.
        # Ignore only the single output object argument, retaining every flag.
        command, count = re.subn(r'(?<!\S)-o\s+(?:"[^"]*"|\S+)', '-o <object>', entry['command'])
        require(count == 1, "Expected one GNU/Clang output object argument")
        result.append((normalized(entry["file"]), normalized(command)))
    return sorted(result)


def decide(runs):
    """Fail closed unless the complete predetermined nine-run set passes."""
    expected = [(round_id, variant) for round_id, variants in enumerate(ORDER, 1) for variant in variants]
    reasons = []
    if [(r.get("round"), r.get("variant")) for r in runs] != expected:
        return {"passes_screen": False, "reasons": ["missing_or_reordered_trials"], "pairs": []}
    for run in runs:
        metrics, summary = run.get("metrics", {}), run.get("summary", {})
        valid = (run.get("returncode") == 0 and run.get("error") is None and
                 metrics.get("measurement_eligible") is True and
                 metrics.get("complete_clean_workload") is True and
                 summary.get("variant") == run["variant"] and summary.get("format") == "cf32" and
                 summary.get("duration_ms") == GATES["duration_ms"] and
                 summary.get("fault") == "none" and
                 metrics.get("accepted_grants") == metrics.get("verified_grants"))
        if not valid:
            reasons.append(f"round_{run['round']}_{run['variant']}_measurement_invalid")
        p99 = (metrics.get("timed_owner_work_ns") or {}).get("p99")
        count = (metrics.get("timed_owner_work_ns") or {}).get("n")
        if type(p99) is not int or p99 <= 0 or count != 3000:
            reasons.append(f"round_{run['round']}_{run['variant']}_owner_metric_invalid")
        for field in ("eligible_verified_requests", "accepted_grants", "verified_grants", "owner_work_over_10ms"):
            if type(metrics.get(field)) is not int or metrics[field] < 0:
                reasons.append(f"round_{run['round']}_{run['variant']}_{field}_invalid")
        scheduled = 0 if run["variant"] == "none" else GATES["scheduled_requests"]
        if summary.get("expected_requests") != scheduled or metrics.get("completed_requests") != scheduled:
            reasons.append(f"round_{run['round']}_{run['variant']}_request_cardinality_invalid")
        if type(metrics.get("eligible_verified_requests")) is int and metrics["eligible_verified_requests"] > scheduled:
            reasons.append(f"round_{run['round']}_{run['variant']}_completion_overflow")
        counts = [metrics.get(key) for key in ("eligible_verified_requests", "verified_grants", "accepted_grants")]
        if all(type(value) is int for value in counts) and not 0 <= counts[0] <= counts[1] <= counts[2] <= scheduled:
            reasons.append(f"round_{run['round']}_{run['variant']}_contradictory_completion_counts")
    if reasons:
        return {"passes_screen": False, "reasons": reasons, "pairs": []}
    pairs = []
    for round_id in range(1, 4):
        by_variant = {r["variant"]: r["metrics"] for r in runs if r["round"] == round_id}
        base, candidate = by_variant["whole"], by_variant["coordinator"]
        b, c = base["eligible_verified_requests"], candidate["eligible_verified_requests"]
        # Integer comparisons avoid floating-point boundary ambiguity at 95%.
        if b * 100 < 95 * 300 or c * 100 < 95 * 300:
            reasons.append(f"round_{round_id}_absolute_completion_below_95_percent")
        if c * 100 < 95 * b:
            reasons.append(f"round_{round_id}_paired_completion_below_95_percent")
        if candidate["owner_work_over_10ms"] > base["owner_work_over_10ms"]:
            reasons.append(f"round_{round_id}_additional_work_over_10ms")
        bp, cp = base["timed_owner_work_ns"]["p99"], candidate["timed_owner_work_ns"]["p99"]
        pairs.append({"round": round_id, "baseline_p99_ns": bp, "candidate_p99_ns": cp,
                      "candidate_minus_baseline_ns": cp - bp, "ratio": cp / bp,
                      "baseline_eligible_verified": b, "candidate_eligible_verified": c})
    bm = statistics.median(p["baseline_p99_ns"] for p in pairs)
    cm = statistics.median(p["candidate_p99_ns"] for p in pairs)
    wins = sum(p["candidate_p99_ns"] < p["baseline_p99_ns"] for p in pairs)
    if cm * 4 > bm * 3:
        reasons.append("median_p99_reduction_below_25_percent")
    if wins < 2:
        reasons.append("fewer_than_two_paired_p99_wins")
    return {"passes_screen": not reasons, "reasons": reasons, "pairs": pairs,
            "baseline_median_p99_ns": bm, "candidate_median_p99_ns": cm,
            "median_ratio": cm / bm, "paired_wins": wins,
            "interpretation": "engineering screen only; no APK/EXE, decoder or RF promotion"}


def captured(command, cwd, prefix, *, timeout=180):
    start = time.perf_counter_ns()
    error = None
    try:
        result = subprocess.run([str(x) for x in command], cwd=cwd, capture_output=True, timeout=timeout, check=False)
        code, stdout, stderr = result.returncode, result.stdout, result.stderr
    except (subprocess.TimeoutExpired, OSError) as exc:
        code, stdout, stderr = None, getattr(exc, "stdout", None) or b"", getattr(exc, "stderr", None) or b""
        error = type(exc).__name__ + ": " + str(exc)
    Path(str(prefix) + ".stdout").write_bytes(stdout)
    Path(str(prefix) + ".stderr").write_bytes(stderr)
    record = {"command": [str(x) for x in command], "returncode": code, "error": error,
              "driver_elapsed_ns": time.perf_counter_ns() - start,
              "stdout_sha256": hashlib.sha256(stdout).hexdigest(), "stderr_sha256": hashlib.sha256(stderr).hexdigest()}
    write_json(str(prefix) + ".process.json", record)
    return record, stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New directory; existing directories are rejected")
    parser.add_argument("--frozen-source", type=Path, required=True)
    parser.add_argument("--host-context", type=Path, required=True,
                        help="JSON documenting power plan, processor and uncontrolled background activity")
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    repo = here.parent.parent
    out, frozen = args.output.resolve(), args.frozen_source.resolve()
    out.mkdir(parents=True, exist_ok=False)
    report = {"schema_version": 1, "status": "preparing", "runs": []}
    write_json(out / "report.json", report)
    try:
        selected = {}
        for name in FROZEN_FILES:
            blob = subprocess.run(["git", "show", f"{FROZEN_REVISION}:experiments/iq_history/{name}"],
                                  cwd=repo, capture_output=True, check=True, timeout=30).stdout
            require((frozen / name).read_bytes() == blob, f"Frozen source differs from Git blob: {name}")
            selected[name] = hashlib.sha256(blob).hexdigest()
        source_paths = sorted(path for folder in ("iq_screen", "iq_slabs", "iq_coordinator", "iq_history", "iq_comparison")
                              for path in (repo / "experiments" / folder).iterdir()
                              if path.is_file() and path.suffix in {".cpp", ".h", ".py", ".txt", ".md"})
        source_paths.append(repo / "docs/research/IQ-SCREEN-PREREGISTRATION-2026-09-25.md")
        source_paths.extend(frozen / n for n in FROZEN_FILES)
        source_hashes = {str(p): digest(p) for p in source_paths}
        require(all(source_hashes[str(frozen / n)] == selected[n] for n in FROZEN_FILES),
                "Frozen source changed after Git verification")
        write_json(out / "prebuild-source-sha256.json", source_hashes)
        host = json.loads(args.host_context.read_bytes())
        require(type(host) is dict and all(host.get(k) for k in
                ("processor", "power_plan", "background_activity", "process_priority")), "Incomplete host context")
        require(host["process_priority"] == "normal", "Only preregistered normal process priority is allowed")
        host.update({"system": platform.system(), "release": platform.release(), "machine": platform.machine(),
                     "python": platform.python_version()})
        write_json(out / "host-context.json", host)
        suffix = ".exe" if sys.platform == "win32" else ""
        builds = {}
        for label, source in (("baseline", frozen), ("candidate", repo / "experiments/iq_history")):
            build = out / (label + "-build")
            commands = [
                ["cmake", "-S", str(here), "-B", str(build), "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release",
                 "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON", "-DXERAX_WHOLE_SOURCE_DIR=" + str(source)],
                ["cmake", "--build", str(build), "--parallel", "2"],
                ["ctest", "--test-dir", str(build), "-V", "--output-on-failure", "--no-tests=error"]]
            for stage, command in zip(("configure", "build", "checks"), commands):
                process, _ = captured(command, repo, out / f"{label}-{stage}")
                require(process["returncode"] == 0 and process["error"] is None, f"{label} {stage} failed")
            builds[label] = {"directory": build, "executable": build / ("xerax_iq_screen" + suffix),
                             "calibrator": build / ("xerax_iq_memory_calibration" + suffix)}
        process, raw = captured([builds["baseline"]["calibrator"], "--format", "cf32"], repo, out / "calibration")
        require(process["returncode"] == 0 and process["error"] is None, "Baseline calibration process failed")
        calibration = json.loads(raw)
        require(calibration.get("available") is True, "Native baseline calibration unavailable")
        write_json(out / "calibration.json", calibration)
        for path, expected_hash in source_hashes.items():
            require(digest(path) == expected_hash, "Source changed during preparation: " + path)
        immutable = dict(source_hashes)
        require(normalized_compilation(builds["baseline"]["directory"], frozen, repo) ==
                normalized_compilation(builds["candidate"]["directory"], repo / "experiments/iq_history", repo),
                "Compiler invocations differ beyond selected source and build paths")
        for build in builds.values():
            for p in (build["executable"], build["calibrator"], build["directory"] / "CMakeCache.txt",
                      build["directory"] / "compile_commands.json", build["directory"] / "build.ninja"):
                immutable[str(p)] = digest(p)
        immutable[str(out / "calibration.json")] = digest(out / "calibration.json")
        compiler_records = {}
        for label, build in builds.items():
            cache = (build["directory"] / "CMakeCache.txt").read_text(encoding="utf-8")
            compiler = next(line.split("=", 1)[1] for line in cache.splitlines()
                            if line.startswith(("CMAKE_CXX_COMPILER:FILEPATH=", "CMAKE_CXX_COMPILER:STRING=")))
            require(Path(compiler).name.lower() in {"g++", "g++.exe", "c++", "c++.exe", "clang++", "clang++.exe"},
                    "This screen runner supports GNU/Clang version reporting, not arbitrary compilers")
            process, raw = captured([compiler, "--version"], repo, out / f"{label}-compiler")
            require(process["returncode"] == 0, "Compiler identity unavailable")
            compiler_records[label] = {"path": compiler, "sha256": digest(compiler), "version": raw.decode("utf-8", "replace")}
        require(compiler_records["baseline"] == compiler_records["candidate"], "Build compilers differ")
        trials = [{"round": round_id, "variant": variant,
                   "command": [str(builds["candidate" if variant == "coordinator" else "baseline"]["executable"]),
                               "--variant", variant, "--format", "cf32", "--duration-ms", "30000", "--fault", "none",
                               "--csv", str(out / f"round-{round_id}-{variant}.csv")]}
                  for round_id, variants in enumerate(ORDER, 1) for variant in variants]
        manifest = {"schema_version": 1, "frozen_utc": datetime.now(timezone.utc).isoformat(),
                    "frozen_whole_revision": FROZEN_REVISION, "frozen_whole_sha256": selected,
                    "order": ORDER, "gates": GATES, "host_context": host, "compilers": compiler_records,
                    "immutable_sha256": immutable, "trials": trials,
                    "cpu_scope": "actual process counters before worker launch through join; excludes prefill and serialization",
                    "memory_scope": "equal bounded payload; unequal explicit metadata accounting; not RSS or memory savings"}
        write_json(out / "frozen-manifest.json", manifest)
        manifest_hash = digest(out / "frozen-manifest.json")
        report.update({"status": "running", "manifest_sha256": manifest_hash})
        write_json(out / "report.json", report)
        for trial in trials:
            for path, expected_hash in immutable.items():
                require(digest(path) == expected_hash, "Frozen input changed: " + path)
            require(digest(out / "frozen-manifest.json") == manifest_hash, "Frozen manifest changed")
            prefix = out / f"round-{trial['round']}-{trial['variant']}"
            print(f"Starting round {trial['round']} {trial['variant']}", flush=True)
            process, raw = captured(trial["command"], repo, prefix, timeout=60)
            run = {"round": trial["round"], "variant": trial["variant"], **process}
            report["runs"].append(run)
            trace = Path(trial["command"][-1])
            if trace.exists():
                run["trace_sha256"] = digest(trace)
            try:
                run["summary"] = json.loads(raw)
                write_json(str(prefix) + ".summary.json", run["summary"])
                run["metrics"] = analyze(trace, run["summary"], allow_failure=process["returncode"] != 0,
                                         memory_calibration=calibration if trial["variant"] != "coordinator" else None)
                write_json(str(prefix) + ".metrics.json", run["metrics"])
                require(process["returncode"] == 0 and process["error"] is None, "Trial process failed")
                require(run["metrics"]["measurement_eligible"], "Trial is not measurement-eligible: " +
                        str(run["metrics"]["measurement_ineligible_reasons"]))
            except Exception as exc:
                run["error"] = type(exc).__name__ + ": " + str(exc)
                write_json(out / "report.json", report)
                raise
            write_json(out / "report.json", report)
            print(f"Finished: p99={run['metrics']['timed_owner_work_ns']['p99']} ns; eligible={run['metrics']['eligible_verified_requests']}", flush=True)
        for path, expected_hash in immutable.items():
            require(digest(path) == expected_hash, "Frozen input changed during final trial: " + path)
        require(digest(out / "frozen-manifest.json") == manifest_hash, "Frozen manifest changed")
        report.update({"status": "complete", "decision": decide(report["runs"])})
        write_json(out / "report.json", report)
        print(json.dumps(report["decision"], indent=2), flush=True)
        return 0  # A measured negative result is a successful experiment.
    except Exception as exc:
        report.update({"status": "failed", "failure": type(exc).__name__ + ": " + str(exc),
                       "decision": failed_decision(report["runs"], str(exc))})
        write_json(out / "report.json", report)
        print(report["failure"], file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
