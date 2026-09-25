"""Synthetic record checks only; no registered corpus or native execution."""

from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import arithmetic


def source_pairs(words):
    return b"".join(int(words[i] + words[i + 1] + "000000", 2).to_bytes(13, "big")
                    for i in (0, 2))


def sacch_for(structure):
    message = f"{int.from_bytes(arithmetic.VCALL[:9], 'big'):072b}"
    index = 3 - structure
    bits = f"{structure:02b}000001" + message[index * 18:(index + 1) * 18] + "000000"
    return int(bits, 2).to_bytes(4, "big")


def record(profile=0xAE, structure=3, words=None, trailer=False):
    if words is None:
        words = ["0" * 49, "1" * 49, "01" * 24 + "0", "10" * 24 + "1"]
    if profile == 0x83:
        return bytes([profile]) + arithmetic.IDLE_SACCH + (arithmetic.TX_REL if trailer else arithmetic.VCALL) + bytes(26)
    facch = bytes(10) if profile == 0xAE else arithmetic.VCALL
    return bytes([profile]) + sacch_for(structure) + facch + source_pairs(words)


def bitstring(raw):
    return "".join(f"{byte:08b}" for byte in raw)


def flip(raw, byte, mask):
    copy = bytearray(raw)
    copy[byte] ^= mask
    return bytes(copy)


class FrameTests(unittest.TestCase):
    def test_dimensions_and_fixed_sync_lich_spacers(self):
        for profile, structure in ((0x83, 0), (0xAE, 3), (0xA6, 2), (0xAA, 1)):
            raw, air = arithmetic.encode_record(record(profile, structure))
            self.assertIs(type(raw), bytes)
            self.assertIs(type(air), bytes)
            self.assertEqual((len(raw), len(air)), (48, 48))
            bits = bitstring(raw)
            self.assertEqual(bits[:20], f"{0xCDF59:020b}")
            self.assertEqual(bits[20:36:2], f"{profile:08b}")
            self.assertEqual(bits[21:36:2], "1" * 8)
            self.assertEqual(bits[:20], bitstring(air)[:20])

    def test_voice_slots_match_frozen_independent_word_arithmetic(self):
        words = ["0" * 49, "1" * 49, "01" * 24 + "0", "10" * 24 + "1"]
        voice = arithmetic._load_checked(arithmetic.VOICE_PATH, arithmetic.VOICE_SHA256, "test_voice")
        raw, _ = arithmetic.encode_record(record(words=words))
        for index, word in enumerate(words):
            self.assertEqual(raw[12 + index * 9:21 + index * 9], voice.encode_word(word))

    def test_both_half_steal_directions_keep_only_correct_voice_pair(self):
        control, _ = arithmetic.encode_record(record(0x83))
        pure_first, _ = arithmetic.encode_record(record(0xAE, 2))
        pure_second, _ = arithmetic.encode_record(record(0xAE, 1))
        first, _ = arithmetic.encode_record(record(0xA6, 2))
        second, _ = arithmetic.encode_record(record(0xAA, 1))
        self.assertEqual(first[12:30], control[12:30])
        self.assertEqual(first[30:48], pure_first[30:48])
        self.assertEqual(second[12:30], pure_second[12:30])
        self.assertEqual(second[30:48], control[12:30])
        self.assertEqual(bitstring(first)[36:96], bitstring(pure_first)[36:96])
        self.assertEqual(bitstring(second)[36:96], bitstring(pure_second)[36:96])

    def test_stolen_source_pair_is_preserved_input_but_never_transmitted(self):
        first = record(0xA6, 2)
        self.assertEqual(arithmetic.encode_record(first), arithmetic.encode_record(flip(first, 15, 128)))
        second = record(0xAA, 1)
        self.assertEqual(arithmetic.encode_record(second), arithmetic.encode_record(flip(second, 28, 128)))
        self.assertNotEqual(arithmetic.encode_record(first), arithmetic.encode_record(flip(first, 28, 128)))
        self.assertNotEqual(arithmetic.encode_record(second), arithmetic.encode_record(flip(second, 15, 128)))

    def test_header_and_trailer_repeat_full_facch(self):
        header, _ = arithmetic.encode_record(record(0x83))
        trailer, _ = arithmetic.encode_record(record(0x83, trailer=True))
        self.assertEqual(header[12:30], header[30:48])
        self.assertEqual(trailer[12:30], trailer[30:48])
        self.assertEqual(header[:12], trailer[:12])
        self.assertNotEqual(header[12:], trailer[12:])

    def test_all_four_superframe_fragments_have_fixed_region_boundaries(self):
        frames = [arithmetic.encode_record(record(0xAE, structure))[0] for structure in range(4)]
        self.assertEqual(len({bitstring(frame)[36:96] for frame in frames}), 4)
        self.assertEqual(len({bitstring(frame)[:36] for frame in frames}), 1)
        self.assertEqual(len({frame[12:] for frame in frames}), 1)

    def test_channel_whitening_mask_domain_and_reset(self):
        masks = []
        for rec in (record(0x83), record(0xAE, 3), record(0xA6, 2), record(0xAA, 1)):
            raw, air = arithmetic.encode_record(rec)
            masks.append(bytes(a ^ b for a, b in zip(raw, air)))
            self.assertEqual(bytes(a ^ b for a, b in zip(air, masks[-1])), raw)
        self.assertEqual(len(set(masks)), 1)
        bits = bitstring(masks[0])
        self.assertEqual(bits[:20], "0" * 20)
        self.assertEqual(bits[21::2], "0" * 182)
        self.assertIn("1", bits[20::2])
        # First eight LFSR output bits can be independently read from the seed.
        self.assertEqual(bits[20:36:2], "00100111")
        # Repeated calls cannot share a continuing PN9 register.
        self.assertEqual(arithmetic.encode_record(record()), arithmetic.encode_record(record()))

    def test_historical_whitening_involution_on_arbitrary_dibits(self):
        control = arithmetic._load_checked(arithmetic.CONTROL_PATH, arithmetic.CONTROL_SHA256, "test_control")
        data = bytes([0, 1, 2, 3] * 45 + [3, 0])
        self.assertEqual(control.whiten(control.whiten(data, 228), 228), data)


class ValidationTests(unittest.TestCase):
    def test_exact_input_type_and_dimension(self):
        for value in (bytearray(record()), memoryview(record()), [0] * 41, None, "0" * 41):
            with self.assertRaises(TypeError):
                arithmetic.encode_record(value)
        for value in (b"", bytes(40), bytes(42), record() + record()):
            with self.assertRaises(ValueError):
                arithmetic.encode_record(value)

    def test_invalid_profile_and_parity(self):
        for value in (0x82, 0xAF, 0xA7, 0xAB, 0x43, 0xA2):
            with self.assertRaisesRegex(ValueError, "profile"):
                arithmetic.encode_record(bytes([value]) + record()[1:])

    def test_sacch_and_both_pair_padding(self):
        for byte in (4, 27, 40):
            for mask in (1, 2, 4, 8, 16, 32):
                with self.assertRaisesRegex(ValueError, "padding"):
                    arithmetic.encode_record(flip(record(), byte, mask))

    def test_ran_is_fixed(self):
        with self.assertRaisesRegex(ValueError, "RAN"):
            arithmetic.encode_record(flip(record(), 1, 1))

    def test_structure_fragment_mismatch(self):
        with self.assertRaisesRegex(ValueError, "fragment"):
            arithmetic.encode_record(flip(record(), 1, 64))
        with self.assertRaisesRegex(ValueError, "fragment"):
            arithmetic.encode_record(flip(record(), 2, 128))

    def test_half_steal_structure_is_fixed(self):
        for rec in (record(0xA6, 3), record(0xAA, 2)):
            with self.assertRaisesRegex(ValueError, "structure"):
                arithmetic.encode_record(rec)

    def test_unused_whole_field_placeholders_must_be_zero(self):
        with self.assertRaisesRegex(ValueError, "FACCH placeholder"):
            arithmetic.encode_record(flip(record(), 5, 1))
        with self.assertRaisesRegex(ValueError, "voice placeholder"):
            arithmetic.encode_record(flip(record(0x83), 15, 128))

    def test_fixed_clear_control_fields(self):
        for rec, offset in ((record(0x83), 5), (record(0xA6, 2), 12), (record(0xAA, 1), 14)):
            with self.assertRaisesRegex(ValueError, "information"):
                arithmetic.encode_record(flip(rec, offset, 128))
        with self.assertRaisesRegex(ValueError, "IDLE"):
            arithmetic.encode_record(flip(record(0x83), 2, 128))


class LoaderTests(unittest.TestCase):
    def test_hash_mismatch_blocks_execution(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "altered.py"
            path.write_text("raise RuntimeError('must never execute')\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "identity"):
                arithmetic._load_checked(path, "0" * 64, "blocked_source")

    def test_preserved_copy_paths_produce_identical_frames(self):
        expected = arithmetic.encode_record(record())
        with tempfile.TemporaryDirectory() as temporary:
            control = Path(temporary) / "control.py"
            voice = Path(temporary) / "voice.py"
            control.write_bytes(arithmetic.CONTROL_PATH.read_bytes())
            voice.write_bytes(arithmetic.VOICE_PATH.read_bytes())
            with mock.patch.object(arithmetic, "CONTROL_PATH", control), mock.patch.object(arithmetic, "VOICE_PATH", voice):
                self.assertEqual(arithmetic.encode_record(record()), expected)
                voice.write_bytes(voice.read_bytes() + b"\n")
                with self.assertRaisesRegex(ValueError, "identity"):
                    arithmetic.encode_record(record())

    def test_checked_bytes_are_executed_without_import_cache(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "module.py"
            raw = b"value = 41\n"
            path.write_bytes(raw)
            module = arithmetic._load_checked(path, hashlib.sha256(raw).hexdigest(), "private_test_module")
            self.assertEqual(module.value, 41)
            self.assertEqual(module.__file__, str(path.resolve()))


if __name__ == "__main__":
    unittest.main()
