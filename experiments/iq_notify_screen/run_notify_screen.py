"""One preregistered six-run poll/notify comparison; no retries or app changes."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import statistics
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "iq_screen"))
from inspect_screen import require
from run_screen import captured, digest, write_json

ORDER = (("poll", "notify"), ("notify", "poll"), ("poll", "notify"))
BASE_REVISION = "dcddc4dc572ac5e034424ca602a860285f2e05a3"
BASE_FOLDERS = ("iq_screen", "iq_notification", "iq_slabs", "iq_coordinator", "iq_comparison", "iq_history")
GATES = {"duration_ms": 30000, "scheduled_requests": 300, "minimum_completion_percent": 95,
         "maximum_median_cpu_percent": 90, "minimum_cpu_winning_pairs": 2,
         "maximum_paired_producer_p99_percent": 105, "maximum_paired_take_p99_addition_ns": 1000000,
         "maximum_added_over_10ms": 0}


def take_p99(metrics):
    """Nearest-rank upper bound over every verified successful take, including late."""
    rows = metrics.get("request_timing_bounds")
    require(type(rows) is list and len(rows) == metrics.get("completed_requests") == 300,
            "Timing ledger must include every completed request")
    seen, values = set(), []
    for row in rows:
        request = row.get("request_id")
        require(type(request) is int and 1 <= request <= 300 and request not in seen,
                "Duplicate or invalid request identity")
        seen.add(request)
        # Base schema4 also emits rows for rejected/expired requests. Only
        # verified successful grants have both observation and verification
        # brackets; late successful grants retain these and must be included.
        grant = row.get("grant_observation_bracket_ns")
        verified = row.get("request_to_verified_ns_bounds")
        if grant is None and verified is None:
            continue
        require(type(grant) is dict and type(verified) is dict, "Partial verified-grant timing identity")
        bounds = row.get("request_to_take_ns_bounds") or {}
        lo, hi = bounds.get("lower_ns"), bounds.get("upper_ns")
        require(type(lo) is int and type(hi) is int and 0 <= lo <= hi, "Invalid take timing bounds")
        values.append(hi)
    require(type(metrics.get("verified_grants")) is int and len(values) == metrics["verified_grants"] > 0,
            "Successful take timing cardinality differs from all verified grants")
    return sorted(values)[(99 * len(values) + 99) // 100 - 1]


def decide(runs):
    expected = [(r, m) for r, modes in enumerate(ORDER, 1) for m in modes]
    if [(run.get("round"), run.get("wait_mode")) for run in runs] != expected:
        return {"passes_screen": False, "reasons": ["missing_or_reordered_trials"], "pairs": []}
    reasons, prepared = [], []
    for run in runs:
        label = f"round_{run['round']}_{run['wait_mode']}"
        m, s = run.get("metrics", {}), run.get("summary", {})
        if not (run.get("returncode") == 0 and run.get("error") is None and
                m.get("measurement_eligible") is True and m.get("complete_clean_workload") is True and
                s.get("schema_version") == 5 and s.get("variant") == "coordinator" and
                s.get("wait_mode") == run["wait_mode"] and s.get("format") == "cf32" and
                s.get("fault") == "none" and s.get("duration_ms") == 30000 and
                s.get("expected_requests") == 300 and m.get("completed_requests") == 300):
            reasons.append(label + "_invalid_measurement")
        counts = [m.get(k) for k in ("eligible_verified_requests", "verified_grants", "accepted_grants")]
        if not (all(type(v) is int for v in counts) and 0 <= counts[0] <= counts[1] == counts[2] <= 300):
            reasons.append(label + "_invalid_counts")
        p = m.get("timed_owner_work_ns") or {}
        cpu = m.get("process_cpu") or {}
        values = (p.get("p99"), cpu.get("elapsed_ns"), m.get("owner_work_over_10ms"))
        if not (all(type(v) is int for v in values) and values[0] > 0 and values[1] > 0 and
                0 <= values[2] <= 3000 and p.get("n") == 3000 and cpu.get("valid") is True and
                cpu.get("scope") == "before_thread_launch_through_join"):
            reasons.append(label + "_invalid_cost_metrics")
        try:
            take = take_p99(m)
        except (ValueError, AttributeError, TypeError):
            take = None
            reasons.append(label + "_invalid_take_metrics")
        prepared.append({"round": run["round"], "wait_mode": run["wait_mode"], "cpu_ns": values[1],
                         "owner_p99_ns": values[0], "owner_over_10ms": values[2],
                         "eligible": counts[0], "take_p99_upper_ns": take})
    if reasons:
        return {"passes_screen": False, "reasons": reasons, "pairs": []}
    pairs = []
    for r in range(1, 4):
        modes = {x["wait_mode"]: x for x in prepared if x["round"] == r}
        b, c = modes["poll"], modes["notify"]
        if b["eligible"] * 100 < 95 * 300 or c["eligible"] * 100 < 95 * 300:
            reasons.append(f"round_{r}_absolute_completion_below_95_percent")
        if c["eligible"] * 100 < 95 * b["eligible"]:
            reasons.append(f"round_{r}_paired_completion_below_95_percent")
        if c["owner_p99_ns"] * 100 > 105 * b["owner_p99_ns"]:
            reasons.append(f"round_{r}_producer_p99_regression_above_5_percent")
        if c["take_p99_upper_ns"] > b["take_p99_upper_ns"] + 1000000:
            reasons.append(f"round_{r}_take_p99_regression_above_1ms")
        if c["owner_over_10ms"] > b["owner_over_10ms"]:
            reasons.append(f"round_{r}_additional_owner_work_above_10ms")
        pairs.append({"round": r, "baseline": b, "candidate": c,
                      "cpu_ratio": c["cpu_ns"] / b["cpu_ns"],
                      "owner_p99_ratio": c["owner_p99_ns"] / b["owner_p99_ns"],
                      "take_p99_upper_addition_ns": c["take_p99_upper_ns"] - b["take_p99_upper_ns"]})
    bm = statistics.median(p["baseline"]["cpu_ns"] for p in pairs)
    cm = statistics.median(p["candidate"]["cpu_ns"] for p in pairs)
    wins = sum(p["candidate"]["cpu_ns"] < p["baseline"]["cpu_ns"] for p in pairs)
    if cm * 100 > bm * 90:
        reasons.append("median_cpu_reduction_below_10_percent")
    if wins < 2:
        reasons.append("fewer_than_two_paired_cpu_wins")
    return {"passes_screen": not reasons, "reasons": reasons, "pairs": pairs,
            "baseline_median_cpu_ns": bm, "candidate_median_cpu_ns": cm,
            "median_cpu_ratio": cm / bm, "cpu_winning_pairs": wins,
            "interpretation": "screen only; a pass permits longer study, not app or RF promotion"}


def failed_decision(runs, reason):
    result = decide(runs)
    result["passes_screen"] = False
    result["reasons"].append("experiment_integrity_failure: " + reason)
    return result


def verify_inputs(hashes):
    for path, expected in hashes.items():
        require(digest(path) == expected, "Frozen input changed: " + path)


def validated_output_guards(run, trial, prefix):
    """Bind retained raw bytes to the exact captured bytes independently validated."""
    hashes = {}
    for field in ("trace", "sidecar"):
        canonical = run["metrics"][field + "_sha256"]
        require(run.get(field + "_sha256") == canonical == digest(trial[field]),
                "Retained output differs from validated " + field)
        hashes[str(trial[field])] = canonical
    for suffix in (".stdout", ".stderr", ".process.json", ".summary.json", ".metrics.json"):
        path = str(prefix) + suffix
        hashes[path] = digest(path)
    return hashes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--host-context", type=Path, required=True)
    args = parser.parse_args()
    from inspect_notify import analyze
    repo, out = HERE.parent.parent, args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    report = {"schema_version": 1, "status": "preparing", "runs": []}
    write_json(out / "report.json", report)
    try:
        paths = sorted(p for folder in (*BASE_FOLDERS, "iq_notify_screen")
                       for p in (repo / "experiments" / folder).iterdir()
                       if p.is_file() and p.suffix in {".cpp", ".h", ".py", ".txt", ".md"})
        for path in paths:
            if path.parent.name in BASE_FOLDERS:
                blob = subprocess.run(["git", "show", f"{BASE_REVISION}:{path.relative_to(repo).as_posix()}"],
                                      cwd=repo, capture_output=True, check=True, timeout=30).stdout
                require(path.read_bytes().replace(b"\r\n", b"\n") == blob.replace(b"\r\n", b"\n"),
                        "Frozen base source content changed: " + str(path))
        paths.extend([repo / "docs/research/IQ-NOTIFY-SCREEN-PREREGISTRATION-2026-09-25.md",
                      repo / ".github/workflows/notify-screen-research.yml"])
        immutable = {str(path): digest(path) for path in paths}
        write_json(out / "prebuild-source-sha256.json", immutable)
        host = json.loads(args.host_context.read_bytes())
        require(type(host) is dict and all(host.get(k) for k in
                ("processor", "power_plan", "background_activity", "process_priority")), "Incomplete host context")
        require(host["process_priority"] == "normal", "Only normal process priority is preregistered")
        host.update(system=platform.system(), release=platform.release(), machine=platform.machine(),
                    python=platform.python_version())
        write_json(out / "host-context.json", host)
        build = out / "common-build"
        stages = (("configure", ["cmake", "-S", HERE, "-B", build, "-G", "Ninja",
                                 "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON"]),
                  ("build", ["cmake", "--build", build, "--parallel", "2"]),
                  ("checks", ["ctest", "--test-dir", build, "-V", "--output-on-failure", "--no-tests=error"]))
        for stage, command in stages:
            process, _ = captured(command, repo, out / stage, timeout=240)
            require(process["returncode"] == 0 and process["error"] is None, "Preflight " + stage + " failed")
        verify_inputs(immutable)
        executable = build / ("xerax_iq_notify_screen.exe" if sys.platform == "win32" else "xerax_iq_notify_screen")
        cache = (build / "CMakeCache.txt").read_text(encoding="utf-8")
        compiler = next(line.split("=", 1)[1] for line in cache.splitlines()
                        if line.startswith(("CMAKE_CXX_COMPILER:FILEPATH=", "CMAKE_CXX_COMPILER:STRING=")))
        require(Path(compiler).name.lower() in {"g++", "g++.exe", "c++", "c++.exe", "clang++", "clang++.exe"},
                "Driver supports GNU/Clang compiler identity only")
        process, raw = captured([compiler, "--version"], repo, out / "compiler")
        require(process["returncode"] == 0 and process["error"] is None, "Compiler identity unavailable")
        compiler_record = {"path": compiler, "sha256": digest(compiler), "version": raw.decode("utf-8", "replace")}
        for path in (executable, build / "CMakeCache.txt", build / "compile_commands.json", build / "build.ninja",
                     Path(compiler), out / "host-context.json"):
            immutable[str(path)] = digest(path)
        trials = []
        for r, modes in enumerate(ORDER, 1):
            for mode in modes:
                prefix = out / f"round-{r}-{mode}"
                trace, sidecar = Path(str(prefix) + ".csv"), Path(str(prefix) + ".sidecar.csv")
                trials.append({"round": r, "wait_mode": mode, "trace": str(trace), "sidecar": str(sidecar),
                               "command": [str(executable), "--variant", "coordinator", "--wait-mode", mode,
                                           "--format", "cf32", "--duration-ms", "30000", "--fault", "none",
                                           "--csv", str(trace), "--sidecar", str(sidecar)]})
        manifest = {"schema_version": 1, "frozen_utc": datetime.now(timezone.utc).isoformat(),
                    "base_revision": BASE_REVISION, "order": ORDER, "gates": GATES, "trials": trials,
                    "host_context": host, "compiler": compiler_record, "immutable_sha256": immutable,
                    "same_executable_for_both_modes": True,
                    "cpu_scope": "before_thread_launch_through_join; excludes prefill and serialization",
                    "memory_scope": "explicit representations/capacities; excludes opaque OS/std resources, not RSS"}
        write_json(out / "frozen-manifest.json", manifest)
        manifest_hash = digest(out / "frozen-manifest.json")
        guards = {**immutable, str(out / "frozen-manifest.json"): manifest_hash}
        report.update(status="running", manifest_sha256=manifest_hash)
        write_json(out / "report.json", report)
        for trial in trials:
            verify_inputs(guards)
            prefix = out / f"round-{trial['round']}-{trial['wait_mode']}"
            print(f"Starting round {trial['round']} {trial['wait_mode']}", flush=True)
            process, raw = captured(trial["command"], repo, prefix, timeout=60)
            run = {"round": trial["round"], "wait_mode": trial["wait_mode"], **process}
            report["runs"].append(run)
            for field in ("trace", "sidecar"):
                if Path(trial[field]).exists():
                    run[field + "_sha256"] = digest(trial[field])
            try:
                run["summary"] = json.loads(raw)
                write_json(str(prefix) + ".summary.json", run["summary"])
                run["metrics"] = analyze(trial["trace"], run["summary"], sidecar=trial["sidecar"],
                                         allow_failure=process["returncode"] != 0)
                write_json(str(prefix) + ".metrics.json", run["metrics"])
                require(process["returncode"] == 0 and process["error"] is None, "Trial process failed")
                require(run["metrics"]["measurement_eligible"], "Trial measurement ineligible")
                run["validated_output_sha256"] = validated_output_guards(run, trial, prefix)
                guards.update(run["validated_output_sha256"])
                verify_inputs(guards)
            except Exception as exc:
                run["error"] = type(exc).__name__ + ": " + str(exc)
                write_json(out / "report.json", report)
                raise
            write_json(out / "report.json", report)
            print(f"Finished: CPU={run['metrics']['process_cpu']['elapsed_ns']} ns; "
                  f"eligible={run['metrics']['eligible_verified_requests']}", flush=True)
        verify_inputs(guards)
        report.update(status="complete", decision=decide(report["runs"]))
        write_json(out / "report.json", report)
        print(json.dumps(report["decision"], indent=2), flush=True)
        return 0  # Negative measured performance is a successful experiment.
    except Exception as exc:
        report.update(status="failed", failure=type(exc).__name__ + ": " + str(exc),
                      decision=failed_decision(report["runs"], str(exc)))
        write_json(out / "report.json", report)
        print(report["failure"], file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
