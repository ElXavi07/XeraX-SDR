"""Pure arithmetic/packing counterexamples; no corpus or native execution."""

from __future__ import annotations

import unittest

import encoding


ZERO = "0" * 49
ONES = "1" * 49


def bits72(raw: bytes) -> str:
    return "".join(f"{byte:08b}" for byte in raw)


def by_field(raw: bytes) -> dict[str, str]:
    fields = {"A": [None] * 24, "B": [None] * 23, "C": [None] * 25}
    for bit, (field, position) in zip(bits72(raw), encoding.channel_layout()):
        fields[field][position] = bit
    return {field: "".join(values) for field, values in fields.items()}


class ArithmeticTests(unittest.TestCase):
    def test_golay_landmarks_and_storage_convention(self):
        self.assertEqual(encoding._golay23(0), 0)
        self.assertEqual(encoding._golay24(0), 0)
        self.assertEqual(encoding._golay23(1), 0xC75)
        self.assertEqual(encoding._golay24(1), 0x18EB)
        self.assertEqual(encoding._golay23(0xFFF), 0x7FFFFF)
        self.assertEqual(encoding._golay24(0xFFF), 0xFFFFFF)

    def test_all_golay_words_systematic_parity_and_minimum_weight(self):
        # Polynomial remainder is independently computed by dynamic long
        # division, rather than repeating the encoder's fixed-degree loop.
        for information in range(4096):
            code23 = encoding._golay23(information)
            code24 = encoding._golay24(information)
            remainder = code23
            while remainder.bit_length() > 11:
                remainder ^= 0xC75 << (remainder.bit_length() - 12)
            self.assertEqual(remainder, 0)
            self.assertEqual(code23 >> 11, information)
            self.assertEqual(code24 >> 12, information)
            self.assertEqual(code24 >> 1, code23)
            self.assertEqual(code24.bit_count() % 2, 0)
            if information:
                self.assertGreaterEqual(code23.bit_count(), 7)
                self.assertGreaterEqual(code24.bit_count(), 8)

    def test_golay_linearity(self):
        for left, right in ((1, 2), (0x800, 0x001), (0xABC, 0x123), (0xFFF, 0xFFF)):
            self.assertEqual(encoding._golay24(left ^ right),
                             encoding._golay24(left) ^ encoding._golay24(right))

    def test_mask_primary_small_landmarks(self):
        # Three scalar primary PRNG_TABLE entries shifted right by one, not a
        # copied table. The registered external stage covers every A value.
        self.assertEqual(encoding._mask23(0), 0x42CC47 >> 1)
        self.assertEqual(encoding._mask23(1), 0x19D6FE >> 1)
        self.assertEqual(encoding._mask23(0xFFF), 0x0B3F09 >> 1)

    def test_mask_emits_updated_state_and_uses_a_information(self):
        self.assertEqual((16 * 0xFFF) >> 15, 1)
        self.assertEqual(encoding._mask23(0xFFF) >> 22, 0)
        a, b = 0xABC, 0x567
        source = f"{a:012b}{b:012b}" + "0" * 25
        fields = by_field(encoding.encode_word(source))
        self.assertEqual(int(fields["A"], 2), encoding._golay24(a))
        self.assertEqual(int(fields["B"], 2), encoding._golay23(b) ^ encoding._mask23(a))
        self.assertNotEqual(int(fields["B"], 2), encoding._golay23(b) ^ encoding._mask23(b))

    def test_information_type_and_range_rejected(self):
        for method in (encoding._golay23, encoding._golay24, encoding._mask23):
            for value in (True, False, 1.0, "1", None):
                with self.subTest(method=method.__name__, value=value):
                    with self.assertRaises(TypeError):
                        method(value)
            for value in (-1, 4096, 1 << 20):
                with self.assertRaises(ValueError):
                    method(value)


class LayoutTests(unittest.TestCase):
    def test_layout_complete_unique_and_immutable(self):
        layout = encoding.channel_layout()
        self.assertIs(type(layout), tuple)
        self.assertEqual(len(layout), 72)
        self.assertEqual(set(layout), {(field, index) for field, count in
                         (("A", 24), ("B", 23), ("C", 25)) for index in range(count)})
        with self.assertRaises(TypeError):
            layout[0] = ("C", 0)

    def test_primary_region_transition_positions(self):
        expected = {0: ("A", 0), 68: ("A", 17), 1: ("A", 18), 21: ("A", 23),
                    25: ("B", 0), 69: ("B", 11), 2: ("B", 12), 42: ("B", 22),
                    46: ("C", 0), 70: ("C", 6), 3: ("C", 7), 71: ("C", 24)}
        for position, value in expected.items():
            self.assertEqual(encoding.channel_layout()[position], value)

    def test_encode_dimensions_and_zero_fields(self):
        raw = encoding.encode_word(ZERO)
        self.assertIs(type(raw), bytes)
        self.assertEqual(len(raw), 9)
        fields = by_field(raw)
        self.assertEqual(fields["A"], "0" * 24)
        self.assertEqual(fields["B"], f"{0x216623:023b}")
        self.assertEqual(fields["C"], "0" * 25)

    def test_unprotected_source_bits_each_change_one_known_channel_bit(self):
        clean = bits72(encoding.encode_word(ZERO))
        for source_index in range(24, 49):
            word = ZERO[:source_index] + "1" + ZERO[source_index + 1:]
            changed = bits72(encoding.encode_word(word))
            actual = [i for i in range(72) if clean[i] != changed[i]]
            wanted = encoding.channel_layout().index(("C", source_index - 24))
            self.assertEqual(actual, [wanted])

    def test_source_validation(self):
        for value in (b"0" * 49, [0] * 49, 0, True, None):
            with self.assertRaises(TypeError):
                encoding.encode_word(value)
        for value in ("", "0" * 48, "0" * 50, "0" * 48 + "2", "0" * 48 + "\n"):
            with self.assertRaises(ValueError):
                encoding.encode_word(value)


class PackingTests(unittest.TestCase):
    def test_pair_is_not_separately_byte_aligned(self):
        left, right = "1" + "0" * 48, "0" * 48 + "1"
        packed = encoding.pack_words([left, right])
        self.assertEqual(packed, bytes.fromhex("80000000000000000000000040"))
        self.assertEqual(encoding.unpack_units(packed), [left, right])

    def test_second_word_starts_at_bit49(self):
        packed = encoding.pack_words([ZERO, "1" + "0" * 48])
        self.assertEqual(packed, bytes.fromhex("00000000000040000000000000"))

    def test_published_silence_pair(self):
        source = bytes.fromhex("f0000000000078000000000000")
        silence = "111100000000" + "0" * 37
        self.assertEqual(encoding.unpack_units(source), [silence, silence])
        self.assertEqual(encoding.pack_words([silence, silence]), source)

    def test_original_padding_is_opaque_and_normalized_only_on_pack(self):
        left, right = "10" * 24 + "1", "01" * 24 + "0"
        normalized = encoding.pack_words([left, right])
        for padding in range(64):
            original = normalized[:-1] + bytes([normalized[-1] | padding])
            extracted = encoding.unpack_units(original)
            self.assertEqual(extracted, [left, right])
            self.assertEqual(encoding.pack_words(extracted), normalized)
            self.assertEqual(original[-1] & 63, padding)

    def test_multiple_records_preserve_duplicates_and_order(self):
        words = [ZERO, ONES, ONES, ZERO, "01" * 24 + "0", ZERO]
        before = list(words)
        packed = encoding.pack_words(words)
        self.assertEqual(len(packed), 39)
        self.assertEqual(encoding.unpack_units(packed), words)
        self.assertEqual(words, before)
        self.assertTrue(all(packed[i] & 63 == 0 for i in range(12, len(packed), 13)))

    def test_zero_records_are_well_defined(self):
        self.assertEqual(encoding.pack_words([]), b"")
        self.assertEqual(encoding.unpack_units(b""), [])

    def test_pack_rejects_wrong_types_odd_count_and_invalid_words(self):
        for value in ((), (ZERO, ZERO), ZERO, iter([ZERO, ZERO]), None):
            with self.assertRaises(TypeError):
                encoding.pack_words(value)
        for value in ([ZERO], [ZERO] * 3):
            with self.assertRaises(ValueError):
                encoding.pack_words(value)
        with self.assertRaises(TypeError):
            encoding.pack_words([ZERO, 0])
        with self.assertRaises(ValueError):
            encoding.pack_words([ZERO, "1" * 48])

    def test_unpack_rejects_mutable_wrong_type_and_partial_record(self):
        for value in (bytearray(13), memoryview(bytes(13)), "0" * 13, [], None):
            with self.assertRaises(TypeError):
                encoding.unpack_units(value)
        for length in (1, 12, 14, 25, 27):
            with self.assertRaises(ValueError):
                encoding.unpack_units(bytes(length))


if __name__ == "__main__":
    unittest.main()
