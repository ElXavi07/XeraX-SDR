"""One registered finite recovery matrix; retain errors and both policy outcomes."""
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

# Bind the actual imported analysis modules, not only later archival copies.
EXECUTED_SOURCES = {str(p.resolve()): prepare.sha(p) for p in (
    Path(__file__), Path(analyze.__file__), Path(prepare.__file__),
    prepare.ROOT / "experiments/nxdn_engine_gap/analyze.py")}


def unchanged(identities):
    return all(Path(path).is_file() and prepare.sha(path) == digest for path, digest in identities.items())


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def launch(binary, directory, case, inputs, manifest, observed):
    directory.mkdir(parents=True, exist_ok=False)
    result = {"measurement_pass": False, "exit_code": None}
    rows = []
    try:
        waveform = manifest["waveforms"][case["waveform"]]
        args = [str(binary.resolve()), str((inputs / waveform["file"]).resolve()), str(case["fast"]),
                str(case["chunk"]), str(observed), str((directory / "pops.u32le").resolve())]
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith("DSD_")}
        save(directory / "invocation.json", {"arguments": args, "dsd_environment_removed": True})
        with (directory / "events.jsonl").open("wb") as out, (directory / "stderr.txt").open("wb") as err:
            result["exit_code"] = subprocess.run(args, stdout=out, stderr=err, timeout=60, env=env, cwd=directory).returncode
        rows = [json.loads(line) for line in (directory / "events.jsonl").read_text().splitlines()]
        result["audit"] = analyze.inspect(rows, directory / "pops.u32le", case, manifest, inputs, observed)
        prepare.require(result["exit_code"] == 0, f"native exit {result['exit_code']}")
        result["measurement_pass"] = True
    except Exception as error:
        result.update(exception=type(error).__name__, detail=str(error))
        (directory / "failure.txt").write_text(traceback.format_exc(), encoding="utf-8")
    save(directory / "audit.json", result)
    return rows, result


def run(native, anchor, inputs, output):
    output.mkdir(parents=True, exist_ok=False)
    prepare.require(unchanged(EXECUTED_SOURCES), "Live analysis source changed after module import")
    manifest = json.loads((inputs / "manifest.json").read_text())
    prepare.require(len(manifest["cases"]) == 54, "Registered case count differs")
    frozen = output / "frozen"
    frozen.mkdir()
    binary = frozen / ("engine.exe" if os.name == "nt" else "engine")
    shutil.copy2(native, binary)
    if os.name == "nt":
        prepare.require(prepare.sha(binary) == prepare.WINDOWS_BINARY_SHA, "Frozen Windows executable differs")
    for p in native.parent.glob("*.dll"):
        shutil.copy2(p, frozen / p.name)
    # Bind the replay observer to its original build/source records without
    # modifying the old experiment's immutable hash guards.
    for p in (anchor / "frozen").rglob("*"):
        if p.is_file() and p.suffix.lower() not in {".exe", ".dll"}:
            target = frozen / "original-build" / p.relative_to(anchor / "frozen")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, target)
    for p in (prepare.ROOT / "experiments/nxdn_recovery").glob("*.py"):
        shutil.copy2(p, frozen / p.name)
    registration = prepare.ROOT / "docs/research/NXDN-RECOVERY-PREREGISTRATION-2026-09-25.md"
    shutil.copy2(registration, frozen / registration.name)
    frame = prepare.ROOT / "upstream/dsd-neo/src/protocol/nxdn/nxdn_frame.c"
    import hashlib
    prepare.require(hashlib.sha256(frame.read_bytes().replace(b"\r\n", b"\n")).hexdigest() == prepare.FRAME_NORMALIZED_SHA,
                    "Integrated frame differs from frozen candidate")
    source_checked = {}
    for p in (anchor / "frozen/source/upstream/dsd-neo").rglob("*"):
        if not p.is_file() or p.name == "nxdn_frame.c":
            continue
        relative = p.relative_to(anchor / "frozen/source")
        current = prepare.ROOT / relative
        prepare.require(current.is_file() and prepare.sha(current) == prepare.sha(p), "Native source drift: " + str(relative))
        source_checked[str(relative)] = prepare.sha(current)
    shutil.copytree(inputs, output / "inputs")
    inputs = output / "inputs"
    identities = {str(p.relative_to(output)): prepare.sha(p) for p in output.rglob("*") if p.is_file()}
    anchor_expected = {}
    for chunk in (37, 512):
        for fast in (0, 1):
            for obs in (0, 1):
                for name in ("events.jsonl", "pops.u32le"):
                    path = anchor / f"runs/p0-clean_weak-f{fast}-c{chunk}/candidate/{obs}/{name}"
                    anchor_expected[str(path.resolve())] = prepare.sha(path)
    save(output / "before-execution.json", {"utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=prepare.ROOT, text=True).strip(),
        "files": identities, "anchor_reference_hashes": anchor_expected, "native_sources_equal": source_checked,
        "executed_source_hashes": EXECUTED_SOURCES,
        "frame_equal_after_crlf_normalization": True, "binary": prepare.sha(binary)})
    report = {"schema": 1, "kind": "nxdn_recovery", "expected_invocations": 216, "attempts": [],
              "measurement_failures": [], "observer_differences": [], "chunk_differences": [],
              "anchor_differences": [], "measurement_pass": False, "warm_progression_pass": False}
    pairs, observed_rows, observed_traces = {}, {}, {}
    cases = sorted(manifest["cases"], key=lambda c: (not manifest["waveforms"][c["waveform"]]["legacy"], c["id"]))
    for base in cases:
        for fast in (0, 1):
            case = dict(base, fast=fast)
            two_rows, two_results = [], []
            for observed in (0, 1):
                directory = output / "runs" / case["id"] / str(fast) / str(observed)
                rows, result = launch(binary, directory, case, inputs, manifest, observed)
                report["attempts"].append({"id": case["id"], "fast": fast, "observed": observed,
                    "measurement_pass": result["measurement_pass"], "exit_code": result["exit_code"], "detail": result.get("detail")})
                two_rows.append(rows); two_results.append(result)
                if not result["measurement_pass"]:
                    report["measurement_failures"].append(f"{case['id']}/{fast}/{observed}: {result.get('detail')}")
                if manifest["waveforms"][case["waveform"]]["legacy"]:
                    for name in ("events.jsonl", "pops.u32le"):
                        reference = anchor / f"runs/p0-clean_weak-f{fast}-c{case['chunk']}/candidate/{observed}/{name}"
                        if not (directory / name).is_file() or prepare.sha(directory / name) != prepare.sha(reference):
                            report["anchor_differences"].append(f"{case['id']}/{fast}/{observed}/{name}")
                save(output / "report.json", report)
            if all(x["measurement_pass"] for x in two_results):
                if analyze.semantic(two_rows[0]) != analyze.semantic(two_rows[1]):
                    report["observer_differences"].append(f"{case['id']}/{fast}")
                pairs.setdefault(base["id"], {})[fast] = two_results[1]["audit"]
                observed_rows[(base["waveform"], base["chunk"], fast)] = two_rows[1]
                observed_traces[(base["waveform"], base["chunk"], fast)] = (output / "runs" / base["id"] / str(fast) / "1/pops.u32le").read_bytes()
    for waveform in manifest["waveforms"]:
        for fast in (0, 1):
            a, b = (waveform, 37, fast), (waveform, 512, fast)
            if a in observed_rows and b in observed_rows:
                ignored = {"provided", "cache_pos", "cache_len", "read_start", "chunk"}
                normalized = lambda rows: [{k: v for k, v in row.items() if k not in ignored} for row in rows]
                if normalized(observed_rows[a]) != normalized(observed_rows[b]) or observed_traces[a] != observed_traces[b]:
                    report["chunk_differences"].append(f"{waveform}/{fast}")
    report["quality"] = analyze.compare(pairs, manifest)
    report["executed_sources_preserved"] = unchanged(EXECUTED_SOURCES)
    report["preservation_pass"] = (unchanged({str(output / name): digest for name, digest in identities.items()})
        and unchanged(anchor_expected) and report["executed_sources_preserved"])
    report["measurement_pass"] = (report["preservation_pass"] and len(report["attempts"]) == 216
        and not report["measurement_failures"] and not report["observer_differences"]
        and not report["anchor_differences"] and not report["chunk_differences"])
    report["warm_progression_pass"] = (report["measurement_pass"] and not report["chunk_differences"]
        and report["quality"].get("progression_pass", False))
    report["files"] = {str(p.relative_to(output)): prepare.sha(p) for p in output.rglob("*") if p.is_file() and p != output / "report.json"}
    save(output / "report.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("native", "anchor", "inputs", "output"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output exists; never replace a completed or failed matrix")
    try:
        report = run(args.native, args.anchor, args.inputs, args.output)
    except Exception as error:
        args.output.mkdir(parents=True, exist_ok=True)
        path = args.output / "report.json"
        report = json.loads(path.read_text()) if path.exists() else {}
        report.update(measurement_pass=False, warm_progression_pass=False, exception=type(error).__name__, detail=str(error))
        save(path, report); (args.output / "failure.txt").write_text(traceback.format_exc(), encoding="utf-8")
    print(json.dumps({k: report.get(k) for k in ("measurement_pass", "warm_progression_pass", "measurement_failures", "observer_differences", "chunk_differences", "anchor_differences", "detail")}))
    sys.exit(0 if report["measurement_pass"] else 1)
