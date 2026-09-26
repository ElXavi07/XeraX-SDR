"""Freeze and execute the registered clear-word study, with no favorable retry."""
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
BASELINE = "e8498d298ad1a6f85da93a8b07730ec99f7c1416"
INPUT_MANIFEST = "4d31e3d17c56162b706f9187f8f000bfbb0fce0f1e353f9ee2519bd66e355a84"
LIVE = {str(Path(p).resolve()): prepare.sha(p) for p in (__file__, analyze.__file__, prepare.__file__)}


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def hashes(folder):
    return {str(p.resolve()): prepare.sha(p) for p in folder.rglob("*") if p.is_file() and "__pycache__" not in p.parts}


def preserved(group):
    return all(Path(p).is_file() and prepare.sha(p) == digest for p, digest in group.items())


def invoke(arguments, folder, stdout_name):
    """Reserve one attempt and retain all partial output, including on failure."""
    folder.mkdir(parents=True, exist_ok=False)
    save(folder / "invocation.json", {"arguments": [str(p) for p in arguments],
         "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
         "timeout_seconds": 120, "dsd_environment_removed": True})
    result = {"exit_code": None}
    try:
        with (folder / stdout_name).open("wb") as out, (folder / "stderr.txt").open("wb") as err:
            result["exit_code"] = subprocess.run([str(p) for p in arguments], cwd=folder,
                stdout=out, stderr=err, timeout=120,
                env={k: v for k, v in os.environ.items() if not k.upper().startswith("DSD_")}).returncode
    except Exception as error:
        result.update(exception=type(error).__name__, detail=str(error))
        (folder / "failure.txt").write_text(traceback.format_exc(), encoding="utf-8")
    save(folder / "process.json", result)
    return result


def run(build, primary, inputs, output):
    # Even a preparation failure is immutable evidence. No existing folder is reused.
    output.mkdir(parents=True, exist_ok=False)
    prepare.need(preserved(LIVE), "Imported source changed")
    prepare.need(prepare.sha(inputs / "manifest.json") == INPUT_MANIFEST, "Registered inputs changed")
    analyze.validate_inputs(inputs)
    prepare.verify_primary(primary)
    prepare.need(not subprocess.check_output(["git", "diff", "HEAD", "--", "experiments/nxdn_voice_words_v1"], cwd=ROOT),
                 "Commit harness before execution")
    prepare.need(not subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard",
                 "experiments/nxdn_voice_words_v1"], cwd=ROOT), "Uncommitted harness file")
    prepare.need(not subprocess.check_output(["git", "diff", BASELINE, "--", "upstream", "patches"], cwd=ROOT),
                 "Product baseline changed")
    audit_path = ROOT / "build/nxdn-voice-words-v1-preflight-audit.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    prepare.need(audit["source_and_linkage_pass"] and audit["corpus_pass"], "Independent preflight failed")
    dependencies = audit["dependencies"]
    runtime = audit["runtime_files"]
    prepare.need(preserved(dependencies) and preserved(runtime), "Audited dependency changed")
    binaries = {name: build / ("xerax_voice_" + name + ".exe") for name in ("primary", "probe")}
    prepare.need(all(prepare.sha(p) == audit["binary_hashes"][name] for name, p in binaries.items()), "Audited binary changed")
    original = hashes(inputs) | hashes(primary) | hashes(Path(__file__).parent) | dependencies | runtime | LIVE
    original |= {str(p.resolve()): prepare.sha(p) for p in binaries.values()}
    old = json.loads((ROOT / "build/nxdn-boundary-v1-pair-20260925/before-execution.json").read_text(encoding="utf-8"))
    protected = old["protected"].copy()
    for name in ("docs/research/evidence/nxdn-boundary-v1-2026-09-25-raw.zip",
                 "docs/research/evidence/nxdn-boundary-v1-2026-09-25.json",
                 "build/nxdn-boundary-v1-pair-20260925/report.json"):
        p = ROOT / name; protected[str(p.resolve())] = prepare.sha(p)
    prepare.need(preserved(protected), "Earlier release or experiment changed")
    frozen = output / "frozen"; frozen.mkdir()
    for name, p in binaries.items():
        shutil.copy2(p, frozen / p.name)
        shutil.copy2(build / (p.stem + ".map"), frozen / (p.stem + ".map"))
    for p in runtime:
        shutil.copy2(p, frozen / Path(p).name)
    for name in ("CMakeCache.txt", "compile_commands.json", "build.ninja", "toolchain.cmake"):
        shutil.copy2(build / name, frozen / name)
    shutil.copytree(primary, frozen / "primary-sources")
    shutil.copytree(inputs, output / "inputs"); inputs = output / "inputs"
    source_target = frozen / "harness"; source_target.mkdir()
    for p in Path(__file__).parent.iterdir():
        if p.is_file(): shutil.copy2(p, source_target / p.name)
    # Copy the actual linked codec and installed metadata/header. No stub is linked.
    codec = frozen / "codec"; codec.mkdir()
    for index, p in enumerate(sorted(dependencies)):
        # Compiler/audit tools are identified and preserved by hash; do not
        # redistribute whole toolchains in the result archive.
        if Path(p).suffix.lower() != ".exe":
            shutil.copy2(p, codec / (str(index) + "-" + Path(p).name))
    shutil.copytree(ROOT / "build/nxdn-observation-v2-dependencies/mbe-neo-metadata", codec / "metadata")
    shutil.copy2(ROOT / "build/nxdn-observation-v2-dependencies/identity.json", codec / "earlier-identity.json")
    registration = ROOT / "docs/research/NXDN-VOICE-WORDS-V1-PREREGISTRATION-2026-09-25.md"
    shutil.copy2(registration, frozen / registration.name)
    for pattern in ("nxdn-voice-words-v1-*audit*", "nxdn-voice-words-v1-*.log",
                    "nxdn-voice-v1-*-review.md"):
        for p in (ROOT / "build").glob(pattern):
            if p.is_file(): shutil.copy2(p, frozen / p.name)
    configured = {}
    for command in json.loads((build / "compile_commands.json").read_text(encoding="utf-8")):
        p = Path(command["file"])
        configured[str(p.resolve())] = prepare.sha(p)
    files = hashes(output)
    save(output / "before-execution.json", {"utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "baseline": BASELINE, "frozen_files": files, "original_files": original,
        "configured_sources": configured, "protected": protected,
        "binaries": audit["binary_hashes"], "preflight_sha256": prepare.sha(audit_path)})
    report = {"schema": 1, "kind": "nxdn_voice_words_v1", "measurement_pass": False,
              "progression_pass": False, "product_promotion": False, "attempts": []}
    save(output / "report.json", report)
    primary_dir = output / "primary"
    primary_channel = primary_dir / "channels9.bin"
    first = invoke([frozen / binaries["primary"].name, inputs / "input.pairs13", primary_channel],
                   primary_dir, "stdout.json")
    report["attempts"].append({"stage": "primary", **first})
    save(output / "report.json", report)
    if first["exit_code"] == 0:
        report["primary"] = analyze.inspect_primary(inputs, primary_channel, primary_dir / "stdout.json")
    else:
        report["primary"] = {"measurement_pass": False, "quality_pass": False, "pass": False}
    save(output / "report.json", report)
    if report["primary"]["pass"]:
        prepare.need(all(preserved(g) for g in (files, original, configured, protected, LIVE)),
                     "Frozen evidence changed after primary; probe blocked")
        # This newly agreed channel file is frozen before the sole decoder batch.
        save(output / "before-probe.json", {"channel_sha256": prepare.sha(primary_channel),
            "channel_bytes": primary_channel.stat().st_size,
            "binary_sha256": audit["binary_hashes"]["probe"],
            "primary_audit": report["primary"], "expected_calls": 27044})
        files[str(primary_channel.resolve())] = prepare.sha(primary_channel)
        second = invoke([frozen / binaries["probe"].name, primary_channel], output / "probe", "rows.jsonl")
        report["attempts"].append({"stage": "probe", **second})
        save(output / "report.json", report)
        if second["exit_code"] == 0:
            report["probe"] = analyze.inspect_probe(inputs, primary_channel, output / "probe/rows.jsonl")
        else:
            report["probe"] = {"measurement_pass": False, "quality_pass": False, "pass": False}
    else:
        report["probe"] = {"skipped": True, "reason": "Primary encoder agreement gate failed", "pass": False}
    report["preservation_pass"] = all(preserved(g) for g in (files, original, configured, protected, LIVE))
    report["measurement_pass"] = report["preservation_pass"] and report["primary"]["measurement_pass"] and (
        report["probe"].get("skipped", False) or report["probe"].get("measurement_pass", False))
    report["progression_pass"] = report["measurement_pass"] and report["primary"]["pass"] and report["probe"]["pass"]
    report["files"] = {str(p.relative_to(output)): prepare.sha(p) for p in output.rglob("*")
                       if p.is_file() and p != output / "report.json"}
    save(output / "report.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("build", "primary", "inputs", "output"): parser.add_argument(name, type=Path)
    args = parser.parse_args()
    if args.output.exists(): parser.error("Existing result directory is immutable")
    try:
        report = run(*(getattr(args, name).resolve() for name in ("build", "primary", "inputs", "output")))
    except Exception as error:
        args.output.mkdir(parents=True, exist_ok=True)
        p = args.output / "report.json"
        report = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        report.update(measurement_pass=False, progression_pass=False, exception=type(error).__name__, detail=str(error))
        save(p, report); (args.output / "failure.txt").write_text(traceback.format_exc(), encoding="utf-8")
    print(json.dumps({k: report.get(k) for k in ("measurement_pass", "progression_pass", "attempts", "detail")}))
    sys.exit(0 if report["measurement_pass"] else 1)
