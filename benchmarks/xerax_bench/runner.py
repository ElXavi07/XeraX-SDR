"""Auditable subprocess adapters and paired reporting; never guesses absent metrics."""
import array
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
import os
import platform
import re
import signal
import statistics
import subprocess
import sys
import time
import wave
from pathlib import Path
from .model import ID, MODES, contained, digest, load_corpus, percentile, read_json, write_json

ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
FRAME = re.compile(r"FRAME (AMBE|IMBE)\s+slot=(\d+)\s+data=([0-9A-Fa-f]+)\s+err=\[(\d+)\]\s+\[(\d+)\]")


def score(text, frame_text, truth):
    frame_log_available = frame_text is not None
    text = ANSI.sub("", text)
    frame_text = ANSI.sub("", frame_text or "")
    evidence = text + "\n" + frame_text
    positive = [bool(re.search(p, evidence, re.I)) for p in truth.get("required", [])]
    forbidden = [bool(re.search(p, evidence, re.I)) for p in truth.get("forbidden", [])]
    passed = (all(positive) and not any(forbidden)) if truth["kind"] != "unknown" else None
    frames = FRAME.findall(frame_text)
    canonical = "\n".join(f"{codec}:{slot}:{payload.upper()}" for codec, slot, payload, *_ in frames)
    errors = re.findall(r"Total audio errors:\s*(\d+)", text)
    p25 = re.findall(r"XeraX P25 FEC: accepted=(\d+) rejected=(\d+); voice_accepted=(\d+) voice_rejected=(\d+)", text)
    dmr = re.findall(r"XeraX DMR evidence: checked=(\d+) suspected_ras=(\d+) rejected=(\d+)", text)
    return {"assertions_passed": passed, "positive_matches": positive, "forbidden_matches": forbidden,
        "audio_errors_reported": int(errors[-1]) if errors else None,
        "sync_log_occurrences": len(re.findall(r"Sync:", text)),
        "decoded_vocoder_frames": len(frames) if frame_log_available else None,
        "frame_payload_sha256": hashlib.sha256(canonical.encode()).hexdigest() if frames else None,
        "frame_error_sum": sum(int(e0) + int(e1) for _, _, _, e0, e1 in frames) if frames else None,
        "p25_fec": list(map(int, p25[-1])) if p25 else None,
        "dmr_evidence": list(map(int, dmr[-1])) if dmr else None,
        "bit_error_rate": None, "first_sync_sample": None, "first_valid_frame_sample": None,
        "first_pcm_sample": None, "speech_intelligibility": None}


def audio_metrics(path):
    if not path.is_file():
        return None
    try:
        with wave.open(str(path), "rb") as wav:
            if wav.getsampwidth() != 2:
                return {"error": "unsupported audio sample width"}
            values = array.array("h", wav.readframes(wav.getnframes()))
            if sys.byteorder != "little":
                values.byteswap()
            count = len(values)
            return {"samples": count, "rate": wav.getframerate(), "channels": wav.getnchannels(),
                "peak": max(map(abs, values), default=0),
                "rms": math.sqrt(sum(float(v) * v for v in values) / count) if count else 0,
                "full_scale_samples": sum(v in (-32768, 32767) for v in values),
                "nonzero_samples": sum(v != 0 for v in values)}
    except (wave.Error, EOFError) as error:
        return {"error": str(error)}


def load_profile(path):
    profile = read_json(path)
    if profile.get("schema") != 1 or not ID.fullmatch(profile.get("name", "")):
        raise ValueError("Invalid adapter profile")
    if profile.get("engine") not in ("xerax-lab", "xerax-cli", "dsd-fme"):
        raise ValueError("Adapter not implemented; use the pending coverage ledger")
    prefix = profile.get("prefix", [])
    if profile["engine"] == "xerax-lab" and prefix not in (["0", "0", "0"], ["1", "0", "0"]):
        raise ValueError("Only baseline/equalizer lab presets are currently validated")
    if profile["engine"] != "xerax-lab" and prefix:
        raise ValueError("Extra adapter arguments need an explicit, reviewed preset")
    if profile.get("executable"):
        executable = Path(profile["executable"])
        if not executable.is_absolute():
            executable = Path(path).resolve().parent / executable
        profile["executable"] = str(executable.resolve())
    profile["profile_sha256"] = digest(path)
    return profile


def command(profile, case, corpus_dir, output, measure):
    engine = profile["engine"]
    inp = case["input"]
    if engine == "dsd-fme" and inp["stage"] != "discriminator":
        return None
    if inp["stage"] == "discriminator" and case["protocol"] in ("p25_cqpsk", "p25p2"):
        return None
    if inp["stage"] == "discriminator" and inp["sample_rate_hz"] != 48000:
        return None  # Both current audio adapters expect 48 kHz, not arbitrary WAV rates.
    args = [profile["executable"], *profile.get("prefix", [])]
    if engine != "dsd-fme":
        args += ["--frontend", "none", "--no-config"]
    args += MODES[case["protocol"]] + ["-o", "null"]
    if inp["stage"] == "iq":
        args += ["--iq-replay", str(contained(corpus_dir, inp["metadata"])), "--iq-replay-rate", "fast"]
    else:
        # Forward slashes are accepted by both native Windows and Cygwin libsndfile.
        args += ["-i", contained(corpus_dir, inp["path"]).as_posix()]
    if measure == "diagnostics":
        args += ["-w", (output / "audio.wav").as_posix()]
        if engine != "dsd-fme":
            args += ["--frame-log", str(output / "frames.log"), "-J", str(output / "events.log")]
    return args


def invoke(args, cwd, log, timeout):
    env = {k: v for k, v in os.environ.items() if not k.startswith("DSD_")}
    start = time.perf_counter()
    with Path(log).open("wb") as handle:
        try:
            child = subprocess.Popen(args, cwd=cwd, env=env, stdout=handle,
                stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                start_new_session=os.name != "nt",
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0)
        except OSError as error:
            handle.write(str(error).encode("utf-8"))
            return {"status": "launch_error", "exit_code": None,
                    "wall_seconds": time.perf_counter() - start}
        try:
            code = child.wait(timeout=timeout)
            status = "completed" if code == 0 else "process_error"
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(child.pid), "/T", "/F"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            else:
                os.killpg(child.pid, signal.SIGKILL)
            child.kill()
            child.wait()
            code, status = None, "timeout"
    return {"status": status, "exit_code": code, "wall_seconds": time.perf_counter() - start}


def run(corpus, profiles, out, repeats=3, measure="diagnostics", only=None, timeout=60, warmups=1):
    if not 1 <= repeats <= 100 or not 1 <= timeout <= 3600 or not 0 <= warmups <= 10:
        raise ValueError("Invalid repeat/timeout/warmup bound")
    if measure not in ("diagnostics", "speed"):
        raise ValueError("Invalid measurement mode")
    doc = load_corpus(corpus)
    variants = [load_profile(p) for p in profiles]
    if not variants or len({p["name"] for p in variants}) != len(variants):
        raise ValueError("Adapter names must be unique")
    selected = [c for c in doc["cases"] if only is None or re.search(only, c["id"])]
    if not selected:
        raise ValueError("No selected cases")
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    for p in variants:
        path = Path(p["executable"]) if p.get("executable") else None
        p["binary_sha256"] = digest(path) if path and path.is_file() else None
    report = {"schema": 1, "corpus_sha256": digest(corpus), "measurement": measure,
        "clock": "process wall time, including startup and shutdown; not acquisition latency",
        "host": {"platform": platform.platform(), "machine": platform.machine(),
                 "processor": platform.processor(), "logical_cpus": os.cpu_count(),
                 "python": sys.version, "cpu_frequency_locked": False},
        "profiles": variants, "repeats": repeats, "warmups": warmups, "runs": [],
        "hardware_acceptance": False, "superiority_established": False}
    for case in selected:
        for rep in range(-warmups, repeats):
            for offset in range(len(variants)):
                p = variants[(offset + rep + warmups) % len(variants)]
                ident = f"{case['id']}--{p['name']}--{'warm' + str(-rep) if rep < 0 else str(rep)}"
                folder = out / ident
                folder.mkdir()
                row = {"case": case["id"], "variant": p["name"], "repeat": rep,
                       "warmup": rep < 0, "stage": case["input"]["stage"],
                       "case_sha256": case["input"]["sha256"], "truth": case["truth"],
                       "duration_seconds": case["input"]["samples"] / case["input"]["sample_rate_hz"],
                       "directory": ident, "metrics": None}
                if p["binary_sha256"] is None:
                    row.update(status="unavailable", reason="adapter executable absent", wall_seconds=None)
                else:
                    args = command(p, case, Path(corpus).resolve().parent, folder, measure)
                    if args is None:
                        row.update(status="unsupported", reason="adapter/input-stage mismatch", wall_seconds=None)
                    else:
                        write_json(folder / "command.json", args)
                        result = invoke(args, folder, folder / "decoder.log", timeout)
                        row.update(result)
                        text = (folder / "decoder.log").read_text(encoding="utf-8", errors="replace")
                        fp = folder / "frames.log"
                        frames = fp.read_text(encoding="utf-8", errors="replace") if fp.is_file() else None
                        row["metrics"] = score(text, frames, case["truth"])
                        if result["status"] != "completed":
                            row["metrics"]["assertions_passed"] = False
                        row["metrics"]["audio"] = audio_metrics(folder / "audio.wav")
                        row["replay_factor"] = row["duration_seconds"] / row["wall_seconds"]
                report["runs"].append(row)
                write_json(out / "report.json", report)
                if rep >= 0:
                    print(f"{case['id']} / {p['name']} / {rep}: {row['status']}", flush=True)
    report["summary"] = summarize(report["runs"])
    write_json(out / "report.json", report)
    (out / "summary.md").write_text(markdown(report), encoding="utf-8")
    return report


def summarize(rows):
    groups = {}
    for row in rows:
        if not row["warmup"]:
            groups.setdefault((row["case"], row["variant"]), []).append(row)
    result = []
    for (case, variant), group in groups.items():
        good = [r for r in group if r["status"] == "completed"]
        times = [r["wall_seconds"] for r in good]
        observed_hashes = [r["metrics"]["frame_payload_sha256"] for r in good
                          if r["metrics"].get("frame_payload_sha256")]
        hashes = set(observed_hashes)
        result.append({"case": case, "variant": variant, "completed": len(good), "attempts": len(group),
            "median_wall_seconds": statistics.median(times) if times else None,
            "p95_wall_seconds": percentile(times, .95),
            "assertions_passed": sum(r["metrics"]["assertions_passed"] is True for r in good),
            "release_gate": group[0]["truth"].get("release_gate", False),
            "payload_consistent": len(hashes) == 1 and len(observed_hashes) == len(good) if hashes else None,
            "statuses": sorted({r["status"] for r in group})})
    return result


def markdown(report):
    lines = ["# XeraX benchmark observations", "",
        f"Measurement: {report['measurement']}. {report['clock']}.", "",
        "No hardware acceptance, BER, acquisition latency or superiority claim is inferred.", "",
        "| Case | Variant | Completed | Field/negative assertions | Median seconds | p95 seconds |",
        "| --- | --- | ---: | ---: | ---: | ---: |"]
    for row in report["summary"]:
        median = f"{row['median_wall_seconds']:.6f}" if row["median_wall_seconds"] is not None else "unavailable"
        p95 = f"{row['p95_wall_seconds']:.6f}" if row["p95_wall_seconds"] is not None else "unavailable"
        lines.append(f"| {row['case']} | {row['variant']} | {row['completed']}/{row['attempts']} | {row['assertions_passed']} | {median} | {p95} |")
    return "\n".join(lines) + "\n"


def compare(report, baseline, candidate):
    if baseline == candidate:
        raise ValueError("Choose distinct variants")
    names = {p["name"] for p in report["profiles"]}
    if baseline not in names or candidate not in names:
        raise ValueError("Unknown variant")
    runs = {(r["case"], r["repeat"], r["variant"]): r for r in report["runs"] if not r["warmup"]}
    cases = sorted({key[0] for key in runs})
    results = []
    for case in cases:
        pairs = [(r, runs.get((case, rep, candidate))) for (c, rep, v), r in runs.items()
                 if c == case and v == baseline]
        valid = [(a, b) for a, b in pairs if b and a["status"] == b["status"] == "completed"]
        ratios = [a["wall_seconds"] / b["wall_seconds"] for a, b in valid]
        result = {"case": case, "paired_runs": len(valid),
                  "median_process_speed_ratio": statistics.median(ratios) if ratios else None,
                  "baseline_field_passes": sum(a["metrics"]["assertions_passed"] is True for a, b in valid),
                  "candidate_field_passes": sum(b["metrics"]["assertions_passed"] is True for a, b in valid),
                  "comparable_payload_pairs": sum(bool(a["metrics"]["frame_payload_sha256"] and
                      b["metrics"]["frame_payload_sha256"]) for a, b in valid),
                  "payload_changes": sum(a["metrics"]["frame_payload_sha256"] != b["metrics"]["frame_payload_sha256"]
                       for a, b in valid if a["metrics"]["frame_payload_sha256"] and b["metrics"]["frame_payload_sha256"]),
                  "gate_regression": any(a["truth"].get("release_gate") and
                      a["metrics"]["assertions_passed"] is True and b["metrics"]["assertions_passed"] is not True
                      for a, b in valid)}
        # Candidate failures cannot disappear from the comparison by exclusion.
        result["missing_or_failed_pairs"] = len(pairs) - len(valid)
        result["candidate_gate_failure"] = any(a["truth"].get("release_gate") and
            (not b or b["status"] != "completed" or b["metrics"]["assertions_passed"] is not True)
            for a, b in pairs)
        results.append(result)
    return {"schema": 1, "baseline": baseline, "candidate": candidate,
            "measurement": report["measurement"], "results": results,
            "promotion_decision": "not_established",
            "reason": "Field recognition and process timing are insufficient for general reception superiority"}


def stress(corpus, profile, out, workers=4, iterations=2, only=None, timeout=60):
    if not 1 <= workers <= 32 or not 1 <= iterations <= 100:
        raise ValueError("Invalid process-load bound")
    # Validate before launching any worker.
    load_corpus(corpus)
    load_profile(profile)
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(run, corpus, [profile], out / f"worker-{i}", iterations,
                               "speed", only, timeout, 0) for i in range(workers)]
        reports = [future.result() for future in futures]
    elapsed = time.perf_counter() - start
    rows = [r for report in reports for r in report["runs"]]
    complete = [r for r in rows if r["status"] == "completed"]
    report = {"schema": 1, "kind": "concurrent_independent_replay_processes",
        "workers": workers, "iterations": iterations, "wall_seconds": elapsed,
        "attempts": len(rows), "completed": len(complete),
        "aggregate_recording_seconds_per_wall_second": sum(r["duration_seconds"] for r in complete) / elapsed,
        "failed_release_assertions": sum(r["truth"].get("release_gate") and
            r["metrics"]["assertions_passed"] is not True for r in complete),
        "hardware_acceptance": False, "shared_channelizer_capacity": None,
        "limitations": ["No live SDR or shared channelizer is exercised",
                       "No sustained thermal acceptance; use longer declared runs separately"]}
    write_json(out / "stress.json", report)
    return report
