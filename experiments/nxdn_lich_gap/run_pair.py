"""Preserve and execute one bounded pair; retain negative results separately from invalid measurements."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import traceback

import prepare


def oracle(sequence, baseline=False):
    confirmed = streak = evidence = 0
    rows = []
    for kind in sequence:
        if kind == "R":
            confirmed = streak = evidence = 0
            result = -1
        elif kind in "PUD" and baseline:
            result = confirmed
        else:
            evidence = 2 if kind == "S" else 1 if kind == "W" else 0
            if evidence == 2:
                confirmed, streak = 1, 0
            elif evidence == 1:
                streak += 1
                confirmed |= streak >= 2
            else:
                streak = 0
            result = 2 if confirmed and evidence else confirmed
        rows.append({"confirmed": int(confirmed), "streak": streak, "evidence": evidence,
                     "proved": int(bool(confirmed and evidence)), "result": int(result)})
    return rows


def check_rows(rows, manifest, vector_dir, role):
    failures, contract_deviations, transition_deviations, behavior_deviations = [], [], [], []
    expected_count = 4 * sum(len(s) for s in prepare.SEQUENCES.values())
    if len(rows) != expected_count:
        failures.append(f"row count {len(rows)} != {expected_count}")
    index = {}
    for row in rows:
        key = row["payload"], row["observed"], row["sequence"], row["step"]
        if key in index:
            failures.append(f"duplicate row {key}")
        index[key] = row
    for payload in range(2):
        for name, sequence in prepare.SEQUENCES.items():
            expected = oracle(sequence)
            implementation = oracle(sequence, role == "baseline")
            for step, kind in enumerate(sequence):
                observed_pair = []
                for enabled in range(2):
                    key = payload, enabled, name, step
                    row = index.get(key)
                    if row is None:
                        failures.append(f"missing {key}"); continue
                    prefix = str(key)
                    def require(condition, message):
                        if not condition:
                            failures.append(f"{prefix}: {message}")
                    require(row["kind"] == kind, "wrong kind")
                    require(row["errors"] == 0 and row["voice"] == 0, "side-effect or read error")
                    count = 0 if kind == "R" else 8 if kind in "PUD" else 182
                    require(row["consumed"] == count, "wrong body consumption")
                    if kind != "R":
                        data = (vector_dir / f"{payload}-{kind}.dibits").read_bytes()
                        meta = manifest["vectors"][f"{payload}-{kind}.dibits"]
                        require(prepare.sha(vector_dir / f"{payload}-{kind}.dibits") == meta["sha256"], "vector mutated")
                        require(row["read_dibits"] == "".join(map(str, data[10:10 + count])), "input trace mismatch")
                    else:
                        require(row["read_dibits"] == "", "reset consumed data")
                    if enabled and any(row[field] != value for field, value in implementation[step].items()):
                        transition_deviations.append({"payload": payload, "sequence": name, "step": step,
                            "predicted": implementation[step], "actual": {f: row[f] for f in implementation[step]}})
                    if enabled and any(row[field] != value for field, value in expected[step].items()):
                        contract_deviations.append({"payload": payload, "sequence": name, "step": step,
                                                    "expected": expected[step], "actual": {f: row[f] for f in expected[step]}})
                    should_hold = kind in "WSC" and bool(row["confirmed"])
                    if row["clock_changed"] != int(should_hold) or row["mono_changed"] != int(should_hold):
                        behavior_deviations.append(f"{prefix}: scanner clock contract")
                    if kind != "R" and row["carrier"] != int(kind not in "PUD"):
                        behavior_deviations.append(f"{prefix}: carrier gate")
                    events = row["events"]
                    need = 3 if enabled and kind in "WSC" else 0
                    require(len(events) == need, "CRC event count")
                    if need and len(events) == 3:
                        for event, channel, part, channel_name in zip(events, (1, 2, 2), (0, 1, 2), ("sacch", "facch", "facch")):
                            truth = meta[channel_name]
                            require((event["channel"], event["part"]) == (channel, part), "CRC identity")
                            require(event["bits"] == truth["information_bits"], "decoded information mismatch")
                            require(event["computed"] == truth["computed_crc"] and event["received"] == truth["transmitted_crc"], "CRC value mismatch")
                            require(bool(event["soft_pass"]) == truth["crc_expected_pass"], "soft CRC verdict mismatch")
                            require(bool(event["fallback"]) == (not truth["crc_expected_pass"]), "fallback mismatch")
                    observed_pair.append({k: v for k, v in row.items() if k not in ("observed", "events")})
                if len(observed_pair) == 2 and observed_pair[0] != observed_pair[1]:
                    failures.append(f"observer changed outcome {payload}/{name}/{step}")
    return {"measurement_pass": not failures, "failures": failures, "contract_deviations": contract_deviations,
            "predicted_transition_deviations": transition_deviations, "behavior_deviations": behavior_deviations}


def execute_role(binary, output, role, manifest):
    phase = "launch"
    exit_code = None
    try:
        with (output / f"{role}.jsonl").open("wb") as out, (output / f"{role}.stderr").open("wb") as err:
            completed = subprocess.run([str(binary.resolve()), str((output / "vectors").resolve())], stdout=out, stderr=err, timeout=60)
        exit_code = completed.returncode
        phase = "parse"
        rows = [json.loads(line) for line in (output / f"{role}.jsonl").read_text().splitlines()]
        phase = "inspect"
        result = check_rows(rows, manifest, output / "vectors", role)
        result["exit_code"] = exit_code
        result["measurement_pass"] &= exit_code == 0
        if exit_code:
            result["failures"].append(f"native exit {exit_code}")
        return rows, result
    except Exception as error:
        return [], {"measurement_pass": False, "exit_code": exit_code,
                    "phase": phase, "exception": type(error).__name__, "detail": str(error),
                    "failures": [f"{phase}: {type(error).__name__}: {error}"],
                    "contract_deviations": [], "behavior_deviations": [], "predicted_transition_deviations": []}


def run(baseline, candidate, build_inputs, output):
    output.mkdir(parents=True, exist_ok=False)
    manifest = prepare.prepare(output / "vectors")
    if prepare.sha(build_inputs / "nxdn_frame_candidate.c") != manifest["candidate_sha256"]:
        raise ValueError("Compiled candidate source does not match declared patch")
    frozen = output / "frozen"
    frozen.mkdir()
    for file in (prepare.ROOT / "experiments/nxdn_lich_gap").glob("*"):
        if file.is_file():
            shutil.copyfile(file, frozen / file.name)
    for file in (prepare.FRAME, prepare.ENCODER, prepare.ROOT / "upstream/dsd-neo/src/protocol/nxdn/nxdn_confirm.c",
                 prepare.ROOT / "upstream/dsd-neo/src/protocol/nxdn/nxdn_deperm.c"):
        shutil.copyfile(file, frozen / file.name)
    snapshots = {}
    for role, binary in (("baseline", baseline), ("candidate", candidate)):
        destination = frozen / (role + binary.suffix)
        shutil.copy2(binary, destination)
        snapshots[role] = destination
    # Write identities before either native executable can run.
    identities = {str(p.relative_to(output)): prepare.sha(p) for p in output.rglob("*") if p.is_file()}
    (output / "before-execution.json").write_text(json.dumps({"utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=prepare.ROOT, text=True).strip(),
        "inputs": identities}, indent=2) + "\n")
    report = {"schema": 1, "kind": "nxdn_lich_gap", "roles": {}}
    all_rows = {}
    for role, binary in snapshots.items():
        rows, result = execute_role(binary, output, role, manifest)
        all_rows[role] = rows
        report["roles"][role] = result
        # A later failure cannot erase the outcome of a completed role.
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    differences = []
    for before, after in zip(all_rows["baseline"], all_rows["candidate"]):
        # Channel outputs, source consumption and CRCs must be unchanged.
        for key in ("payload", "observed", "sequence", "step", "kind", "consumed", "read_dibits", "events", "voice", "errors", "content"):
            if before[key] != after[key]:
                differences.append(f"{before['payload']}/{before['sequence']}/{before['step']}/{key}")
    bridged = [r for r in all_rows["baseline"] if r["observed"] and r["sequence"] in ("parity_gap", "unsupported_gap", "direction_gap")
               and r["step"] == 2 and r["confirmed"] == 1]
    post = {str(p.relative_to(output)): prepare.sha(p) for p in output.rglob("*") if p.is_file() and p != output / "report.json"}
    report["preservation_pass"] = all(post.get(k) == v for k, v in identities.items()) and prepare.sha(prepare.FRAME) == manifest["frame_source_sha256"]
    report["channel_differences"] = differences
    report["baseline_bridges"] = len(bridged)
    report["measurement_pass"] = report["preservation_pass"] and not differences and all(r["measurement_pass"] for r in report["roles"].values())
    report["progression_pass"] = (report["measurement_pass"] and len(bridged) == 6
        and not report["roles"]["candidate"]["contract_deviations"]
        and not report["roles"]["baseline"]["predicted_transition_deviations"]
        and not any(r["behavior_deviations"] for r in report["roles"].values()))
    report["files"] = post
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("baseline", "candidate", "build_inputs", "output"):
        parser.add_argument(arg, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output already exists; never replace an attempted experiment")
    try:
        report = run(args.baseline, args.candidate, args.build_inputs, args.output)
    except Exception as error:
        path = args.output / "report.json"
        report = json.loads(path.read_text()) if path.exists() else {"schema": 1, "roles": {}}
        report.update({"measurement_pass": False, "progression_pass": False, "baseline_bridges": 0,
                       "channel_differences": [], "exception": type(error).__name__, "detail": str(error)})
        args.output.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2) + "\n")
        (args.output / "failure.txt").write_text(traceback.format_exc())
    print(json.dumps({k: report[k] for k in ("measurement_pass", "progression_pass", "baseline_bridges", "channel_differences")}))
    sys.exit(0 if report["measurement_pass"] else 1)
