"""Encoder controls independent of the XeraX decoder and its lookup tables."""
import hashlib
import json
from pathlib import Path
import random
import tempfile
import unittest

import generate_vectors as vectors


# Fixed before any receiver result. Channel/raw goldens corroborated against
# primary MMDVM encoders at the pinned commit, with only a documented terminal
# FACCH puncture sentinel added to avoid its original out-of-bounds list read.
SACCH_GOLDEN = "001010010001100000010000110000110000000110000110110001101000"
FACCH_GOLDEN = ("000000000000000001000000001000000000100000000100000001000000001000"
                "000000100000011100000001100000010100000000000000010000000000000000"
                "010000000000")
UNWHITENED_HEX = ("cdf59d55f291810c30186c6800004020080404020081c060500010000400000040"
                   "20080404020081c060500010000400")
AIR_HEX = ("cdf59dd752190b0c92b0eee2820260288224aea08289e2eafa0838882c28000a42"
           "a2282c8628aaa1e2e0f88a18a0ae02")
# Pinned NXDNControl.cpp SCRAMBLER array; not a decoder table. This independent
# golden compares the full frame, including its unwhitened 20-bit FSW region.
WHITENING_MASK_HEX = ("00000082a0888a00a2a8828a820220088a20aaa28208228aaa0828882828000a0282"
                      "2028822aaa202280a88a08a0aa02")
HASHES = {
    "valid": "f9a9ddcf3005ff69815ac6edef66afbd9d2188bb17d327fcdb98c26f49d5c7ef",
    "wrong_all_crc": "14a140e5706e58ecd9b5d72ab96e6a5c1edbbc8f3f4072a019d0c5f174c6a7c9",
    "wrong_lich": "94f5a65aea462e1a4b046a3b32b47b7c2cf0cc61d19967c22490c358e11243ed",
}


def polynomial_crc(data, width, low_polynomial):
    """Alternate whole-polynomial GF(2) division, not register iteration."""
    message = 0
    for bit in data:
        message = (message << 1) | bit
    dividend = (((1 << width) - 1) << len(data)) ^ (message << width)
    divisor = (1 << width) | low_polynomial
    while dividend.bit_length() >= divisor.bit_length():
        dividend ^= divisor << (dividend.bit_length() - divisor.bit_length())
    return dividend


def from_packed(data):
    return bytes((value >> shift) & 3 for value in data for shift in (6, 4, 2, 0))


class IndependentEncoderTests(unittest.TestCase):
    def test_primary_crc_channel_and_complete_frame_goldens(self):
        data, meta = vectors.build_frame()
        self.assertEqual(meta["sacch"]["computed_crc"], 0x12)
        self.assertEqual(meta["facch_a"]["computed_crc"], 0x830)
        self.assertEqual(meta["sacch"]["channel_bits"], SACCH_GOLDEN)
        self.assertEqual(meta["facch_a"]["channel_bits"], FACCH_GOLDEN)
        self.assertEqual(bytes(meta["unwhitened_dibits"]), from_packed(bytes.fromhex(UNWHITENED_HEX)))
        self.assertEqual(data, from_packed(bytes.fromhex(AIR_HEX)))
        self.assertEqual(meta["lich_channel_bits"], "1101010101011111")
        self.assertEqual(meta["sacch"]["convolution_input_bits"], "000101110001000000000000000100100000")
        self.assertEqual(meta["facch_a"]["information_bits"], "00010000" + "0" * 72)

    def test_crc_matches_algebraic_division_for_fixed_varied_inputs(self):
        rng = random.Random(0x4E58444E)
        for width, polynomial in ((6, 0x27), (12, 0x80F)):
            for length in (0, 1, 2, 5, 8, 26, 32, 80, 96, 127):
                for _ in range(4):
                    data = tuple(rng.randrange(2) for _ in range(length))
                    self.assertEqual(vectors.crc(data, width, polynomial), polynomial_crc(data, width, polynomial))

    def test_crc_check_bits_zero_residual_and_wrong_crc_not_repaired_by_encoder(self):
        _, good = vectors.build_frame("valid")
        _, bad = vectors.build_frame("wrong_all_crc")
        for name in ("sacch", "facch_a", "facch_b"):
            a, b = good[name], bad[name]
            width = a["crc_width"]
            poly = 0x27 if width == 6 else 0x80F
            info = tuple(map(int, a["information_bits"]))
            self.assertEqual(a["information_bits"], b["information_bits"])
            self.assertEqual(a["computed_crc"], b["computed_crc"])
            self.assertEqual(a["transmitted_crc"] ^ b["transmitted_crc"], 1 << (width - 1))
            self.assertEqual(sum(x != y for x, y in zip(a["check_bits"], b["check_bits"])), 1)
            self.assertEqual(polynomial_crc(info + tuple(map(int, a["check_bits"])), width, poly), 0)
            self.assertNotEqual(polynomial_crc(info + tuple(map(int, b["check_bits"])), width, poly), 0)
            self.assertFalse(b["crc_expected_pass"])
            self.assertEqual(b["coded_bits"], vectors.bit_string(vectors.convolution(map(int, b["convolution_input_bits"]))))

    def test_convolution_impulse_and_independent_polynomial_order(self):
        self.assertEqual(vectors.bit_string(vectors.convolution((1,) + (0,) * 9)), "11010110110000000000")
        for number in range(256):
            data = vectors.bits(number, 8) + (0,) * 4
            shift = 0
            reference = []
            for value in data:
                shift = ((shift << 1) | value) & 31
                reference.extend((bin(shift & 0x19).count("1") % 2, bin(shift & 0x17).count("1") % 2))
            self.assertEqual(vectors.convolution(data), tuple(reference))
            # The fifth register bit was part of the last output; only the
            # four retained history bits constitute the next encoder state.
            self.assertEqual(shift & 15, 0)

    def test_interleave_basis_vectors_form_bijection_and_inverse(self):
        for rows, columns in ((12, 5), (16, 9)):
            observed = set()
            size = rows * columns
            for source_index in range(size):
                basis = tuple(int(index == source_index) for index in range(size))
                transmitted = vectors.interleave(basis, rows, columns)
                self.assertEqual(sum(transmitted), 1)
                destination = transmitted.index(1)
                self.assertEqual(destination, (source_index % rows) * columns + source_index // rows)
                observed.add(destination)
                restored = tuple(transmitted[(index % rows) * columns + index // rows] for index in range(size))
                self.assertEqual(restored, basis)
            self.assertEqual(observed, set(range(size)))

    def test_puncture_exact_lengths_and_removed_positions(self):
        for count, period, residue, expected in ((72, 6, 5, 60), (192, 4, 1, 144)):
            self.assertEqual(len(vectors.puncture((0,) * count, period, residue)), expected)
            for index in range(count):
                basis = tuple(int(i == index) for i in range(count))
                actual = vectors.puncture(basis, period, residue)
                self.assertEqual(sum(actual), int(index % period != residue))

    def test_whitening_matches_independent_primary_mask(self):
        data, meta = vectors.build_frame()
        mask = bytes.fromhex(WHITENING_MASK_HEX)
        raw = bytes.fromhex(UNWHITENED_HEX)
        self.assertEqual(len(mask), 48)
        primary_air = bytes(a ^ b for a, b in zip(raw, mask))
        self.assertEqual(from_packed(primary_air), data)
        unwhitened = bytes(meta["unwhitened_dibits"])
        self.assertEqual(data[:10], unwhitened[:10])
        self.assertEqual(vectors.whiten(data[10:]), unwhitened[10:])
        self.assertTrue(all((a & 1) == (b & 1) for a, b in zip(data, unwhitened)))

    def test_whitening_involution_period_and_explicit_seed(self):
        for seed in (1, 228, 511):
            data = bytes(range(4)) * 180
            self.assertEqual(vectors.whiten(vectors.whiten(data, seed), seed), data)
        period = vectors.whiten(bytes(1022))
        self.assertEqual(period[:511], period[511:])
        self.assertNotEqual(period[:182], bytes(182))
        for seed in (0, -1, 512, True):
            with self.assertRaises(ValueError):
                vectors.whiten(bytes(182), seed)

    def test_full_air_fsw_and_sign_projection_are_distinct(self):
        data, meta = vectors.build_frame()
        self.assertEqual(meta["fsw_bits"], "11001101111101011001")
        self.assertEqual(meta["fsw_dibits"], "3031331121")
        signs = "".join("1" if vectors.LEVELS[value] > 0 else "3" for value in data[:10])
        self.assertEqual(signs, "3131331131")
        self.assertNotEqual(meta["fsw_dibits"], signs)

    def test_wrong_lich_changes_only_parity_and_leaves_all_channel_codewords(self):
        good, gm = vectors.build_frame("valid")
        bad, bm = vectors.build_frame("wrong_lich")
        self.assertEqual(gm["lich_seven_bit"], 0x41)
        self.assertEqual(gm["lich_full_byte"], 0x83)
        self.assertEqual(bm["lich_full_byte"], 0x82)
        self.assertEqual([i for i, (a, b) in enumerate(zip(good, bad)) if a != b], [17])
        self.assertEqual(good[17] ^ bad[17], 2)
        for name in ("sacch", "facch_a", "facch_b"):
            self.assertEqual(gm[name], bm[name])
        self.assertFalse(bm["lich_expected_pass"])
        self.assertFalse(bm["expected_current_frame_proof"])
        self.assertEqual(bm["expected_channel_callbacks"], 0)

    def test_all_variants_have_exact_fixed_hashes_and_boundaries(self):
        for variant in vectors.VARIANTS:
            data, meta = vectors.build_frame(variant)
            self.assertIsInstance(data, bytes)
            self.assertEqual(len(data), 192)
            self.assertLessEqual(max(data), 3)
            self.assertEqual(hashlib.sha256(data).hexdigest(), HASHES[variant])
            self.assertEqual(meta["sha256"], HASHES[variant])
            self.assertEqual(meta["channel_frame_dibit_intervals"],
                             {"fsw": [0, 10], "lich": [10, 18], "sacch": [18, 48],
                              "facch_a": [48, 120], "facch_b": [120, 192]})
            self.assertEqual(meta["single_frame_sign_candidates"], {"positive": [0, 170], "negative": []})

    def test_generate_refuses_overwrite_and_freezes_exact_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "vectors"
            manifest = vectors.generate(directory)
            self.assertEqual(json.loads((directory / "vectors.json").read_text()), manifest)
            for variant in vectors.VARIANTS:
                raw = (directory / (variant + ".dibits")).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), HASHES[variant])
            for sequence in manifest["sequences"].values():
                self.assertEqual(sequence["total_dibits"], 800)
                self.assertEqual(sequence["sign_candidates"],
                                 {"positive": [32, 202, 224, 394, 416, 586, 608, 778], "negative": []})
            before = (directory / "vectors.json").read_bytes()
            with self.assertRaises(FileExistsError):
                vectors.generate(directory)
            self.assertEqual((directory / "vectors.json").read_bytes(), before)

    def test_invalid_inputs_rejected_without_assert_statements(self):
        for action in (lambda: vectors.bits(-1, 8), lambda: vectors.bits(256, 8),
                       lambda: vectors.bits(1, 0), lambda: vectors.crc((0,), 8, 7),
                       lambda: vectors.convolution((2,)), lambda: vectors.to_dibits((1,)),
                       lambda: vectors.to_dibits((True, 0)), lambda: vectors.whiten((4,)),
                       lambda: vectors.interleave((0,), 12, 5),
                       lambda: vectors.puncture((0,), 1, 0),
                       lambda: vectors.build_frame("unknown")):
            with self.assertRaises(ValueError):
                action()


if __name__ == "__main__":
    unittest.main()
