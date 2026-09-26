"""Freeze and run the registered engine matrix once, retaining every attempted process."""
import argparse
import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import traceback

import analyze
import prepare


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def execute(binary, directory, case, inputs, manifest, enabled):
    directory.mkdir(parents=True, exist_ok=False)
    result = {"measurement_pass": False, "exit_code": None}
    rows = []
    try:
        arguments = [str(binary.resolve()), str((inputs / manifest["waveforms"][case["waveform"]]["file"]).resolve()),
                     str(case["fast"]), str(case["chunk"]), str(enabled), str((directory / "pops.u32le").resolve())]
        environment = {k: v for k, v in os.environ.items() if not k.upper().startswith("DSD_")}
        save(directory / "invocation.json", {"arguments": arguments, "dsd_environment_removed": True})
        with (directory / "events.jsonl").open("wb") as out, (directory / "stderr.txt").open("wb") as err:
            result["exit_code"] = subprocess.run(arguments, stdout=out, stderr=err, timeout=60, env=environment,
                                                   cwd=directory).returncode
        rows = [json.loads(line) for line in (directory / "events.jsonl").read_text().splitlines()]
        result["audit"] = analyze.inspect(rows, directory / "pops.u32le", case, manifest, inputs, enabled)
        analyze.require(result["exit_code"] == 0, f"native exit {result['exit_code']}")
        result["measurement_pass"] = True
    except Exception as error:
        result.update(exception=type(error).__name__, detail=str(error))
        (directory / "failure.txt").write_text(traceback.format_exc())
    save(directory / "audit.json", result)
    return rows, result


def run(build, output):
    output.mkdir(parents=True, exist_ok=False)
    manifest = prepare.prepare(output / "inputs")
    for file in (output / "inputs").rglob("*"):
        if file.is_file():
            relative = file.relative_to(output / "inputs")
            analyze.require(prepare.sha(file) == prepare.sha(build / "inputs" / relative), f"build input mismatch {relative}")
    frozen = output / "frozen"
    frozen.mkdir()
    for path in (prepare.ROOT / "experiments/nxdn_engine_gap").glob("*"):
        if path.is_file():
            shutil.copy2(path, frozen / path.name)
    for relative in ("upstream/dsd-neo/src/engine/engine.c", "upstream/dsd-neo/src/engine/dispatch/dispatch_nxdn.c",
                     "upstream/dsd-neo/src/engine/dispatch/protocol_dispatch.c", "upstream/dsd-neo/src/protocol/nxdn/nxdn_frame.c",
                     "upstream/dsd-neo/src/protocol/nxdn/nxdn_confirm.c", "upstream/dsd-neo/src/protocol/nxdn/nxdn_deperm.c",
                     "upstream/dsd-neo/src/core/frames/dsd_dibit.c", "upstream/dsd-neo/src/dsp/dsd_symbol.c",
                     "upstream/dsd-neo/src/dsp/dsd_frame_sync.c", "experiments/nxdn_frames/generate_vectors.py",
                     "docs/research/NXDN-ENGINE-GAP-PREREGISTRATION-2026-09-25.md"):
        destination = frozen / "source" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(prepare.ROOT / relative, destination)
    binaries = {}
    for role in ("baseline", "candidate"):
        binary = build / ("xerax_nxdn_engine_" + role + (".exe" if os.name == "nt" else ""))
        binaries[role] = frozen / (role + binary.suffix)
        shutil.copy2(binary, binaries[role])
        shutil.copy2(build / (role + ".map"), frozen / (role + ".map"))
    for dependency in build.glob("*.dll"):
        shutil.copy2(dependency, frozen / dependency.name)
    for name in ("CMakeCache.txt", "compile_commands.json", "build.ninja"):
        if (build / name).is_file():
            shutil.copy2(build / name, frozen / name)
    identities = {str(p.relative_to(output)): prepare.sha(p) for p in output.rglob("*") if p.is_file()}
    save(output / "before-execution.json", {"utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
         "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=prepare.ROOT, text=True).strip(), "files": identities})
    report = {"schema": 1, "kind": "nxdn_engine_gap", "case_count": len(manifest["cases"]), "attempts": [],
              "measurement_failures": [], "chunk_differences": [], "measurement_pass": False, "progression_pass": False}
    audits = {}
    for case in manifest["cases"]:
        for role, binary in binaries.items():
            two_rows, two_results = [], []
            for enabled in (0, 1):
                directory = output / "runs" / case["id"] / role / str(enabled)
                rows, result = execute(binary, directory, case, output / "inputs", manifest, enabled)
                report["attempts"].append({"id": case["id"], "role": role, "observed": enabled,
                    "measurement_pass": result["measurement_pass"], "exit_code": result["exit_code"],
                    "detail": result.get("detail")})
                two_rows.append(rows); two_results.append(result)
                if not result["measurement_pass"]:
                    report["measurement_failures"].append(f"{case['id']}/{role}/{enabled}: {result.get('detail')}")
                save(output / "report.json", report)
            if all(r["measurement_pass"] for r in two_results):
                if analyze.semantic(two_rows[0]) != analyze.semantic(two_rows[1]):
                    report["measurement_failures"].append(f"{case['id']}/{role}: observer changed common outcomes")
                audits.setdefault(case["id"], {})[role] = two_results[1]["audit"]
    complete_pairs = {cid: roles for cid, roles in audits.items() if set(roles) == {"baseline", "candidate"}}
    report["quality"] = analyze.quality(complete_pairs)
    for case in manifest["cases"]:
        if case["chunk"] != 37:
            continue
        other = case["id"].removesuffix("c37") + "c512"
        for role in ("baseline", "candidate"):
            if role in audits.get(case["id"], {}) and role in audits.get(other, {}):
                if analyze.chunk_signature(audits[case["id"]][role]) != analyze.chunk_signature(audits[other][role]):
                    report["chunk_differences"].append(f"{case['id']}/{other}/{role}")
    report["reset_coverage"] = []
    for case in manifest["cases"]:
        waveform = manifest["waveforms"][case["waveform"]]
        for role, audit in audits.get(case["id"], {}).items():
            if waveform["zero_gaps_before_shaping"]:
                lo, hi = waveform["zero_gaps_before_shaping"][0]
                actual = [{"frontier": r["begin"]["frontier"], "before_confirmed": r["begin"]["confirmed"],
                           "before_streak": r["begin"]["streak"], "after_confirmed": r["end"]["confirmed"],
                           "after_streak": r["end"]["streak"]} for r in audit["resets"] if lo < r["begin"]["frontier"] < hi]
                report["reset_coverage"].append({"id": case["id"], "role": role, "gap": [lo, hi], "resets": actual})
    report["reset_gate_pass"] = bool(report["reset_coverage"]) and all(
        any((r["before_confirmed"] == 1 if "-strong_reset_gap-" in control["id"] else
             r["before_confirmed"] == 0 and r["before_streak"] == 1)
            and r["after_confirmed"] == r["after_streak"] == 0 for r in control["resets"])
        for control in report["reset_coverage"])
    report["preservation_pass"] = all(prepare.sha(output / relative) == digest for relative, digest in identities.items())
    report["measurement_pass"] = (report["preservation_pass"] and not report["measurement_failures"]
                                   and len(report["attempts"]) == len(manifest["cases"]) * 4)
    report["progression_pass"] = (report["measurement_pass"] and report["quality"]["progression_pass"]
                                  and not report["chunk_differences"] and report["reset_gate_pass"])
    report["files"] = {str(p.relative_to(output)): prepare.sha(p) for p in output.rglob("*") if p.is_file() and p != output / "report.json"}
    save(output / "report.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("build", type=Path); parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output already exists; do not replace an experiment")
    try:
        report = run(args.build, args.output)
    except Exception as error:
        path = args.output / "report.json"
        report = json.loads(path.read_text()) if path.exists() else {}
        report.update(measurement_pass=False, progression_pass=False, exception=type(error).__name__, detail=str(error))
        args.output.mkdir(parents=True, exist_ok=True)
        save(path, report); (args.output / "failure.txt").write_text(traceback.format_exc())
    print(json.dumps({k: report.get(k) for k in ("measurement_pass", "progression_pass", "measurement_failures", "chunk_differences", "detail")}))
    sys.exit(0 if report["measurement_pass"] else 1)
