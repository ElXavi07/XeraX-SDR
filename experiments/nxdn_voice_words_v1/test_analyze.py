"""Synthetic evidence counterexamples; no registered corpus or native execution.

Probe fixtures deliberately use fictitious channel/source relationships and mock
only validate_inputs. Input fixtures replace the primary-manifest and linked-byte
pins explicitly, so they cannot pass as real registered inputs. No encoder is
imported and no decoder output is used as source truth.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import analyze


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def dumped(value):
    return (json.dumps(value, separators=(",", ":")) + "\n").encode()


def source_fixture(linked, silence):
    # Local synthetic truth construction, separate from the checker's helpers.
    answer = []
    for label, raw in (("announcement", linked), ("upstream_silence", silence)):
        extracted = []
        for offset in range(0, len(raw), 13):
            bits = f"{int.from_bytes(raw[offset:offset + 13], 'big'):0104b}"
            extracted.extend((bits[:49], bits[49:98]))
        answer.extend((label, i, value) for i, value in enumerate(extracted))
    answer += [("zero", 0, "0" * 49), ("ones", 0, "1" * 49)]
    answer += [("onehot", i, f"{1 << (48 - i):049b}") for i in range(49)]
    answer += [("sweep_a", i, f"{i << 37:049b}") for i in range(4096)]
    answer += [("sweep_b", i, f"{i << 25:049b}") for i in range(4096)]
    answer += [("pair_padding", 0, "0" * 49)]
    return [{"id": i, "kind": kind, "source_index": index, "bits": bits}
            for i, (kind, index, bits) in enumerate(answer)]


class InputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        linked = bytes(range(130))  # Intentionally not the registered asset.
        primary = {"repositories": analyze.PINS, "files": [
            {"path": "MMDVM-Host/synthetic", "commit": analyze.PINS["MMDVM-Host"],
             "sha256": "0" * 64, "git_blob_sha1": "1" * 40}]}
        primary_raw = dumped(primary)
        rows = source_fixture(linked, analyze.SILENCE)
        packed = b"".join(int(rows[i]["bits"] + rows[i + 1]["bits"] + "000000", 2).to_bytes(13, "big")
                          for i in range(0, len(rows), 2))
        files = {"linked-source.bin": linked, "silence-source.bin": analyze.SILENCE,
                 "primary-manifest.json": primary_raw, "words.json": dumped(rows),
                 "input.pairs13": packed, "expected.channels9": bytes(analyze.WORDS * 9)}
        for name, raw in files.items():
            (self.root / name).write_bytes(raw)
        self.manifest = {"schema": 1, "kind": "nxdn_voice_words_v1", "words": 8266,
                         "base_words": 73, "pairs": 4133, "probe_calls": 27044,
                         "primary_pins": analyze.PINS, "primary_files": {"MMDVM-Host/synthetic": "0" * 64},
                         "primary_manifest_sha256": sha(primary_raw),
                         "linked_original_padding": [linked[i] & 63 for i in range(12, 130, 13)],
                         "silence_original_padding": 0,
                         "generation_sources": {name: sha(Path(analyze.__file__).with_name(name).read_bytes())
                                                for name in ("prepare.py", "encoding.py")},
                         "files": {name: {"bytes": len(raw), "sha256": sha(raw)} for name, raw in files.items()}}
        self.save_manifest()
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(analyze, "PRIMARY_MANIFEST_SHA256", sha(primary_raw)).start()
        mock.patch.object(analyze, "LINKED_SHA256", sha(linked)).start()

    def save_manifest(self):
        (self.root / "manifest.json").write_bytes(dumped(self.manifest))

    def replace_file(self, name, raw):
        (self.root / name).write_bytes(raw)
        self.manifest["files"][name] = {"bytes": len(raw), "sha256": sha(raw)}
        self.save_manifest()

    def test_synthetic_valid_inputs_reconstruct_truth(self):
        sources, channels = analyze.validate_inputs(self.root)
        self.assertEqual(len(sources), 8266)
        self.assertEqual(len(channels), 8266)
        self.assertEqual(sources[22], "0" * 49)
        self.assertEqual(sources[23], "1" * 49)
        self.assertEqual(sources[24], "1" + "0" * 48)
        self.assertEqual(sources[72], "0" * 48 + "1")
        self.assertEqual(sources[4168], "1" * 12 + "0" * 37)
        self.assertEqual(sources[8264], "0" * 12 + "1" * 12 + "0" * 25)
        self.assertEqual(sources[8265], "0" * 49)

    def test_rehashed_mislabeled_source_rejected(self):
        rows = json.loads((self.root / "words.json").read_bytes())
        rows[73]["kind"] = "sweep_b"
        self.replace_file("words.json", dumped(rows))
        with self.assertRaisesRegex(ValueError, "identity/label/content"):
            analyze.validate_inputs(self.root)

    def test_rehashed_source_index_rejected(self):
        rows = json.loads((self.root / "words.json").read_bytes())
        rows[20]["source_index"] = 1  # Duplicate silence bits cannot hide wrong lineage.
        self.replace_file("words.json", dumped(rows))
        with self.assertRaisesRegex(ValueError, "identity/label/content"):
            analyze.validate_inputs(self.root)

    def test_rehashed_source_order_rejected(self):
        rows = json.loads((self.root / "words.json").read_bytes())
        rows[24], rows[25] = rows[25], rows[24]
        self.replace_file("words.json", dumped(rows))
        with self.assertRaises(ValueError):
            analyze.validate_inputs(self.root)

    def test_rehashed_normalized_padding_rejected(self):
        raw = bytearray((self.root / "input.pairs13").read_bytes())
        raw[12] |= 1
        self.replace_file("input.pairs13", bytes(raw))
        with self.assertRaisesRegex(ValueError, "padding"):
            analyze.validate_inputs(self.root)

    def test_rehashed_normalized_content_rejected(self):
        raw = bytearray((self.root / "input.pairs13").read_bytes())
        raw[0] ^= 128
        self.replace_file("input.pairs13", bytes(raw))
        with self.assertRaisesRegex(ValueError, "packing"):
            analyze.validate_inputs(self.root)

    def test_unhashed_file_edit_rejected(self):
        (self.root / "expected.channels9").write_bytes(bytes(8266 * 9 - 1))
        with self.assertRaisesRegex(ValueError, "hash/size"):
            analyze.validate_inputs(self.root)

    def test_primary_pin_self_replacement_rejected(self):
        self.manifest["primary_manifest_sha256"] = "a" * 64
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "closure identity"):
            analyze.validate_inputs(self.root)

    def test_original_padding_provenance_rejected(self):
        self.manifest["linked_original_padding"][0] ^= 1
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "Original announcement padding"):
            analyze.validate_inputs(self.root)

    def test_false_boolean_count_rejected(self):
        self.manifest["schema"] = True
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "count"):
            analyze.validate_inputs(self.root)

    def test_generator_identity_rejected(self):
        self.manifest["generation_sources"]["encoding.py"] = "0" * 64
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "Generator source"):
            analyze.validate_inputs(self.root)


class ResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = [f"{i:049b}" for i in range(analyze.WORDS)]
        cls.channels = [bytes([i % 256]) * 9 for i in range(analyze.WORDS)]
        cls.rows = []

        def add(word, mutation, mode):
            raw = bytearray(cls.channels[word])
            truth = [int(bit) for bit in cls.sources[word]]
            if mutation >= 0:
                raw[mutation // 8] ^= 128 >> (mutation % 8)
                # Four columns, each containing 18 linear channel bits.
                linear = (mutation % 4) * 18 + mutation // 4
                if linear >= 47:
                    truth[linear - 23] ^= 1
            cls.rows.append({"seq": len(cls.rows), "word": word, "mutation": mutation,
                             "mode": mode, "input": raw.hex(), "status": 0, "bits": truth,
                             "input_unchanged": 1, "c0_errors": 0, "protected_errors": 0,
                             "c4_errors": 0, "total_errors": 0, "flags": 0})

        for word in range(8266):
            for mode in ("hard", "soft"):
                add(word, -1, mode)
        for word in range(73):
            for mutation in range(72):
                for mode in ("hard", "soft"):
                    add(word, mutation, mode)
        cls.lines = [dumped(row) for row in cls.rows]

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.primary = self.root / "primary.channels9"
        self.primary.write_bytes(b"".join(self.channels))
        self.summary = self.root / "stdout.json"
        self.summary.write_bytes(dumped(analyze.PRIMARY_SUMMARY))
        self.probe = self.root / "probe.jsonl"
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(analyze, "validate_inputs", return_value=(self.sources, self.channels)).start()

    def inspect(self, replacements=None, lines=None):
        output = list(self.lines) if lines is None else lines
        for index, changes in (replacements or {}).items():
            row = dict(self.rows[index])
            row.update(changes)
            output[index] = dumped(row)
        self.probe.write_bytes(b"".join(output))
        return analyze.inspect_probe(self.root, self.primary, self.probe)

    def test_complete_synthetic_grid_counts(self):
        report = self.inspect()
        self.assertTrue(report["pass"], report)
        expected = {"rows": 27044, "checked_calls": 27044, "clean": 16532,
                    "protected_a": 3504, "protected_b": 3358, "unprotected_c": 3650,
                    "hard": 13522, "soft": 13522}
        self.assertEqual({k: report["counts"][k] for k in expected}, expected)

    def test_primary_exact_summary_and_channels(self):
        report = analyze.inspect_primary(self.root, self.primary, self.summary)
        self.assertTrue(report["pass"], report)

    def test_primary_mismatch_is_quality_failure(self):
        raw = bytearray(self.primary.read_bytes()); raw[17] ^= 1
        self.primary.write_bytes(raw)
        report = analyze.inspect_primary(self.root, self.primary, self.summary)
        self.assertTrue(report["measurement_pass"])
        self.assertFalse(report["quality_pass"])
        self.assertEqual(report["details"][0]["word"], 1)

    def test_primary_short_output_is_measurement_failure(self):
        self.primary.write_bytes(self.primary.read_bytes()[:-1])
        self.assertFalse(analyze.inspect_primary(self.root, self.primary, self.summary)["measurement_pass"])

    def test_primary_summary_boolean_duplicate_or_extra_rejected(self):
        for raw in (dumped({**analyze.PRIMARY_SUMMARY, "schema": True}),
                    dumped({**analyze.PRIMARY_SUMMARY, "extra": 0}),
                    b'{"schema":1,"schema":1}\n',
                    dumped(analyze.PRIMARY_SUMMARY) * 2):
            self.summary.write_bytes(raw)
            self.assertFalse(analyze.inspect_primary(self.root, self.primary, self.summary)["measurement_pass"])

    def test_missing_row_is_measurement_failure(self):
        self.assertFalse(self.inspect(lines=self.lines[:-1])["measurement_pass"])

    def test_duplicate_row_is_measurement_failure(self):
        lines = list(self.lines); lines[1] = lines[0]
        self.assertFalse(self.inspect(lines=lines)["measurement_pass"])

    def test_reordered_row_is_measurement_failure(self):
        lines = list(self.lines); lines[0], lines[1] = lines[1], lines[0]
        self.assertFalse(self.inspect(lines=lines)["measurement_pass"])

    def test_extra_row_is_measurement_failure(self):
        self.assertFalse(self.inspect(lines=self.lines + [self.lines[-1]])["measurement_pass"])

    def test_wrong_actual_mutation_input_is_measurement_failure(self):
        report = self.inspect({16532: {"input": self.channels[0].hex()}})
        self.assertFalse(report["measurement_pass"])
        self.assertTrue(report["quality_pass"])

    def test_wrong_clean_output_is_quality_failure(self):
        report = self.inspect({0: {"bits": [1] * 49}})
        self.assertTrue(report["measurement_pass"])
        self.assertFalse(report["quality_pass"])
        self.assertEqual(report["counts"]["wrong_output"], 1)

    def test_unprotected_original_word_is_not_success(self):
        # Transmitted index3 is C7: source bit31 must change.
        report = self.inspect({16532 + 3 * 2: {"bits": [0] * 49}})
        self.assertTrue(report["measurement_pass"])
        self.assertFalse(report["quality_pass"])
        self.assertEqual(report["details"][0]["source_bit"], 31)

    def test_protected_bit_cannot_be_mislabeled_unprotected(self):
        wrong = [0] * 49; wrong[24] = 1
        report = self.inspect({16532: {"bits": wrong}})  # Position0 is A0.
        self.assertFalse(report["quality_pass"])
        self.assertEqual(report["details"][0]["category"], "protected_a")

    def test_negative_status_and_changed_input_are_quality_failures(self):
        report = self.inspect({0: {"status": -1}, 1: {"input_unchanged": 0}})
        self.assertTrue(report["measurement_pass"])
        self.assertFalse(report["quality_pass"])
        self.assertEqual(report["counts"]["negative_status"], 1)
        self.assertEqual(report["counts"]["changed_input"], 1)

    def test_decoder_nonbinary_return_is_content_failure(self):
        report = self.inspect({0: {"bits": [-1] * 49}})
        self.assertTrue(report["measurement_pass"])
        self.assertFalse(report["quality_pass"])

    def test_invalid_type_or_shape_is_measurement_failure(self):
        report = self.inspect({0: {"status": True}, 1: {"bits": [0] * 48}})
        self.assertFalse(report["measurement_pass"])

    def test_malformed_json_is_retained_as_measurement_failure(self):
        lines = list(self.lines); lines[2] = b'{"seq":NaN}\n'
        self.assertFalse(self.inspect(lines=lines)["measurement_pass"])

    def test_probe_is_blocked_on_primary_disagreement(self):
        raw = bytearray(self.primary.read_bytes()); raw[0] ^= 128
        self.primary.write_bytes(raw)
        report = self.inspect()
        self.assertFalse(report["pass"])
        self.assertEqual(report["counts"]["checked_calls"], 0)


if __name__ == "__main__":
    unittest.main()
