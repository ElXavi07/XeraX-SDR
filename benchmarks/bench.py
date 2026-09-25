#!/usr/bin/env python3
"""Offline benchmark CLI. All decoder invocations use argv lists, never a shell."""
import argparse
import json
from pathlib import Path
from xerax_bench import corpus, runner
from xerax_bench.model import load_corpus, read_json, write_json


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="action", required=True)
    gen = sub.add_parser("generate")
    gen.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    gen.add_argument("--out", type=Path, required=True)
    gen.add_argument("--scenarios", nargs="+", choices=list(corpus.SCENARIOS), default=["clean", "awgn20", "awgn10", "echo", "dropout"])
    gen.add_argument("--seed", type=int, default=20260924)
    val = sub.add_parser("validate")
    val.add_argument("corpus", type=Path)
    disc = sub.add_parser("discriminator")
    disc.add_argument("corpus", type=Path)
    disc.add_argument("--out", type=Path, required=True)
    imp = sub.add_parser("register")
    imp.add_argument("sidecar", type=Path)
    imp.add_argument("--out", type=Path, required=True)
    imp.add_argument("--protocol", choices=list(corpus.FIXTURES[i][1] for i in range(len(corpus.FIXTURES))) + ["dmr_t3", "auto"], required=True)
    imp.add_argument("--kind", choices=["off_air_iq", "synthetic_protocol", "remodulated_discriminator"], required=True)
    imp.add_argument("--description", required=True)
    imp.add_argument("--expected", action="append")
    imp.add_argument("--hardware", type=Path)
    mix = sub.add_parser("mix")
    mix.add_argument("corpus", type=Path)
    mix.add_argument("--left", required=True)
    mix.add_argument("--right", required=True)
    mix.add_argument("--offset-hz", type=float, default=12500)
    mix.add_argument("--sir-db", type=float, default=0)
    mix.add_argument("--out", type=Path, required=True)
    run = sub.add_parser("run")
    run.add_argument("corpus", type=Path)
    run.add_argument("--profile", type=Path, action="append", required=True)
    run.add_argument("--out", type=Path, required=True)
    run.add_argument("--repeats", type=int, default=3)
    run.add_argument("--warmups", type=int, default=1)
    run.add_argument("--timeout", type=int, default=60)
    run.add_argument("--measure", choices=["diagnostics", "speed"], default="diagnostics")
    run.add_argument("--only")
    stress = sub.add_parser("stress")
    stress.add_argument("corpus", type=Path)
    stress.add_argument("--profile", type=Path, required=True)
    stress.add_argument("--out", type=Path, required=True)
    stress.add_argument("--workers", type=int, default=4)
    stress.add_argument("--iterations", type=int, default=2)
    stress.add_argument("--only")
    stress.add_argument("--timeout", type=int, default=60)
    cmp = sub.add_parser("compare")
    cmp.add_argument("report", type=Path)
    cmp.add_argument("--baseline", required=True)
    cmp.add_argument("--candidate", required=True)
    cmp.add_argument("--out", type=Path, required=True)
    ins = sub.add_parser("inspect")
    ins.add_argument("frames", type=Path)
    ins.add_argument("--out", type=Path, help="Optional parsed vocoder frames as JSONL")
    a = p.parse_args()
    try:
        if a.action == "generate":
            result = corpus.generate(a.repo, a.out, a.scenarios, a.seed)
            print(f"Generated {len(result['cases'])} cases")
        elif a.action == "validate":
            print(f"Validated {len(load_corpus(a.corpus)['cases'])} cases")
        elif a.action == "discriminator":
            print(f"Exported {len(corpus.discriminator_suite(a.corpus, a.out)['cases'])} cases")
        elif a.action == "register":
            corpus.register_capture(a.sidecar, a.out, a.protocol, a.kind, a.description,
                                    a.expected, read_json(a.hardware) if a.hardware else None)
            print("Capture imported byte-exactly; provenance remains operator-declared")
        elif a.action == "mix":
            corpus.mix(a.corpus, a.left, a.right, a.out, a.offset_hz, a.sir_db)
            print("Mixed capture created; no hardware or simultaneous-decoder claim")
        elif a.action == "run":
            report = runner.run(a.corpus, a.profile, a.out, a.repeats, a.measure, a.only, a.timeout, a.warmups)
            bad = [r for r in report["runs"] if not r["warmup"] and
                   (r["status"] != "completed" or (r["truth"].get("release_gate") and r["metrics"]["assertions_passed"] is not True))]
            print(f"{len(bad)} unavailable, failed or release-gate observations; see report")
            return 1 if bad else 0
        elif a.action == "compare":
            write_json(a.out, runner.compare(read_json(a.report), a.baseline, a.candidate))
        elif a.action == "stress":
            report = runner.stress(a.corpus, a.profile, a.out, a.workers, a.iterations, a.only, a.timeout)
            print(json.dumps(report, indent=2))
            return int(report["attempts"] != report["completed"] or report["failed_release_assertions"] > 0)
        else:
            text = a.frames.read_text(encoding="utf-8")
            if a.out:
                with a.out.open("x", encoding="utf-8") as output:
                    for index, match in enumerate(runner.FRAME.finditer(text)):
                        codec, slot, payload, e0, e1 = match.groups()
                        output.write(json.dumps({"index": index, "codec": codec, "slot": int(slot),
                            "payload_hex": payload, "engine_errors": [int(e0), int(e1)],
                            "sample_index": None}) + "\n")
            print(json.dumps(runner.score("", text,
                {"kind": "unknown"}), indent=2))
    except (ValueError, OSError, KeyError) as error:
        p.exit(2, str(error) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
