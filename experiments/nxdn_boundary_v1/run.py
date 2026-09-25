"""Run the preregistered 144-process boundary screen once; preserve every failure."""
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

ROOT = prepare.ROOT
LIVE = {str(Path(p).resolve()): prepare.sha(p) for p in (__file__, analyze.__file__, prepare.__file__)}


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def preserved(group):
    return all(Path(p).is_file() and prepare.sha(p) == value for p, value in group.items())


def invoke(binary, folder, case, inputs, manifest, observed, enabled):
    folder.mkdir(parents=True, exist_ok=False)
    result = {"measurement_pass": False, "exit_code": None}
    try:
        args = [str(binary), str(inputs / manifest["waveforms"][case["waveform"]]["file"]),
                "0", str(case["chunk"]), str(observed), str(folder / "pops.u32le")]
        save(folder / "invocation.json", {"arguments": args, "dsd_environment_removed": True})
        with (folder / "events.jsonl").open("wb") as out, (folder / "stderr.txt").open("wb") as err:
            result["exit_code"] = subprocess.run(args, stdout=out, stderr=err, cwd=folder, timeout=60,
                env={k: v for k, v in os.environ.items() if not k.upper().startswith("DSD_")}).returncode
        rows = [json.loads(line) for line in (folder / "events.jsonl").read_text().splitlines()]
        audit = analyze.inspect(rows, folder / "pops.u32le", case, manifest, inputs, observed)
        audit["policy"] = analyze.inspect_policy(folder / "phase.jsonl", rows, enabled)
        result["audit"] = audit
        prepare.need(result["exit_code"] == 0 and audit["measurement_pass"]
                     and audit["policy"]["measurement_pass"], "Native or measurement failure")
        result["measurement_pass"] = True
    except Exception as error:
        result.update(exception=type(error).__name__, detail=str(error))
        (folder / "failure.txt").write_text(traceback.format_exc(), encoding="utf-8")
    save(folder / "audit.json", result)
    return result


def run(build, parent, inputs, output):
    output.mkdir(parents=True, exist_ok=False)
    prepare.need(preserved(LIVE), "Imported scripts changed")
    manifest = json.loads((inputs / "manifest.json").read_text())
    prepare.need(prepare.sha(inputs / "manifest.json") == "11a9a496bc4671d174b4b7cce096598a44d7dd35b0378d63258ceddf652c7c08", "Input identity changed")
    prepare.need(len(manifest["cases"]) == 36 and len(manifest["waveforms"]) == 18, "Grid changed")
    frozen = output / "frozen"; frozen.mkdir()
    binaries = {}
    for role in ("baseline", "candidate"):
        binaries[role] = frozen / (role + ".exe")
        shutil.copy2(build / ("xerax_nxdn_boundary_" + role + ".exe"), binaries[role])
        shutil.copy2(build / (role + ".map"), frozen / (role + ".map"))
    for p in build.glob("*.dll"):
        shutil.copy2(p, frozen / p.name)
    for name in ("CMakeCache.txt", "compile_commands.json", "build.ninja", "toolchain.cmake"):
        shutil.copy2(build / name, frozen / name)
    shutil.copytree(build / "generated", frozen / "generated")
    shutil.copytree(build / "observation/generated", frozen / "observation-generated")
    for module in ("nxdn_boundary_v1", "nxdn_observation_v2"):
        target = frozen / module; target.mkdir()
        for p in (ROOT / "experiments" / module).iterdir():
            if p.is_file(): shutil.copy2(p, target / p.name)
    registration = ROOT / "docs/research/NXDN-BOUNDARY-V1-PREREGISTRATION-2026-09-25.md"
    shutil.copy2(registration, frozen / registration.name)
    # Preserve reports of independent preflight checks, including any corrections.
    for pattern in ("nxdn-boundary-v1-*audit*", "nxdn-boundary-v1-*log", "nxdn-boundary-v1-*note*", "nxdn-boundary-v1-dependency*.json"):
        for p in (ROOT / "build").glob(pattern):
            if p.is_file(): shutil.copy2(p, frozen / p.name)
    configured = {}
    for command in json.loads((build / "compile_commands.json").read_text()):
        p = Path(command["file"])
        if p.is_file(): configured[str(p.resolve())] = prepare.sha(p)
    linked = json.loads((ROOT / "build/nxdn-boundary-v1-build-audit.json").read_text())
    prepare.need(linked["source_and_linkage_pass"], "Independent build audit failed")
    dependencies = {p: value["sha256"] for p, value in linked["explicit_link_archives"].items()}
    prepare.need(preserved(dependencies), "Audited dependency archives changed")
    prepare.need(not subprocess.check_output(["git", "diff", "56e83dd", "--", "upstream"], cwd=ROOT), "Product changed")
    protected = {}
    for group in json.loads((ROOT / "build/nxdn-observation-v2-preservation-after.json").read_text()).values():
        for p, digest in group.items(): protected[str((ROOT / p).resolve())] = digest
    for p in (ROOT / "docs/research/evidence/nxdn-observation-v2-2026-09-25-raw.zip",
              ROOT / "docs/research/evidence/nxdn-observation-v2-2026-09-25.json", parent / "report.json"):
        protected[str(p.resolve())] = prepare.sha(p)
    prepare.need(preserved(protected), "Protected artifacts changed")
    shutil.copytree(inputs, output / "inputs"); inputs = output / "inputs"
    anchors = {}
    for case in manifest["cases"]:
        anchor = manifest["waveforms"][case["waveform"]].get("boundary_anchor")
        if not anchor: continue
        for observed in (0, 1):
            for name in ("events.jsonl", "pops.u32le"):
                path = parent / "runs" / f"{anchor}-c{case['chunk']}" / str(observed) / name
                anchors[str(path)] = prepare.sha(path)
                target = frozen / "anchors" / case["id"] / str(observed) / name
                target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, target)
    files = {str(p.resolve()): prepare.sha(p) for p in output.rglob("*") if p.is_file()}
    save(output / "before-execution.json", {"utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "frozen_files": files, "executed_sources": LIVE, "configured_sources": configured,
        "explicit_link_archives": dependencies,
        "configured_scope": "Existing paths in compile_commands, including configured unbuilt targets",
        "protected": protected, "anchors": anchors,
        "binaries": {role: prepare.sha(p) for role, p in binaries.items()}})
    report = {"kind": "nxdn_boundary_v1", "attempts": [], "measurement_failures": [], "anchor_differences": [],
              "measurement_pass": False, "progression_pass": False, "product_promotion": False}
    pairs = {}
    for case in manifest["cases"]:
        for role in ("baseline", "candidate"):
            for observed in (0, 1):
                folder = output / "runs" / case["id"] / role / str(observed)
                result = invoke(binaries[role], folder, case, inputs, manifest, observed, int(role == "candidate"))
                report["attempts"].append({"id": case["id"], "role": role, "observed": observed,
                    "exit_code": result["exit_code"], "measurement_pass": result["measurement_pass"], "detail": result.get("detail")})
                if result["measurement_pass"]:
                    pairs.setdefault(case["id"], {}).setdefault(role, {})[observed] = result["audit"]
                else: report["measurement_failures"].append(f"{case['id']}/{role}/{observed}: {result.get('detail')}")
                if role == "baseline" and manifest["waveforms"][case["waveform"]].get("boundary_anchor"):
                    for name in ("events.jsonl", "pops.u32le"):
                        reference = frozen / "anchors" / case["id"] / str(observed) / name
                        if not (folder / name).is_file() or prepare.sha(folder / name) != prepare.sha(reference):
                            report["anchor_differences"].append(f"{case['id']}/{observed}/{name}")
                save(output / "report.json", report)
    report["contract"] = analyze.compare(pairs, manifest)
    report["preservation_pass"] = all(preserved(g) for g in (files, LIVE, configured, protected, anchors, dependencies))
    report["measurement_pass"] = (len(report["attempts"]) == 144 and report["preservation_pass"]
        and not report["measurement_failures"] and not report["anchor_differences"] and report["contract"]["measurement_pass"])
    report["progression_pass"] = report["measurement_pass"] and report["contract"]["progression_pass"]
    report["files"] = {str(p.relative_to(output)): prepare.sha(p) for p in output.rglob("*") if p.is_file() and p != output / "report.json"}
    save(output / "report.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("build", "parent", "inputs", "output"): parser.add_argument(name, type=Path)
    args = parser.parse_args()
    if args.output.exists(): parser.error("Existing result directory is immutable")
    try:
        report = run(*(getattr(args, n).resolve() for n in ("build", "parent", "inputs", "output")))
    except Exception as error:
        args.output.mkdir(parents=True, exist_ok=True)
        path = args.output / "report.json"
        report = json.loads(path.read_text()) if path.exists() else {}
        report.update(measurement_pass=False, progression_pass=False, exception=type(error).__name__, detail=str(error))
        save(path, report); (args.output / "failure.txt").write_text(traceback.format_exc(), encoding="utf-8")
    print(json.dumps({k: report.get(k) for k in ("measurement_pass", "progression_pass", "measurement_failures", "anchor_differences", "detail")}))
    sys.exit(0 if report["measurement_pass"] else 1)
