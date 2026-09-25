"""Independent checker counterexamples using explicitly synthetic truth pins.

No arithmetic/encoder import, actual registered corpus generation, or native
execution. Synthetic control channels are only layout markers; external output
gate fixtures explicitly mock validate_inputs and cannot certify real frames.
"""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import analyze


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def dump(value):
    return (json.dumps(value, separators=(",", ":")) + "\n").encode()


class InputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        source = bytes(range(130))
        words = []
        for i in range(0, 130, 13):
            bits = f"{int.from_bytes(source[i:i + 13], 'big'):0104b}"
            words.extend((bits[:49], bits[49:98]))
        channels = b"".join(bytes([i % 249 + 1]) * 9 for i in range(8266))
        previous = dump({"measurement_pass": True, "progression_pass": True,
                         "preservation_pass": True, "product_promotion": False})
        self.mask = bytes(3) + b"\xaa" * 45
        control = ("const unsigned char SCRAMBLER[] = {" + ", ".join(f"0x{x:02X}U" for x in self.mask) + "};\n").encode()
        primary = dump({"repositories": analyze.PINS, "files": [
            {"path": "MMDVM-Host/NXDNControl.cpp", "sha256": sha(control), "bytes": len(control),
             "commit": analyze.PINS["MMDVM-Host"],
             "git_blob_sha1": hashlib.sha1(b"blob " + str(len(control)).encode() + b"\0" + control).hexdigest()}]})
        # Literal registered layout identities; synthetic words/channel markers.
        grid = [("header", 131, 0, None, [], analyze.VCALL),
                ("voice0", 174, 3, 0, [0, 1, 2, 3], bytes(10)),
                ("voice1", 174, 2, 1, [4, 5, 6, 7], bytes(10)),
                ("voice2", 174, 1, 2, [8, 9, 10, 11], bytes(10)),
                ("voice3", 174, 0, 3, [12, 13, 14, 15], bytes(10)),
                ("voice4", 174, 3, 0, [16, 17, 18, 19], bytes(10)),
                ("facch_first", 166, 2, 1, [0, 1, 2, 3], analyze.VCALL),
                ("facch_second", 170, 1, 2, [4, 5, 6, 7], analyze.VCALL),
                ("trailer", 131, 0, None, [], analyze.TRAILER)]
        rows, records, self.raw, self.air = [], [], [], []
        message = "".join(f"{x:08b}" for x in analyze.VCALL[:9])
        for identity, (name, lich, structure, fragment, quartet, facch) in enumerate(grid):
            info = f"{structure:02b}000001" + ("00010000" + "0" * 10 if fragment is None else message[18 * fragment:18 * (fragment + 1)])
            voice = bytes(26) if not quartet else b"".join(
                int(words[a] + words[b] + "000000", 2).to_bytes(13, "big") for a, b in (quartet[:2], quartet[2:]))
            rec = bytes([lich]) + int(info + "000000", 2).to_bytes(4, "big") + facch + voice
            logical = "".join(bit + "1" for bit in f"{lich:08b}")
            prefix = int(f"{0xCDF59:020b}" + logical + "0" * 60, 2).to_bytes(12, "big")
            traffic = bytearray((b"\xdd" if name == "trailer" else b"\xcc") * 36)
            slots = [] if not quartet else [2, 3] if name == "facch_first" else [0, 1] if name == "facch_second" else list(range(4))
            transmitted = []
            for slot in slots:
                source_id = quartet[slot]
                traffic[slot * 9:(slot + 1) * 9] = channels[source_id * 9:(source_id + 1) * 9]
                transmitted.append({"slot": slot, "source_id": source_id})
            raw = prefix + bytes(traffic)
            air = bytes(a ^ b for a, b in zip(raw, self.mask))
            rows.append({"id": identity, "name": name, "lich": lich, "structure": structure,
                         "fragment": fragment, "source_quartet": quartet, "transmitted_voice": transmitted,
                         "sacch_information": info, "facch_information": facch.hex(),
                         "record_sha256": sha(rec), "raw_sha256": sha(raw), "air_sha256": sha(air)})
            records.append(rec); self.raw.append(raw); self.air.append(air)
        self.rows = rows
        files = {"input.records41": b"".join(records), "expected.records96": b"".join(a + b for a, b in zip(self.raw, self.air)),
                 "expected.raw48": b"".join(self.raw), "expected.air48": b"".join(self.air), "frames.json": dump(rows),
                 "linked-source.bin": source, "voice-reference.channels9": channels, "voice-reference-report.json": previous,
                 "primary-manifest.json": primary, "NXDNControl.cpp": control}
        for name, raw in files.items():
            (self.root / name).write_bytes(raw)
        self.manifest = {"schema": 1, "kind": "nxdn_air_v1", "frames": 9, "input_bytes": 369,
                         "output_bytes": 864, "sacch_calls": 9, "facch_calls": 6, "voice_pair_calls": 12,
                         "transmitted_voice_words": 24, "partial_second_sacch_cycle": True,
                         "voice_reference_report_sha256": sha(previous), "primary_manifest_sha256": sha(primary),
                         "generation_sources": {name.replace("/", "\\"): sha((analyze.ROOT / name).read_bytes()) for name in analyze.SOURCES},
                         "files": {name: {"bytes": len(raw), "sha256": sha(raw)} for name, raw in files.items()}}
        self.save_manifest()
        self.addCleanup(mock.patch.stopall)
        for key, value in {"SOURCE_SHA": sha(source), "CHANNEL_SHA": sha(channels), "REPORT_SHA": sha(previous),
                           "PRIMARY_SHA": sha(primary), "CONTROL_SHA": sha(control)}.items():
            mock.patch.object(analyze, key, value).start()

    def save_manifest(self):
        (self.root / "manifest.json").write_bytes(dump(self.manifest))

    def replace(self, name, raw):
        (self.root / name).write_bytes(raw)
        self.manifest["files"][name] = {"bytes": len(raw), "sha256": sha(raw)}
        self.save_manifest()

    def update_frames(self):
        self.replace("expected.raw48", b"".join(self.raw))
        self.replace("expected.air48", b"".join(self.air))
        self.replace("expected.records96", b"".join(a + b for a, b in zip(self.raw, self.air)))
        for i in range(9):
            self.rows[i]["raw_sha256"] = sha(self.raw[i])
            self.rows[i]["air_sha256"] = sha(self.air[i])
        self.replace("frames.json", dump(self.rows))

    def mutate_raw(self, frame, byte, mask):
        raw = bytearray(self.raw[frame]); raw[byte] ^= mask
        self.raw[frame] = bytes(raw)
        self.air[frame] = bytes(a ^ b for a, b in zip(raw, self.mask))
        self.update_frames()

    def test_complete_synthetic_layout_and_windows_source_paths(self):
        result = analyze.validate_inputs(self.root)
        self.assertEqual(len(result["expected_records96"]), 864)
        self.assertEqual(len(result["input_bytes"]), 369)
        self.assertEqual(len(result["frames"]), 9)
        self.assertEqual(result["whitening"], self.mask)

    def test_rehashed_source_id_metadata_rejected(self):
        self.rows[6]["transmitted_voice"][0]["source_id"] = 1
        self.replace("frames.json", dump(self.rows))
        with self.assertRaisesRegex(ValueError, "metadata"):
            analyze.validate_inputs(self.root)

    def test_rehashed_unused_quartet_lineage_rejected(self):
        self.rows[6]["source_quartet"][0] = 19
        self.replace("frames.json", dump(self.rows))
        with self.assertRaisesRegex(ValueError, "metadata"):
            analyze.validate_inputs(self.root)

    def test_rehashed_false_boolean_identity_rejected(self):
        self.rows[0]["id"] = False
        self.replace("frames.json", dump(self.rows))
        with self.assertRaisesRegex(ValueError, "metadata"):
            analyze.validate_inputs(self.root)

    def test_rehashed_input_padding_rejected(self):
        raw = bytearray((self.root / "input.records41").read_bytes()); raw[4] |= 1
        self.replace("input.records41", bytes(raw))
        with self.assertRaisesRegex(ValueError, "record bytes"):
            analyze.validate_inputs(self.root)

    def test_rehashed_input_order_rejected(self):
        raw = (self.root / "input.records41").read_bytes()
        self.replace("input.records41", raw[41:82] + raw[:41] + raw[82:])
        with self.assertRaisesRegex(ValueError, "record bytes"):
            analyze.validate_inputs(self.root)

    def test_rehashed_sync_corruption_rejected(self):
        self.mutate_raw(0, 0, 128)
        with self.assertRaisesRegex(ValueError, "Sync"):
            analyze.validate_inputs(self.root)

    def test_rehashed_lich_spacer_corruption_rejected(self):
        self.mutate_raw(0, 2, 4)  # Absolute bit21 is a fixed spacer.
        with self.assertRaisesRegex(ValueError, "LICH"):
            analyze.validate_inputs(self.root)

    def test_rehashed_lich_parity_corruption_rejected(self):
        self.mutate_raw(0, 4, 32)  # Absolute bit34 is logical parity.
        with self.assertRaisesRegex(ValueError, "LICH"):
            analyze.validate_inputs(self.root)

    def test_rehashed_voice_interval_corruption_rejected(self):
        self.mutate_raw(1, 12, 1)
        with self.assertRaisesRegex(ValueError, "voice interval"):
            analyze.validate_inputs(self.root)

    def test_rehashed_half_steal_swap_rejected(self):
        raw = self.raw[6]
        self.raw[6] = raw[:12] + raw[30:] + raw[12:30]
        self.air[6] = bytes(a ^ b for a, b in zip(self.raw[6], self.mask))
        self.update_frames()
        with self.assertRaisesRegex(ValueError, "voice interval"):
            analyze.validate_inputs(self.root)

    def test_rehashed_missing_whitening_rejected(self):
        self.air[0] = self.raw[0]
        self.update_frames()
        with self.assertRaisesRegex(ValueError, "whitening"):
            analyze.validate_inputs(self.root)

    def test_rehashed_wrong_whitening_rejected(self):
        raw = bytearray(self.air[0]); raw[47] ^= 128
        self.air[0] = bytes(raw)
        self.update_frames()
        with self.assertRaisesRegex(ValueError, "whitening"):
            analyze.validate_inputs(self.root)

    def test_rehashed_repeated_facch_half_corruption_rejected(self):
        self.mutate_raw(0, 12, 128)
        with self.assertRaisesRegex(ValueError, "FACCH placement"):
            analyze.validate_inputs(self.root)

    def test_separate_output_files_must_agree(self):
        raw = bytearray((self.root / "expected.records96").read_bytes()); raw[-1] ^= 1
        self.replace("expected.records96", bytes(raw))
        with self.assertRaisesRegex(ValueError, "interleaved"):
            analyze.validate_inputs(self.root)

    def test_primary_source_rehash_cannot_change_pinned_constant(self):
        self.replace("NXDNControl.cpp", (self.root / "NXDNControl.cpp").read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "source identity"):
            analyze.validate_inputs(self.root)

    def test_generator_hash_rejected(self):
        key = next(iter(self.manifest["generation_sources"]))
        self.manifest["generation_sources"][key] = "0" * 64
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "Generation source changed"):
            analyze.validate_inputs(self.root)

    def test_extra_inventory_path_rejected(self):
        self.manifest["files"]["extra.bin"] = {"bytes": 0, "sha256": sha(b"")}
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "inventory"):
            analyze.validate_inputs(self.root)


class OutputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.expected = bytes((frame * 13 + bit) % 256 for frame in range(9) for bit in range(96))
        self.output = self.root / "output.bin"
        self.summary = self.root / "summary.json"
        self.output.write_bytes(self.expected)
        self.summary.write_bytes(dump(analyze.SUMMARY))
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(analyze, "validate_inputs", return_value={"expected_records96": self.expected}).start()

    def inspect(self):
        return analyze.inspect_output(self.root, self.output, self.summary)

    def test_exact_output_and_summary(self):
        result = self.inspect()
        self.assertTrue(result["pass"], result)
        self.assertEqual(result["counts"]["frames"], 9)
        self.assertEqual(result["counts"]["different_bytes"], 0)

    def test_missing_or_extra_record_is_measurement_failure(self):
        for raw in (self.expected[:-96], self.expected + self.expected[:96], self.expected[:-1]):
            self.output.write_bytes(raw)
            result = self.inspect()
            self.assertFalse(result["measurement_pass"])
            self.assertTrue(result["quality_pass"])

    def test_reordered_output_is_quality_failure(self):
        self.output.write_bytes(self.expected[96:192] + self.expected[:96] + self.expected[192:])
        result = self.inspect()
        self.assertTrue(result["measurement_pass"])
        self.assertFalse(result["quality_pass"])
        self.assertEqual(result["counts"]["different_frames"], 2)

    def test_raw_and_air_byte_corruption_are_quality_failures(self):
        raw = bytearray(self.expected); raw[0] ^= 1; raw[48] ^= 1
        self.output.write_bytes(raw)
        result = self.inspect()
        self.assertTrue(result["measurement_pass"])
        self.assertFalse(result["quality_pass"])
        self.assertEqual(result["counts"]["different_raw_bytes"], 1)
        self.assertEqual(result["counts"]["different_air_bytes"], 1)

    def test_missing_whitening_output_is_quality_failure(self):
        self.output.write_bytes(self.expected[:48] + self.expected[:48] + self.expected[96:])
        self.assertFalse(self.inspect()["quality_pass"])

    def test_half_steal_swap_output_is_quality_failure(self):
        raw = bytearray(self.expected); start = 6 * 96
        raw[start + 12:start + 48] = raw[start + 30:start + 48] + raw[start + 12:start + 30]
        self.output.write_bytes(raw)
        self.assertFalse(self.inspect()["quality_pass"])

    def test_malformed_summary_is_measurement_failure(self):
        for raw in (dump({**analyze.SUMMARY, "frames": 8}), dump({**analyze.SUMMARY, "schema": True}),
                    dump({**analyze.SUMMARY, "extra": 0}), b'{"schema":1,"schema":1}',
                    dump(analyze.SUMMARY) * 2, b'{"frames":NaN}'):
            self.summary.write_bytes(raw)
            self.assertFalse(self.inspect()["measurement_pass"])

    def test_bad_inputs_are_measurement_failure(self):
        with mock.patch.object(analyze, "validate_inputs", side_effect=ValueError("input changed")):
            result = self.inspect()
        self.assertFalse(result["pass"])
        self.assertIn("input changed", result["measurement_issues"])

    def test_quality_failure_survives_bad_summary(self):
        self.output.write_bytes(bytes(864))
        self.summary.write_bytes(b"malformed")
        result = self.inspect()
        self.assertFalse(result["measurement_pass"])
        self.assertFalse(result["quality_pass"])
        self.assertTrue(result["details"])


if __name__ == "__main__":
    unittest.main()
