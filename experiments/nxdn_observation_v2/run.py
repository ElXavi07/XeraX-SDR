"""Execute the registered 36 observation-only cases once and retain all failures."""
import argparse
import copy
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

EXTRAS = {"lich", "scch", "voice_begin", "voice_end", "mbe_begin", "mbe_end", "audio_begin", "audio_end"}
LIVE = {str(Path(p).resolve()): prepare.sha(p) for p in (__file__, analyze.__file__, prepare.__file__)}


def save(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def preserved(hashes):
    return all(Path(p).is_file() and prepare.sha(p) == digest for p, digest in hashes.items())


def anchor_projection(old, new):
    """Only new telemetry and explicitly unavailable EOF positions may differ."""
    try:
        return project_anchor(old, new)
    except (KeyError, TypeError, ValueError, IndexError):
        # A malformed trace fails this gate without preventing remaining attempts.
        return False


def project_anchor(old, new):
    previous = copy.deepcopy(old)
    projected = [copy.deepcopy(r) for r in new if r["kind"] not in EXTRAS]
    if len(previous) != len(projected):
        return False
    for number, (a, b) in enumerate(zip(previous, projected)):
        b["seq"] = number
        if b["kind"] == "configuration":
            for key in ("observation_schema", "datascope", "pulse_digi_rate_out", "floating_point", "dmr_stereo"):
                b.pop(key, None)
        if b["kind"] == "summary":
            for key in tuple(b):
                if key.startswith("v2_"):
                    b.pop(key)
        if b["kind"] == "frame_end":
            calls = b.pop("body_calls")
            if len(calls) != len(b["body_positions"]) or len(calls) != len(a.get("body_positions", [])):
                return False
            for i, call in enumerate(calls):
                if b["body_positions"][i] == 0:
                    if not call["eof_after"] or call["symbol_after"] != call["symbol_before"]:
                        return False
                    a["body_positions"][i] = 0
        if a != b:
            return False
    return True


def invoke(binary, folder, case, inputs, manifest, enabled):
    folder.mkdir(parents=True, exist_ok=False)
    result, rows = {"measurement_pass": False, "exit_code": None}, []
    try:
        args = [str(binary.resolve()), str((inputs / manifest["waveforms"][case["waveform"]]["file"]).resolve()),
                "0", str(case["chunk"]), str(enabled), str((folder / "pops.u32le").resolve())]
        save(folder / "invocation.json", {"arguments": args, "dsd_environment_removed": True})
        with (folder / "events.jsonl").open("wb") as out, (folder / "stderr.txt").open("wb") as err:
            result["exit_code"] = subprocess.run(args, stdout=out, stderr=err, cwd=folder, timeout=60,
                env={k: v for k, v in os.environ.items() if not k.upper().startswith("DSD_")}).returncode
        rows = [json.loads(line) for line in (folder / "events.jsonl").read_text().splitlines()]
        result["audit"] = analyze.inspect(rows, folder / "pops.u32le", case, manifest, inputs, enabled)
        prepare.require(result["exit_code"] == 0, "Nonzero native exit")
        result["measurement_pass"] = True
    except Exception as error:
        result.update(exception=type(error).__name__, detail=str(error))
        (folder / "failure.txt").write_text(traceback.format_exc(), encoding="utf-8")
    save(folder / "audit.json", result)
    return rows, result


def run(build, parent, inputs, output):
    output.mkdir(parents=True, exist_ok=False)
    prepare.require(preserved(LIVE), "Imported execution script changed")
    manifest = json.loads((inputs / "manifest.json").read_text())
    prepare.require(len(manifest["cases"]) == 18, "Registered grid changed")
    frozen = output / "frozen"; frozen.mkdir()
    binary = frozen / "engine.exe"
    shutil.copy2(build / "xerax_nxdn_observation_v2.exe", binary)
    for p in build.glob("*.dll"):
        shutil.copy2(p, frozen / p.name)
    for name in ("CMakeCache.txt", "compile_commands.json", "build.ninja", "observation.map", "toolchain.cmake"):
        shutil.copy2(build / name, frozen / name)
    shutil.copytree(build / "generated", frozen / "generated")
    for p in Path(__file__).parent.iterdir():
        if p.is_file():
            shutil.copy2(p, frozen / p.name)
    registration = prepare.ROOT / "docs/research/NXDN-OBSERVATION-V2-PREREGISTRATION-2026-09-25.md"
    shutil.copy2(registration, frozen / registration.name)
    compiled_sources = {}
    for command in json.loads((build / "compile_commands.json").read_text()):
        p = Path(command["file"])
        if p.is_file():
            compiled_sources[str(p.resolve())] = prepare.sha(p)
    prepare.require(not subprocess.check_output(["git", "diff", "938c5fe", "--", "upstream"], cwd=prepare.ROOT),
                    "Product sources changed against the frozen baseline")
    shutil.copytree(inputs, output / "inputs"); inputs = output / "inputs"
    anchors = {}
    for case in manifest["cases"]:
        if not manifest["waveforms"][case["waveform"]].get("anchor_waveform"):
            continue
        for enabled in (0, 1):
            for name in ("events.jsonl", "pops.u32le"):
                path = parent / "runs" / case["id"] / "0" / str(enabled) / name
                anchors[str(path.resolve())] = prepare.sha(path)
                target = frozen / "anchor-reference" / case["id"] / str(enabled) / name
                target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, target)
    files = {str(p.resolve()): prepare.sha(p) for p in output.rglob("*") if p.is_file()}
    save(output / "before-execution.json", {"utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=prepare.ROOT, text=True).strip(),
        "frozen_files": files, "executed_sources": LIVE, "configured_source_hashes": compiled_sources, "anchors": anchors,
        "source_hash_scope": "Existing source paths in compile_commands; includes configured targets not built for this experiment.",
        "binary_sha256": prepare.sha(binary)})
    report = {"kind": "nxdn_observation_v2", "attempts": [], "measurement_failures": [], "anchor_differences": [],
              "measurement_pass": False, "product_or_recovery_improvement_claim": False}
    pairs = {}
    for case in manifest["cases"]:
        for enabled in (0, 1):
            folder = output / "runs" / case["id"] / str(enabled)
            rows, result = invoke(binary, folder, case, inputs, manifest, enabled)
            report["attempts"].append({"id": case["id"], "observed": enabled, "exit_code": result["exit_code"],
                "measurement_pass": result["measurement_pass"], "detail": result.get("detail")})
            if result["measurement_pass"]:
                pairs.setdefault(case["id"], {})[enabled] = result["audit"]
            else:
                report["measurement_failures"].append(f"{case['id']}/{enabled}: {result.get('detail')}")
            if manifest["waveforms"][case["waveform"]].get("anchor_waveform"):
                ref = frozen / "anchor-reference" / case["id"] / str(enabled)
                old = [json.loads(line) for line in (ref / "events.jsonl").read_text().splitlines()]
                if not anchor_projection(old, rows):
                    report["anchor_differences"].append(case["id"] + f"/{enabled}/events")
                if not (folder / "pops.u32le").is_file() or prepare.sha(folder / "pops.u32le") != prepare.sha(ref / "pops.u32le"):
                    report["anchor_differences"].append(case["id"] + f"/{enabled}/trace")
            save(output / "report.json", report)
    report["contract"] = analyze.compare(pairs, manifest)
    report["preservation_pass"] = all(preserved(group) for group in (files, LIVE, compiled_sources, anchors))
    report["measurement_pass"] = (len(report["attempts"]) == 36 and report["preservation_pass"]
        and not report["measurement_failures"] and not report["anchor_differences"]
        and report["contract"].get("measurement_pass", False))
    report["files"] = {str(p.relative_to(output)): prepare.sha(p) for p in output.rglob("*")
                       if p.is_file() and p != output / "report.json"}
    save(output / "report.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("build", "parent", "inputs", "output"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Existing result directory is immutable")
    try:
        report = run(args.build, args.parent, args.inputs, args.output)
    except Exception as error:
        args.output.mkdir(parents=True, exist_ok=True)
        path = args.output / "report.json"
        report = json.loads(path.read_text()) if path.exists() else {}
        report.update(measurement_pass=False, exception=type(error).__name__, detail=str(error))
        save(path, report); (args.output / "failure.txt").write_text(traceback.format_exc(), encoding="utf-8")
    print(json.dumps({k: report.get(k) for k in ("measurement_pass", "measurement_failures", "anchor_differences", "detail")}))
    sys.exit(0 if report["measurement_pass"] else 1)
