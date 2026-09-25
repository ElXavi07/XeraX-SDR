"""Synthetic observation counterexamples; never runs a native decoder."""
import collections
import copy
import hashlib
from pathlib import Path
import struct
import tempfile
import unittest

import analyze


def call(before=0, advance=20, eof_before=0, eof_after=0, committed=1, symbol=10):
    return {"before": before, "after": before + advance, "eof_before": eof_before,
            "eof_after": eof_after, "symbol_before": symbol, "symbol_after": symbol + committed}


def fixture(directory):
    directory = Path(directory); (directory / "vectors").mkdir()
    samples = 5000; raw = struct.pack("<5000f", *([1.0] * samples)); (directory / "wave").write_bytes(raw)
    lich = []
    register = 228
    for bit in format(0x83, "08b"):
        lich.append(((int(bit) << 1) | 1) ^ ((register & 1) << 1))
        register = (register >> 1) | ((((register >> 4) ^ register) & 1) << 8)
    body = "".join(map(str, lich)) + "0" * 174
    vector = bytes(10) + bytes(map(int, body)); (directory / "vectors/s").write_bytes(vector)
    metadata = {}
    for name, width, length in (("sacch", 6, 26), ("facch", 12, 80)):
        bits = "0" * length; check = analyze.crc(bits, width)
        metadata[name] = {"information_bits": bits, "computed_crc": check, "transmitted_crc": check, "crc_expected_pass": True}
    metadata["sha256"] = hashlib.sha256(vector).hexdigest()
    wave = {"scenario": "warm_clean", "samples": samples, "file": "wave", "sha256": hashlib.sha256(raw).hexdigest(),
            "original_file": "wave", "original_sha256": hashlib.sha256(raw).hexdigest(), "original_samples": samples,
            "edit": {"kind": "none", "source_start": 0, "count": 0},
            "frames": [{"ordinal": 0, "start": 0, "end": 3840, "kind": "S", "vector": "s"}]}
    case = {"id": "w-c37", "waveform": "w", "chunk": 37, "fast": 0}
    manifest = {"waveforms": {"w": wave}, "vectors": {"vectors": {"s": metadata}}, "cases": [case]}
    state = {"confirmed": 0, "streak": 0, "evidence": 0, "proved": 0, "verdict": 0,
             "profile_valid": 0, "profile_idx": 0, "profile_symbol": 0, "hunt_idx": 1,
             "symbolcnt": 0, "sync": 28, "pn95": 228, "sps": 20, "rf_mod": 2,
             "audio_indices": [0, 0, 0, 0]}
    rows = []
    def add(kind, frontier=0, frame=-1, **extra):
        row = {"seq": len(rows), "kind": kind, "provided": frontier, "frontier": frontier, "pops": frontier,
               "eof": int(frontier == samples), "frame": frame, "cache_pos": 0, "cache_len": 0,
               "read_start": frontier, "value": 0, **state, **extra}; rows.append(row); return row
    add("configuration", **analyze.CONFIG)
    add("initialized"); add("reset_begin"); add("reset_end"); add("search_begin")
    state["symbolcnt"] = 10
    add("search_end", 200, value=28); add("dispatch_begin", 200, 0); add("frame_begin", 200, 0)
    state["symbolcnt"] = 18
    add("lich", 360, 0, result=1, reason="accepted", full_lich=0x83, lich=0x41,
        parity_received=1, parity_computed=1, voice=0, scch=0, pich_tch=0, idas=0, sacch=1, facch=3)
    state["symbolcnt"] = 192
    for channel, part in ((1, 0), (2, 1), (2, 2)):
        expected = metadata["sacch" if channel == 1 else "facch"]
        add("crc", 3840, 0, channel=channel, part=part, bits=expected["information_bits"],
            computed=expected["computed_crc"], received=expected["transmitted_crc"], soft_pass=1, fallback=0)
    state.update(confirmed=1, evidence=2, proved=1)
    calls = [call(200 + i * 20, symbol=10 + i) for i in range(182)]
    add("frame_end", 3840, 0, value=2, body=body, body_count=182, body_positions=[x["after"] for x in calls], body_calls=calls)
    state.update(profile_valid=1, profile_idx=1, profile_symbol=192)
    add("dispatch_end", 3840, 0); add("search_begin", 3840); add("search_end", samples, value=-1)
    add("completed", samples)
    add("summary", samples, observed=1, fast=0, chunk=37, samples=samples, errors=0, starts=0, tunes=0,
        skipped=0, frames=1, dispatches=1, resets=1, crcs=3, rate_calls=0, reacquire_calls=0,
        v2_lich_events=1, v2_scch_events=0, v2_voice_calls=0, v2_mbe_calls=0, v2_audio_calls=0)
    trace = directory / "trace"; trace.write_bytes(struct.pack("<5000I", *range(samples)))
    return rows, trace, case, manifest


def comparison_fixture():
    scenarios = ("warm_clean", "cold_sync_blank", "warm_drop20", "prefix_12360", "prefix_12361", "prefix_12380", "prefix_12521", "scch_valid", "scch_wrong")
    manifest = {"waveforms": {}, "cases": []}; pairs = {}
    for scenario in scenarios:
        wave = {"scenario": scenario}
        if scenario.startswith("scch_"):
            wave["scch_expected"] = {"information_bits": "0" * 25, "computed_crc": 17,
                                     "transmitted_crc": 17 if scenario == "scch_valid" else 81,
                                     "crc_expected_pass": scenario == "scch_valid"}
        manifest["waveforms"][scenario] = wave
        for chunk in (37, 512):
            case = {"id": f"{scenario}-c{chunk}", "waveform": scenario, "chunk": chunk, "fast": 0}
            manifest["cases"].append(case); pairs[case["id"]] = {}
            frame = {"begin": {"eof": 0, "audio_indices": [0, 0, 0, 0]}, "end": {"eof": 0, "audio_indices": [0, 0, 0, 0]},
                     "source": {"ordinal": 0, "kind": "S"}, "fully_sampled": True, "classes": ["complete"] * 182,
                     "lich": [], "scch": [], "events": []}
            frames = [frame]; classes = {"complete": 182}
            if scenario.startswith("prefix_"):
                cut = int(scenario.removeprefix("prefix_")); completes = {12360: 0, 12361: 0, 12380: 1, 12521: 8}[cut]
                kind = "partial_eof" if cut in (12361, 12521) else "empty_first_eof"
                frame.update(source=None, fully_sampled=False, classes=["complete"] * completes + [kind] + ["empty_after_eof"] * 7)
                frame["end"]["eof"] = 1; classes = dict(collections.Counter(frame["classes"]))
            elif scenario == "cold_sync_blank": classes["empty_after_eof"] = 73
            elif scenario == "warm_drop20":
                frame["lich"] = [{"result": 1, "lich": 0x77, "voice": 3, "scch": 1}]
                frame["scch"] = [{"bits": "0" * 25, "computed": 17, "received": 81}]
                frame["events"] = [{"kind": "audio_end"}]; frame["end"]["audio_indices"][1] = 640
            elif scenario.startswith("scch_"):
                frame["source"]["kind"] = "V"; expected = wave["scch_expected"]
                frame["scch"] = [{"bits": expected["information_bits"], "computed": expected["computed_crc"], "received": expected["transmitted_crc"]}]
                frames.append(copy.deepcopy(frame)); frames[1]["source"]["ordinal"] = 1
            for enabled in (0, 1):
                pairs[case["id"]][enabled] = {"case": case, "summary": {"observed": enabled}, "measurement_pass": True,
                    "semantic": [{"kind": "receiver", "value": 1}], "chunk_semantic": [{"kind": "common"}],
                    "trace_sha256": f"trace-{scenario}-{enabled}", "call_classes": classes, "frames": copy.deepcopy(frames)}
    return pairs, manifest


def voice_fixture(directory):
    rows, trace, case, manifest = fixture(directory)
    end = next(r for r in rows if r["kind"] == "frame_end")
    lich = next(r for r in rows if r["kind"] == "lich")
    encoded = []; register = 228
    for bit in format(0xef, "08b"):
        encoded.append(((int(bit) << 1) | 1) ^ ((register & 1) << 1))
        register = (register >> 1) | ((((register >> 4) ^ register) & 1) << 8)
    end["body"] = "".join(map(str, encoded)) + end["body"][8:]
    vector = bytes(10) + bytes(map(int, end["body"])); (Path(directory) / "vectors/s").write_bytes(vector)
    manifest["vectors"]["vectors"]["s"]["sha256"] = hashlib.sha256(vector).hexdigest()
    lich.update(full_lich=0xef, lich=0x77, voice=3, scch=1, idas=1, sacch=0, facch=0)
    rows = [r for r in rows if r["kind"] != "crc"]
    template = {k: v for k, v in end.items() if k not in ("body", "body_count", "body_positions", "body_calls")}
    events = [{**template, "kind": "scch", "bits": "0" * 25, "check_bits": format(17, "07b"),
               "computed": 17, "received": 17, "soft_pass": 1, "fallback": 0, "direction": 1},
              {**template, "kind": "voice_begin", "value": 3}]
    checksum = 2166136261
    for _ in range(320): checksum = (checksum * 16777619) & 0xffffffff
    for _ in range(4):
        events.extend([{**template, "kind": "mbe_begin", "value": 0}, {**template, "kind": "audio_begin", "value": 0},
            {**template, "kind": "audio_end", "value": 0, "pcm_domain": "internal_post_gain_float160_and_staged_short160",
             "float_finite": 160, "float_nonzero": 0, "float_peak": 0.0, "float_energy": 0.0,
             "short_nonzero": 0, "short_peak": 0, "short_checksum": checksum}, {**template, "kind": "mbe_end", "value": 0}])
    events.append({**template, "kind": "voice_end", "value": 3})
    index = rows.index(end); rows[index:index] = events
    for seq, row in enumerate(rows): row["seq"] = seq
    rows[-1].update(crcs=0, v2_scch_events=1, v2_voice_calls=1, v2_mbe_calls=4, v2_audio_calls=4)
    return rows, trace, case, manifest


def unconfirmed_voice_fixture(directory, fabricate_voice=False):
    rows, trace, case, manifest = voice_fixture(directory)
    if not fabricate_voice:
        rows = [r for r in rows if not r["kind"].startswith(("voice_", "mbe_", "audio_"))]
        rows[-1].update(v2_voice_calls=0, v2_mbe_calls=0, v2_audio_calls=0)
    for seq, row in enumerate(rows):
        row.update(seq=seq, confirmed=0, profile_valid=0, profile_idx=0, profile_symbol=0)
        if row["kind"] == "scch": row.update(streak=0, evidence=0, proved=0)
        if row["kind"] in ("frame_end", "dispatch_end", "completed", "summary"):
            row.update(streak=1, evidence=1, proved=0, value=0)
        if row["kind"] == "dispatch_end": row["verdict"] = 1
    return rows, trace, case, manifest


class ObservationChecker(unittest.TestCase):
    def test_independent_crc_known_vectors(self):
        self.assertEqual(analyze.crc("0" * 25, 7), 17)
        self.assertEqual(analyze.crc("00001011000100000101010101", 6), 59)
        self.assertEqual(analyze.crc("00010000000100100011010001010110011110001001101010111100110111101111000000010010", 12), 345)

    def test_fully_recorded_synthetic_frame_and_observer_off(self):
        with tempfile.TemporaryDirectory() as temp:
            rows, trace, case, manifest = fixture(temp)
            audit = analyze.inspect(rows, trace, case, manifest, temp, 1)
            self.assertTrue(audit["measurement_pass"]); self.assertTrue(audit["frames"][0]["fully_sampled"])
            off = [r for r in copy.deepcopy(rows) if r["kind"] not in analyze.OPTIONAL]
            for seq, r in enumerate(off): r.update(seq=seq, frontier=0, pops=0)
            off[-1].update(observed=0, crcs=0); trace.write_bytes(b"")
            quiet = analyze.inspect(off, trace, case, manifest, temp, 0)
            self.assertEqual(audit["semantic"], quiet["semantic"])

    def test_completed_zero_and_exact_boundary_are_valid(self):
        self.assertEqual(analyze.classify_call(call(80), 100), "complete")
        self.assertEqual(analyze.classify_call(call(100, 0, eof_after=1, committed=0), 100), "empty_first_eof")
        self.assertEqual(analyze.classify_call(call(100, 0, 1, 1, 0), 100), "empty_after_eof")

    def test_partial_one_and_nineteen_samples_do_not_complete(self):
        for count in (1, 19):
            self.assertEqual(analyze.classify_call(call(100 - count, count, eof_after=1, committed=0), 100), "partial_eof")
            with self.assertRaisesRegex(ValueError, "falsely completed"):
                analyze.classify_call(call(100 - count, count, eof_after=1), 100)

    def test_impossible_counter_eof_or_delivery_transitions_fail(self):
        values = [call(0, 0), call(0, 20, committed=0), call(0, 20, committed=2),
                  call(100, 0, 1, 0, 0), call(80, 20, 1, 1, 0), call(80, 20, 0, 1, 0)]
        for value in values:
            with self.assertRaises(ValueError): analyze.classify_call(value, 100)

    def test_provider_prefetch_is_not_consumption_or_eof(self):
        row = {"eof": 0, "provided": 100, "read_start": 50, "cache_len": 50, "cache_pos": 20}
        self.assertEqual(analyze.common_frontier(row, 100), 70)
        row.update(eof=1, cache_len=0, cache_pos=0)
        self.assertEqual(analyze.common_frontier(row, 100), 100)

    def test_missing_pop_duplicate_pop_and_stale_position_fail(self):
        for mutation in ("missing", "duplicate", "position", "interval"):
            with tempfile.TemporaryDirectory() as temp:
                rows, trace, case, manifest = fixture(temp)
                if mutation in ("missing", "duplicate"):
                    words = list(range(5000))
                    if mutation == "missing": words.pop(350)
                    else: words[350] = 349
                    trace.write_bytes(struct.pack("<" + "I" * len(words), *words))
                else:
                    end = next(r for r in rows if r["kind"] == "frame_end")
                    if mutation == "position": end["body_positions"][5] -= 1
                    else: end["body_calls"][5]["before"] -= 1
                with self.assertRaises(ValueError): analyze.inspect(rows, trace, case, manifest, temp, 1)

    def test_partial_and_empty_positions_cannot_receive_source_identity(self):
        frame = {"begin": {"eof": 0, "sync": 28}, "end": {"eof": 1, "body_count": 182,
                 "body_positions": [20] * 182}, "classes": ["complete"] * 181 + ["partial_eof"]}
        self.assertIsNone(analyze.source_identity(frame, {"frames": []}, list(range(5000))))

    def test_final_crc7_received_bits_and_fallback_are_checked(self):
        event = {"bits": "0" * 25, "check_bits": format(81, "07b"), "computed": 17, "received": 81,
                 "soft_pass": 0, "fallback": 1, "direction": 1}
        analyze.validate_crc(event, 7, 25)
        for key, value in (("computed", 18), ("check_bits", format(17, "07b")), ("fallback", 0)):
            wrong = {**event, key: value}
            with self.assertRaises(ValueError): analyze.validate_crc(wrong, 7, 25)

    def test_soft_pass_requires_final_acceptance_but_fallback_may_recover(self):
        for width, length in ((6, 26), (7, 25), (12, 80)):
            bits = "0" * length; computed = analyze.crc(bits, width)
            event = {"bits": bits, "computed": computed, "received": computed ^ 1,
                     "soft_pass": 1, "fallback": 0, "direction": 1,
                     "check_bits": format(computed ^ 1, f"0{width}b")}
            with self.assertRaisesRegex(ValueError, "Soft pass contradicts"):
                analyze.validate_crc(event, width, length)
            event.update(soft_pass=0, fallback=1, received=computed, check_bits=format(computed, f"0{width}b"))
            analyze.validate_crc(event, width, length)

    def test_lich_dibits_and_summary_counts_not_trusted(self):
        for mutation in ("lich", "summary", "profile", "scope"):
            with tempfile.TemporaryDirectory() as temp:
                rows, trace, case, manifest = fixture(temp)
                if mutation == "lich": next(r for r in rows if r["kind"] == "lich")["full_lich"] ^= 2
                elif mutation == "summary": rows[-1]["v2_lich_events"] = 2
                elif mutation == "profile": next(r for r in rows if r["kind"] == "frame_begin")["sps"] = 10
                else: rows[0]["datascope"] = 1
                with self.assertRaises(ValueError): analyze.inspect(rows, trace, case, manifest, temp, 1)

    def test_internal_pcm_counts_and_statistics_do_not_imply_speech(self):
        checksum = 2166136261
        for _ in range(320): checksum = (checksum * 16777619) & 0xffffffff
        event = {"pcm_domain": "internal_post_gain_float160_and_staged_short160", "float_finite": 160,
                 "float_nonzero": 2, "float_peak": 2.0, "float_energy": 5.0,
                 "short_nonzero": 0, "short_peak": 0, "short_checksum": checksum}
        analyze.validate_audio(event)
        # A measured nonfinite receiver value must remain an outcome, not a new
        # blanket side-effect prohibition like the previous audio-index guard.
        analyze.validate_audio({**event, "float_finite": 159})
        for key, value in (("float_finite", 1), ("float_energy", 3), ("short_nonzero", 161), ("pcm_domain", "played_audio"), ("short_checksum", 123)):
            with self.assertRaises(ValueError): analyze.validate_audio({**event, key: value})

    def test_complete_registered_observation_grid_can_pass(self):
        pairs, manifest = comparison_fixture()
        result = analyze.compare(pairs, manifest)
        self.assertTrue(result["measurement_pass"], result["issues"])
        self.assertEqual(result["expected_invocations"], 36)

    def test_missing_grid_observer_change_and_chunk_change_fail(self):
        for mutation in ("grid", "observer", "chunk"):
            pairs, manifest = comparison_fixture(); cid = "warm_clean-c37"
            if mutation == "grid": del pairs[cid][0]
            elif mutation == "observer": pairs[cid][0]["semantic"] = []
            else: pairs[cid][1]["trace_sha256"] = "changed"
            self.assertFalse(analyze.compare(pairs, manifest)["measurement_pass"], mutation)

    def test_finite_cut_requires_exact_call_exposure_and_no_attribution(self):
        for mutation in ("missing", "complete", "attributed"):
            pairs, manifest = comparison_fixture(); audit = pairs["prefix_12361-c37"][1]
            if mutation == "missing": audit["call_classes"].pop("partial_eof")
            elif mutation == "complete": audit["frames"][0]["classes"][0] = "complete"
            else: audit["frames"][0]["source"] = {"ordinal": 3}
            self.assertFalse(analyze.compare(pairs, manifest)["measurement_pass"], mutation)

    def test_wrong_crc_control_cannot_pass_through_missing_or_corrected_check(self):
        for mutation in ("missing", "check", "source"):
            pairs, manifest = comparison_fixture(); frame = pairs["scch_wrong-c37"][1]["frames"][0]
            if mutation == "missing": frame["scch"] = []
            elif mutation == "check": frame["scch"][0]["received"] = 17
            else: frame["source"] = None
            self.assertFalse(analyze.compare(pairs, manifest)["measurement_pass"], mutation)

    def test_previous_voice_activity_must_remain_measured(self):
        pairs, manifest = comparison_fixture()
        pairs["warm_drop20-c37"][1]["frames"][0]["events"] = []
        self.assertFalse(analyze.compare(pairs, manifest)["measurement_pass"])

    def test_voice_mbe_and_audio_forwarding_events_pair_with_actual_frame(self):
        with tempfile.TemporaryDirectory() as temp:
            rows, trace, case, manifest = voice_fixture(temp)
            result = analyze.inspect(rows, trace, case, manifest, temp, 1)
            self.assertEqual(result["scch_events"], 1)
            self.assertEqual(result["summary"]["v2_audio_calls"], 4)
            rows = [r for r in rows if not (r["kind"] == "mbe_end" and r["seq"] == next(x["seq"] for x in rows if x["kind"] == "mbe_end"))]
            for seq, row in enumerate(rows): row["seq"] = seq
            with self.assertRaisesRegex(ValueError, "nesting|Unpaired"):
                analyze.inspect(rows, trace, case, manifest, temp, 1)

    def test_accepted_unconfirmed_voice_profile_correctly_has_no_calls(self):
        with tempfile.TemporaryDirectory() as temp:
            rows, trace, case, manifest = unconfirmed_voice_fixture(temp)
            result = analyze.inspect(rows, trace, case, manifest, temp, 1)
            frame = result["frames"][0]
            self.assertEqual(frame["lich"][0]["result"], 1)
            self.assertEqual(frame["lich"][0]["voice"], 3)
            self.assertEqual(frame["scch"][0]["computed"], frame["scch"][0]["received"])
            self.assertEqual(frame["end"]["confirmed"], 0)
            self.assertEqual(result["summary"]["v2_voice_calls"], 0)

    def test_fabricated_unconfirmed_voice_call_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            rows, trace, case, manifest = unconfirmed_voice_fixture(temp, fabricate_voice=True)
            with self.assertRaisesRegex(ValueError, "profile/confirmation guard"):
                analyze.inspect(rows, trace, case, manifest, temp, 1)

    def test_voice_entry_confirmation_cannot_be_hidden_by_final_confirmation(self):
        with tempfile.TemporaryDirectory() as temp:
            rows, trace, case, manifest = voice_fixture(temp)
            next(r for r in rows if r["kind"] == "voice_begin")["confirmed"] = 0
            with self.assertRaisesRegex(ValueError, "began without confirmation"):
                analyze.inspect(rows, trace, case, manifest, temp, 1)

    def test_optional_events_cannot_move_after_frame_end(self):
        with tempfile.TemporaryDirectory() as temp:
            rows, trace, case, manifest = fixture(temp)
            event = copy.deepcopy(next(r for r in rows if r["kind"] == "crc"))
            index = next(i for i, r in enumerate(rows) if r["kind"] == "frame_end")
            rows.insert(index + 1, event)
            # Keep the global coordinates valid so ownership, not a counter typo, rejects it.
            for seq, row in enumerate(rows): row["seq"] = seq
            with self.assertRaisesRegex(ValueError, "outside observed frame"):
                analyze.inspect(rows, trace, case, manifest, temp, 1)

    def test_hash_updated_map_tampering_still_fails_declared_edit(self):
        with tempfile.TemporaryDirectory() as temp:
            _, _, _, manifest = fixture(temp); wave = manifest["waveforms"]["w"]
            values = list(range(5000)); values[50] = 49
            raw = struct.pack("<5000I", *values); (Path(temp) / "lineage").write_bytes(raw)
            wave.update(lineage_file="lineage", lineage_sha256=hashlib.sha256(raw).hexdigest())
            with self.assertRaisesRegex(ValueError, "edit/lineage mismatch"):
                analyze.read_inputs(wave, manifest, temp)


if __name__ == "__main__":
    unittest.main()
