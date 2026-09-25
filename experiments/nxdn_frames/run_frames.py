"""Preserve one bounded NXDN frame experiment, including negative receiver results.

Usage: python run_frames.py <observer executable> <NEW output directory>
Exit zero means valid measurement evidence, not a passing receiver-quality gate.
No build, retries, decoder tuning, hardware access, or speed test is performed.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

REPO_ROOT = Path(__file__).resolve().parents[2]
TIMEOUT_SECONDS = 300
GENERATOR = "experiments/nxdn_frames/generate_vectors.py"
VALIDATOR = "experiments/nxdn_frames/inspect_frames.py"
VARIANTS = ("valid", "wrong_all_crc", "wrong_lich")
SCENARIOS = ("valid", "bad_crc", "bad_lich", "mixed", "one_fsw", "zero", "random")
VECTOR_NAMES = ("vectors.json",) + tuple(name + ".dibits" for name in VARIANTS)
SOURCE_FILES = (
    "experiments/nxdn_frames/observer.c",
    "experiments/nxdn_frames/side_effect_sinks.c",
    "experiments/nxdn_frames/side_effect_sinks.h",
    "experiments/nxdn_frames/dsp_side_effect_sinks.c",
    "experiments/nxdn_frames/CMakeLists.txt",
    "experiments/nxdn_frames/SCHEMA.md",
    GENERATOR, VALIDATOR,
    "experiments/nxdn_frames/test_generate_vectors.py",
    "experiments/nxdn_frames/test_inspect_frames.py",
    "experiments/nxdn_frames/run_frames.py",
    "experiments/nxdn_frames/test_run_frames.py",
    "docs/research/NXDN-FRAMES-PREREGISTRATION-2026-09-25.md",
    "upstream/dsd-neo/src/protocol/nxdn/nxdn_test_support.h",
    "upstream/dsd-neo/src/protocol/nxdn/nxdn_frame.c",
    "upstream/dsd-neo/src/protocol/nxdn/nxdn_deperm.c",
    "upstream/dsd-neo/src/protocol/nxdn/nxdn_convolution.c",
    "upstream/dsd-neo/src/protocol/nxdn/nxdn_confirm.c",
    "upstream/dsd-neo/src/protocol/nxdn/nxdn_descramble.c",
    "upstream/dsd-neo/src/protocol/nxdn/nxdn_crc.c",
    "upstream/dsd-neo/src/protocol/nxdn/nxdn_dcr_utils.c",
    "upstream/dsd-neo/src/protocol/nxdn/nxdn_enc_class.c",
    "upstream/dsd-neo/src/protocol/nxdn/nxdn_confirm.h",
    "upstream/dsd-neo/src/protocol/nxdn/nxdn_internal.h",
    "upstream/dsd-neo/src/core/util/dsd_misc.c",
    "upstream/dsd-neo/src/core/util/bit_packing.c",
    "upstream/dsd-neo/src/core/frames/dsd_dibit.c",
    "upstream/dsd-neo/src/dsp/dsd_symbol.c",
    "upstream/dsd-neo/src/dsp/dsd_frame_sync.c",
    "upstream/dsd-neo/src/dsp/dsd_filters.c",
    "upstream/dsd-neo/src/dsp/symbol_test_support.h",
    "upstream/dsd-neo/src/dsp/symbol_levels.c",
    "upstream/dsd-neo/src/dsp/frame_sync_level.c",
    "upstream/dsd-neo/src/dsp/frame_sync_profile.c",
    "upstream/dsd-neo/src/dsp/frame_sync_policy.c",
    "upstream/dsd-neo/src/dsp/CMakeLists.txt",
    "upstream/dsd-neo/tests/test_support/frame_sync_state_buffers.h",
    "upstream/dsd-neo/tests/test_support/frame_sync_dsp_stubs.c",
    "upstream/dsd-neo/tests/CMakeLists.txt",
    "upstream/dsd-neo/CMakeLists.txt",
)


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def write_json(path, value):
    with Path(path).open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def git_state(root):
    def git(*args):
        result = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                                check=True, timeout=10, text=True, encoding="utf-8", errors="replace")
        return result.stdout
    head = git("rev-parse", "HEAD").strip()
    if len(head) != 40 or any(char not in "0123456789abcdef" for char in head):
        raise ValueError("Git did not report a full source commit")
    return {"head": head,
            "tracked_repository_dirty": bool(git("status", "--porcelain=v1", "--untracked-files=no").strip()),
            "relevant_status_porcelain": git("status", "--porcelain=v1", "--untracked-files=all", "--", *SOURCE_FILES).splitlines(),
            "scope": "Global tracked dirty flag; only explicitly named experiment input paths are listed. "
                     "Unrelated file contents and untracked paths are not collected."}


def load_entry(source, path, entry):
    # Compile precisely the bytes in the manifest, not a cached import or a
    # second source read. Both frozen modules use only the Python standard lib.
    namespace = {"__name__": "xerax_frozen_frame_" + entry, "__file__": str(path)}
    exec(compile(source, str(path), "exec"), namespace)
    function = namespace.get(entry)
    if not callable(function):
        raise ValueError("Frozen module has no " + entry + " entry point")
    return function


def output_paths(directory):
    names = ["cases.jsonl", "stderr.log", "process.json"]
    names += ["%s-r%d-o%d-c%d.u32le" % (scenario, ramp, offset, chunk)
              for scenario in SCENARIOS for ramp in (8, 14)
              for offset in (range(20) if scenario == "valid" else (0,)) for chunk in (1, 37, 512)]
    names += ["vectors/" + name for name in VECTOR_NAMES]
    return [directory / name for name in names]


def capture_outputs(directory):
    result = {}
    for path in output_paths(directory):
        if path.is_symlink() or path.parent.is_symlink():
            raise ValueError("Output evidence must not be a symlink: " + path.name)
        if path.exists():
            if not path.is_file():
                raise ValueError("Output evidence is not a file: " + path.name)
            result[path.relative_to(directory).as_posix()] = digest(path)
    return result


def run(executable, output_directory, *, repo_root=None):
    root = Path(repo_root if repo_root is not None else REPO_ROOT).resolve()
    executable, directory = Path(executable).resolve(), Path(output_directory).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    vector_dir = directory / "vectors"
    command = [str(executable), str(vector_dir), str(directory)]
    started = time.monotonic_ns()
    report = {"schema": 1, "kind": "nxdn_frame_runner", "status": "failed", "measurement_pass": False,
              "measurement_contract_pass": None, "direct_block_gate_pass": None, "receiver_gate_pass": None,
              "domain": "discriminator_samples", "speed_measurement": False,
              "started_utc": datetime.now(timezone.utc).isoformat(), "command": command,
              "timeout_seconds": TIMEOUT_SECONDS, "platform": None, "python": sys.version,
              "source_git": None, "source_git_after": None, "inputs_before": {}, "inputs_after": {},
              "outputs_before_validation": {}, "outputs_after_validation": {}, "validated_outputs": {},
              "errors": [], "native": {"status": "not_started", "returncode": None}, "analysis": None,
              "limits": ["Exit zero means measurement validity, not a receiver-quality success; inspect receiver_gate_pass.",
                         "Source and binary hashes do not prove an existing executable was built from these sources or record all transitive build inputs.",
                         "Only generated discriminator-domain control decoding is studied, not original IQ, voice, hardware, or speed.",
                         "The subprocess timeout kills and waits for the observer, which does not spawn children.",
                         "Hash checks detect persistent input/output changes; they are not a tamper-proof filesystem snapshot."]}
    frozen, source_bytes, manifest_hashes = {}, {}, {}
    stdout_path, stderr_path = directory / "cases.jsonl", directory / "stderr.log"

    def error(phase, reason):
        report["errors"].append({"phase": phase, "reason": str(reason)})

    def save_manifest(name, value):
        write_json(directory / name, value)
        manifest_hashes[name] = digest(directory / name)

    try:
        report["platform"] = platform.platform()
        report["source_git"] = git_state(root)
        for path in [root / name for name in SOURCE_FILES] + [executable]:
            if not path.is_file():
                raise FileNotFoundError("Required frozen input missing: " + str(path))
            if path in (root / GENERATOR, root / VALIDATOR):
                source_bytes[str(path)] = path.read_bytes()
                frozen[str(path)] = hashlib.sha256(source_bytes[str(path)]).hexdigest()
            else:
                frozen[str(path)] = digest(path)
        manifest = {"schema": 1, "command": command, "source_git": report["source_git"],
                    "platform": report["platform"], "python": report["python"], "inputs": dict(frozen),
                    "domain": report["domain"], "speed_measurement": False}
        save_manifest("source-inputs-before.json", manifest)
        generate = load_entry(source_bytes[str(root / GENERATOR)], root / GENERATOR, "generate")
        analyze = load_entry(source_bytes[str(root / VALIDATOR)], root / VALIDATOR, "analyze")
        generated = generate(vector_dir)
        if generated.get("generator_sha256") != frozen[str(root / GENERATOR)]:
            raise ValueError("Generated manifest reports a different generator source")
        for name, expected in tuple(frozen.items()):
            if digest(name) != expected:
                raise ValueError("Source changed before observer launch: " + name)
        for name in VECTOR_NAMES:
            path = vector_dir / name
            if path.is_symlink() or not path.is_file():
                raise ValueError("Generator did not create a regular fixed vector file: " + name)
            frozen[str(path)] = digest(path)
        manifest["inputs"] = dict(frozen)
        manifest["frozen_utc"] = datetime.now(timezone.utc).isoformat()
        save_manifest("manifest-before.json", manifest)
        report["inputs_before"] = dict(frozen)
        environment = {key: value for key, value in os.environ.items() if not key.upper().startswith("DSD_")}
        with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
            try:
                result = subprocess.run(command, cwd=root, env=environment, stdin=subprocess.DEVNULL,
                                        stdout=stdout, stderr=stderr, timeout=TIMEOUT_SECONDS, check=False)
                report["native"] = {"status": "completed", "returncode": result.returncode}
                if result.returncode != 0:
                    error("native", "nonzero_exit")
            except subprocess.TimeoutExpired as exc:
                report["native"] = {"status": "timeout", "returncode": None}
                error("native", "timeout: " + str(exc))
            except OSError as exc:
                report["native"] = {"status": "launch_failed", "returncode": None}
                error("native", exc)
        write_json(directory / "process.json", report["native"])
        guards = capture_outputs(directory)
        report["outputs_before_validation"] = guards
        try:
            metrics = analyze(stdout_path, directory, vector_dir / "vectors.json")
            report["analysis"] = metrics
            write_json(directory / "analysis.json", metrics)
            for key in ("measurement_contract_pass", "direct_block_gate_pass", "receiver_gate_pass"):
                if type(metrics.get(key)) is not bool:
                    raise ValueError("Inspector lacks a boolean " + key)
                report[key] = metrics[key]
            if not metrics["measurement_contract_pass"] or not metrics["direct_block_gate_pass"]:
                error("analysis", "independent_measurement_gate_failed")
            validated = {"cases.jsonl": metrics["log_sha256"]}
            for table in ("artifact_sha256", "vector_sha256"):
                for name, value in metrics[table].items():
                    path = Path(name).resolve()
                    try:
                        relative = path.relative_to(directory).as_posix()
                    except ValueError as exc:
                        raise ValueError("Inspector returned an external evidence path") from exc
                    if relative not in guards:
                        raise ValueError("Inspector returned an unguarded evidence path")
                    if relative in validated and validated[relative] != value:
                        raise ValueError("Inspector returned contradictory evidence hashes")
                    validated[relative] = value
            expected_vectors = {"vectors/" + name for name in VECTOR_NAMES}
            if not expected_vectors <= set(validated):
                raise ValueError("Inspector did not bind every frozen vector file")
            report["validated_outputs"] = validated
            if any(guards.get(name) != value for name, value in validated.items()):
                error("analysis", "validator_hash_mismatch")
            for name in expected_vectors:
                if validated[name] != frozen[str(directory / name)]:
                    error("analysis", "vector_changed_after_launch")
        except Exception as exc:
            error("analysis", type(exc).__name__ + ": " + str(exc))
        after = capture_outputs(directory)
        report["outputs_after_validation"] = after
        if guards != after:
            error("output_integrity", "output_changed_during_validation")
    except Exception as exc:
        error("driver", type(exc).__name__ + ": " + str(exc))
    finally:
        for path in (stdout_path, stderr_path):
            if not path.exists():
                path.touch(exist_ok=False)
        for name, expected in frozen.items():
            try:
                actual = digest(name)
            except OSError as exc:
                actual = None
                error("input_integrity", exc)
            report["inputs_after"][name] = actual
            if actual != expected:
                error("input_integrity", "frozen_input_changed: " + name)
        report["inputs_before"] = dict(frozen)
        try:
            report["source_git_after"] = git_state(root)
            if report["source_git"] != report["source_git_after"]:
                error("source_integrity", "git_state_changed")
        except Exception as exc:
            error("source_integrity", type(exc).__name__ + ": " + str(exc))
        try:
            final_outputs = capture_outputs(directory)
            prior = report["outputs_after_validation"] or report["outputs_before_validation"]
            if prior and final_outputs != prior:
                error("output_integrity", "output_changed_before_final_report")
            report["output_sha256"] = final_outputs
            if (directory / "analysis.json").is_file():
                report["analysis_sha256"] = digest(directory / "analysis.json")
            report["manifest_sha256"] = manifest_hashes
            for name, expected in manifest_hashes.items():
                if digest(directory / name) != expected:
                    error("input_integrity", "frozen_manifest_changed: " + name)
        except Exception as exc:
            error("output_integrity", type(exc).__name__ + ": " + str(exc))
        report["driver_elapsed_ns"] = time.monotonic_ns() - started
        report["measurement_pass"] = (not report["errors"] and report["native"]["returncode"] == 0
                                      and report["measurement_contract_pass"] is True and report["direct_block_gate_pass"] is True)
        report["status"] = ("measurement_passed_receiver_passed" if report["receiver_gate_pass"] else "measurement_passed_receiver_failed") if report["measurement_pass"] else "failed"
        write_json(directory / "report.json", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("new_output_directory", type=Path)
    args = parser.parse_args(argv)
    try:
        report = run(args.executable, args.new_output_directory)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps({"status": report["status"], "measurement_pass": report["measurement_pass"],
                      "receiver_gate_pass": report["receiver_gate_pass"],
                      "report": str(args.new_output_directory.resolve() / "report.json")}))
    return 0 if report["measurement_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
