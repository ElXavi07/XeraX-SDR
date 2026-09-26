"""Freeze and run the registered nine-frame primary reference exactly once."""
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
BASELINE = "85bec0a62bb21f5f1bec75d6da9c65820462b39c"
INPUT_SHA = "17061018477b6451207758d6e0390b3ef623e88099f565bfc3416f1168127067"
LIVE = {str(Path(p).resolve()): prepare.sha(p) for p in (__file__, analyze.__file__, prepare.__file__)}


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def hashes(folder):
    return {str(p.resolve()): prepare.sha(p) for p in folder.rglob("*") if p.is_file() and "__pycache__" not in p.parts}


def preserved(group):
    return all(Path(p).is_file() and prepare.sha(p) == digest for p, digest in group.items())


def invoke(arguments, folder, stdout_name):
    folder.mkdir(parents=True, exist_ok=False)
    save(folder / "invocation.json", {"arguments": [str(p) for p in arguments],
        "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "timeout_seconds": 60,
        "dsd_environment_removed": True})
    result = {"exit_code": None}
    try:
        with (folder / stdout_name).open("wb") as out, (folder / "stderr.txt").open("wb") as err:
            result["exit_code"] = subprocess.run([str(p) for p in arguments], cwd=folder,
                stdout=out, stderr=err, timeout=60,
                env={k: v for k, v in os.environ.items() if not k.upper().startswith("DSD_")}).returncode
    except Exception as error:
        result.update(exception=type(error).__name__, detail=str(error))
        (folder / "failure.txt").write_text(traceback.format_exc(), encoding="utf-8")
    save(folder / "process.json", result)
    return result


def checked_invoke(arguments, folder, stdout_name, groups, copies):
    prepare.need(all(preserved(group) for group in (*groups, copies)),
                 "Pre-launch preservation or copied identity changed; native execution blocked")
    return invoke(arguments, folder, stdout_name)


def run(build, private, inputs, output):
    output.mkdir(parents=True, exist_ok=False)
    prepare.need(preserved(LIVE), "Imported source changed")
    prepare.need(prepare.sha(inputs / "manifest.json") == INPUT_SHA, "Registered input identity changed")
    analyze.validate_inputs(inputs)
    prepare.need(not subprocess.check_output(["git", "diff", "HEAD", "--", "experiments/nxdn_air_v1"], cwd=ROOT),
                 "Commit harness before execution")
    prepare.need(not subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard", "experiments/nxdn_air_v1"], cwd=ROOT),
                 "Uncommitted harness file")
    prepare.need(not subprocess.check_output(["git", "diff", BASELINE, "--", "upstream", "patches"], cwd=ROOT), "Product baseline changed")
    audit_path = ROOT / "build/nxdn-air-v1-build-audit.json"
    audit_sha = prepare.sha(audit_path)
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    prepare.need(audit["source_and_linkage_pass"], "Source/build audit failed")
    dependencies = audit["dependencies"]; runtime = audit["runtime_files"]
    prepare.need(preserved(dependencies) and preserved(runtime), "Audited source/dependency changed")
    binary = build / "xerax_air_primary.exe"
    prepare.need(prepare.sha(binary) == audit["binary_sha256"], "Audited binary changed")
    original = hashes(inputs) | hashes(private) | hashes(Path(__file__).parent) | dependencies | runtime | LIVE
    original[str(audit_path.resolve())] = audit_sha
    original[str(binary.resolve())] = prepare.sha(binary)
    old_before = ROOT / "build/nxdn-voice-words-v1-run-20260925/before-execution.json"
    protected = json.loads(old_before.read_text(encoding="utf-8"))["protected"].copy()
    additions = {
        "docs/research/evidence/nxdn-voice-words-v1-2026-09-25-raw.zip": "974ee2696bbddfc5bb814a2b951f03318bfc4c3146a9e8422b41f60dae4d9131",
        "build/nxdn-voice-words-v1-run-20260925/report.json": "22e466257755e88281fc84987eb1a44687b9a51d2ac4af66a96fd9ae04df2c8b"}
    for name, digest in additions.items(): protected[str((ROOT / name).resolve())] = digest
    index = ROOT / "docs/research/evidence/nxdn-voice-words-v1-2026-09-25.json"
    protected[str(index.resolve())] = prepare.sha(index)
    prepare.need(preserved(protected), "Earlier release or research changed")
    frozen = output / "frozen"; frozen.mkdir()
    copies = {str((frozen / binary.name).resolve()): audit["binary_sha256"]}
    shutil.copy2(binary, frozen / binary.name)
    for p, digest in runtime.items():
        shutil.copy2(p, frozen / Path(p).name)
        copies[str((frozen / Path(p).name).resolve())] = digest
    for name in ("CMakeCache.txt", "compile_commands.json", "build.ninja", "toolchain.cmake", "xerax_air_primary.map"):
        shutil.copy2(build / name, frozen / name)
    shutil.copytree(private, frozen / "primary")
    shutil.copytree(inputs, output / "inputs")
    for source, destination in ((private, frozen / "primary"), (inputs, output / "inputs")):
        for p in source.rglob("*"):
            if p.is_file(): copies[str((destination / p.relative_to(source)).resolve())] = original[str(p.resolve())]
    inputs = output / "inputs"
    repo_copy = frozen / "source_repository"
    for p in Path(__file__).parent.iterdir():
        if p.is_file():
            target = repo_copy / p.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(p, target)
            copies[str(target.resolve())] = original[str(p.resolve())]
    for name in ("experiments/nxdn_frames/generate_vectors.py", "experiments/nxdn_voice_words_v1/encoding.py",
                 "experiments/nxdn_voice_words_v1/primary_support.cpp"):
        p = ROOT / name; target = repo_copy / name
        target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(p, target)
        original[str(p.resolve())] = prepare.sha(p)
        copies[str(target.resolve())] = original[str(p.resolve())]
    registration = ROOT / "docs/research/NXDN-AIR-V1-PREREGISTRATION-2026-09-25.md"
    original[str(registration.resolve())] = dependencies[str(registration.resolve())]
    shutil.copy2(registration, frozen / registration.name)
    copies[str((frozen / registration.name).resolve())] = original[str(registration.resolve())]
    for pattern in ("nxdn-air-v1-*audit*", "nxdn-air-v1-*review*", "nxdn-air-v1-*.log", "nxdn-air-v1-*-plan.md"):
        for p in (ROOT / "build").glob(pattern):
            if p.is_file():
                original.setdefault(str(p.resolve()), prepare.sha(p))
                shutil.copy2(p, frozen / p.name)
                copies[str((frozen / p.name).resolve())] = original[str(p.resolve())]
    configured = {str(Path(c["file"]).resolve()): prepare.sha(c["file"])
                  for c in json.loads((build / "compile_commands.json").read_text(encoding="utf-8"))}
    files = hashes(output)
    save(output / "before-execution.json", {"utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "receiver_baseline": BASELINE, "frozen_files": files, "original_files": original,
        "copied_identities": copies,
        "configured_sources": configured, "protected": protected, "binary_sha256": prepare.sha(binary),
        "build_audit_sha256": audit_sha})
    report = {"schema": 1, "kind": "nxdn_air_v1", "measurement_pass": False,
              "progression_pass": False, "product_promotion": False, "attempts": []}
    save(output / "report.json", report)
    attempt = output / "primary"
    status = checked_invoke([frozen / binary.name, inputs / "input.records41", attempt / "frames.records96"],
                            attempt, "stdout.json", (files, original, configured, protected, LIVE), copies)
    report["attempts"].append({"stage": "primary", **status}); save(output / "report.json", report)
    if status["exit_code"] == 0:
        report["content"] = analyze.inspect_output(inputs, attempt / "frames.records96", attempt / "stdout.json")
    else:
        report["content"] = {"measurement_pass": False, "quality_pass": False, "pass": False}
    report["preservation_pass"] = all(preserved(g) for g in (files, original, configured, protected, LIVE))
    report["measurement_pass"] = report["preservation_pass"] and report["content"]["measurement_pass"]
    report["progression_pass"] = report["measurement_pass"] and report["content"]["pass"]
    report["files"] = {str(p.relative_to(output)): prepare.sha(p) for p in output.rglob("*")
                       if p.is_file() and p != output / "report.json"}
    save(output / "report.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("build", "private", "inputs", "output"): parser.add_argument(name, type=Path)
    args = parser.parse_args()
    if args.output.exists(): parser.error("Existing result directory is immutable")
    try:
        report = run(*(getattr(args, name).resolve() for name in ("build", "private", "inputs", "output")))
    except Exception as error:
        args.output.mkdir(parents=True, exist_ok=True)
        path = args.output / "report.json"
        report = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        report.update(measurement_pass=False, progression_pass=False, exception=type(error).__name__, detail=str(error))
        save(path, report); (args.output / "failure.txt").write_text(traceback.format_exc(), encoding="utf-8")
    print(json.dumps({k: report.get(k) for k in ("measurement_pass", "progression_pass", "attempts", "detail")}))
    sys.exit(0 if report["measurement_pass"] else 1)
