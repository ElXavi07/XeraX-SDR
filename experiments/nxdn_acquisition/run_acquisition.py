"""One bounded correctness run with frozen inputs and retained failure evidence.

Usage: python run_acquisition.py <observer executable> <new output directory>
This does not build the executable or measure radio/performance superiority.
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
VALIDATOR = "experiments/nxdn_acquisition/inspect_acquisition.py"
SOURCE_FILES = (
    "experiments/nxdn_acquisition/observer.c",
    VALIDATOR,
    "experiments/nxdn_acquisition/test_inspect_acquisition.py",
    "experiments/nxdn_acquisition/run_acquisition.py",
    "experiments/nxdn_acquisition/test_run_acquisition.py",
    "docs/research/NXDN-ACQUISITION-PREREGISTRATION-2026-09-25.md",
    "upstream/dsd-neo/src/dsp/dsd_symbol.c",
    "upstream/dsd-neo/src/dsp/symbol_test_support.h",
    "upstream/dsd-neo/src/dsp/CMakeLists.txt",
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
    # Closing the context propagates write/close errors instead of reporting a
    # successful experiment whose evidence did not reach the filesystem.
    with Path(path).open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def git_state(root):
    def git(*args):
        result = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                                check=True, timeout=10, text=True, encoding="utf-8", errors="replace")
        return result.stdout
    head = git("rev-parse", "HEAD").strip()
    if len(head) != 40 or any(c not in "0123456789abcdef" for c in head):
        raise ValueError("Git did not report a full source commit")
    tracked_dirty = bool(git("status", "--porcelain=v1", "--untracked-files=no").strip())
    relevant = git("status", "--porcelain=v1", "--untracked-files=all", "--", *SOURCE_FILES)
    return {"head": head, "tracked_repository_dirty": tracked_dirty,
            "relevant_status_porcelain": relevant.splitlines(),
            "scope": "Global tracked dirty flag; only explicit research-input paths are listed. "
                     "Unrelated untracked paths and file contents are not collected."}


def load_analyzer(source, path):
    # Execute exactly the bytes frozen in the manifest, not an earlier imported
    # module or a second path read that might contain different source.
    namespace = {"__name__": "xerax_frozen_acquisition_validator", "__file__": str(path)}
    exec(compile(source, str(path), "exec"), namespace)
    analyze = namespace.get("analyze")
    if not callable(analyze):
        raise ValueError("Frozen validator has no analyze entry point")
    return analyze


def output_paths(directory):
    # The harness's finite public output names only; never recurse through an
    # arbitrary output directory or hash unrelated/private files.
    names = ["cases.jsonl", "stderr.log", "process.json"]
    names += ["r%d-o%d-c%d.u32le" % (ramp, offset, chunk)
              for ramp in (8, 14) for offset in range(20) for chunk in (1, 37, 512)]
    return [directory / name for name in names]


def capture_outputs(directory):
    result = {}
    for path in output_paths(directory):
        if path.is_symlink():
            raise ValueError("Output artifact cannot be a symlink: " + path.name)
        if path.exists():
            if not path.is_file():
                raise ValueError("Output artifact is not a file: " + path.name)
            result[path.name] = digest(path)
    return result


def run(executable, output_directory, *, repo_root=None):
    root = Path(repo_root if repo_root is not None else REPO_ROOT).resolve()
    executable = Path(executable).resolve()
    directory = Path(output_directory).resolve()
    # Atomic admission: an existing directory/file is always refused, including
    # empty directories. Its previous contents are never overwritten or removed.
    directory.mkdir(parents=True, exist_ok=False)
    command = [str(executable), str(directory)]
    started = time.monotonic_ns()
    report = {"schema": 1, "kind": "acquisition_runner", "status": "failed", "gate_pass": False,
              "domain": "discriminator_samples", "speed_measurement": False,
              "started_utc": datetime.now(timezone.utc).isoformat(), "command": command,
              "timeout_seconds": TIMEOUT_SECONDS, "platform": None,
              "python": sys.version, "source_git": None, "source_git_after": None,
              "inputs_before": {}, "inputs_after": {}, "outputs_before_validation": {},
              "outputs_after_validation": {}, "validated_outputs": {}, "errors": [],
              "native": {"status": "not_started", "returncode": None}, "analysis": None,
              "limits": ["This driver executes an existing binary; it does not prove the binary was built "
                         "from the recorded source or capture its transitive compiler/library inputs.",
                         "Only the declared discriminator correctness and invariance gates are evaluated.",
                         "Subprocess timeout kills/waits for the observer process; this observer does not spawn children.",
                         "Final hashes detect persistent file changes; they are not a tamper-proof filesystem snapshot."]}
    frozen = {}
    validator_source = None

    def error(phase, reason):
        report["errors"].append({"phase": phase, "reason": str(reason)})

    stdout_path, stderr_path = directory / "cases.jsonl", directory / "stderr.log"
    try:
        # Platform inspection may invoke an OS helper and can fail. Keep it
        # inside evidence preservation just like source/launch inspection.
        report["platform"] = platform.platform()
        report["source_git"] = git_state(root)
        paths = [root / name for name in SOURCE_FILES] + [executable]
        for path in paths:
            if not path.is_file():
                raise FileNotFoundError("Required frozen input is missing: " + str(path))
            if path == root / VALIDATOR:
                validator_source = path.read_bytes()
                frozen[str(path)] = hashlib.sha256(validator_source).hexdigest()
            else:
                frozen[str(path)] = digest(path)
        report["inputs_before"] = dict(frozen)
        manifest = {"schema": 1, "kind": "acquisition_inputs_before", "frozen_utc": datetime.now(timezone.utc).isoformat(),
                    "command": command, "source_git": report["source_git"], "inputs": frozen,
                    "platform": report["platform"], "python": report["python"],
                    "domain": report["domain"], "speed_measurement": False}
        write_json(directory / "manifest-before.json", manifest)
        report["manifest_before_sha256"] = digest(directory / "manifest-before.json")
        analyze = load_analyzer(validator_source, root / VALIDATOR)
        environment = {key: value for key, value in os.environ.items() if not key.startswith("DSD_")}
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
            metrics = analyze(stdout_path, directory)
            report["analysis"] = metrics
            write_json(directory / "analysis.json", metrics)
            if metrics.get("gate_pass") is not True:
                error("analysis", "independent_gate_failed")
            validated = {"cases.jsonl": metrics["log_sha256"]}
            for name, value in metrics["artifact_sha256"].items():
                path = Path(name).resolve()
                if path.parent != directory or path.name not in guards:
                    raise ValueError("Validator returned an unguarded output identity")
                validated[path.name] = value
            report["validated_outputs"] = validated
            if any(guards.get(name) != value for name, value in validated.items()):
                error("analysis", "validator_hash_mismatch")
        except Exception as exc:
            error("analysis", type(exc).__name__ + ": " + str(exc))
        after = capture_outputs(directory)
        report["outputs_after_validation"] = after
        if guards != after:
            error("output_integrity", "output_changed_during_validation")
    except Exception as exc:
        error("driver", type(exc).__name__ + ": " + str(exc))
    finally:
        # Preserve evidence for missing executable, launch failure and malformed
        # output as well as success. Empty streams are explicit, not a pass.
        for path in (stdout_path, stderr_path):
            if not path.exists():
                path.touch(exist_ok=False)
        for name, expected in frozen.items():
            try:
                actual = digest(Path(name))
            except OSError as exc:
                actual = None
                error("input_integrity", str(exc))
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
            if "manifest_before_sha256" in report and digest(directory / "manifest-before.json") != report["manifest_before_sha256"]:
                error("input_integrity", "frozen_manifest_changed")
        except Exception as exc:
            error("output_integrity", type(exc).__name__ + ": " + str(exc))
        report["driver_elapsed_ns"] = time.monotonic_ns() - started
        report["gate_pass"] = (not report["errors"] and report["native"]["returncode"] == 0
                               and report["analysis"] is not None and report["analysis"].get("gate_pass") is True)
        report["status"] = "passed" if report["gate_pass"] else "failed"
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
    print(json.dumps({"status": report["status"], "gate_pass": report["gate_pass"],
                      "report": str(args.new_output_directory.resolve() / "report.json")}))
    return 0 if report["gate_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
