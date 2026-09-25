import unittest
import prepare


class TransformContract(unittest.TestCase):
    def test_discontinuity_has_explicit_original_indices(self):
        values = [float(n) for n in range(40)]
        data, origin, occurrence = prepare.transform(values, "drop", 7, 20)
        self.assertEqual(origin, list(range(7)) + list(range(27, 40)))
        self.assertEqual(data, [float(n) for n in origin])
        self.assertEqual(occurrence, [0] * 20)
        data, origin, occurrence = prepare.transform(values, "repeat", 7, 20)
        self.assertEqual(origin, list(range(27)) + list(range(7, 40)))
        self.assertEqual(data, [float(n) for n in origin])
        self.assertEqual(occurrence, [0] * 27 + [1] * 20 + [0] * 13)

    def test_amplitude_edits_preserve_coordinates(self):
        values = [1., -2., 3., -4., 5.]
        self.assertEqual(prepare.transform(values, "none"), (values, list(range(5)), [0] * 5))
        self.assertEqual(prepare.transform(values, "blank", 1, 3)[0], [1., 0., 0., 0., 5.])
        self.assertEqual(prepare.transform(values, "invert", 1, 3)[0], [1., 2., -3., 4., 5.])
        self.assertEqual(prepare.transform(values, "zero")[0], [0.] * 5)
        self.assertEqual(values, [1., -2., 3., -4., 5.])

    def test_outside_fault_is_rejected(self):
        for kind, q, count in [("other", 0, 0), ("drop", -1, 1), ("repeat", 2, 4), ("blank", 0, -1)]:
            with self.assertRaises(ValueError):
                prepare.transform([1., 2., 3.], kind, q, count)

    def test_registered_payloads_and_checksums_are_distinct(self):
        encoder = prepare.load_encoder()
        sources = []
        for payload in (0, 1):
            valid, meta = prepare.vector(encoder, payload, "S")
            bad, negative = prepare.vector(encoder, payload, "C")
            self.assertEqual(len(valid), 192)
            self.assertNotEqual(valid, bad)
            for name, width in (("sacch", 6), ("facch", 12)):
                good, wrong = meta[name], negative[name]
                self.assertEqual(good["information_bits"], wrong["information_bits"])
                self.assertEqual(good["computed_crc"], good["transmitted_crc"])
                self.assertEqual(good["transmitted_crc"] ^ wrong["transmitted_crc"], 1 << (width - 1))
                self.assertTrue(good["crc_expected_pass"])
                self.assertFalse(wrong["crc_expected_pass"])
                self.assertLess(wrong["transmitted_crc"], 1 << width)
            sources.append(meta)
        self.assertNotEqual(sources[0]["sacch"]["information_bits"], sources[1]["sacch"]["information_bits"])
        self.assertNotEqual(sources[0]["facch"]["information_bits"], sources[1]["facch"]["information_bits"])


if __name__ == "__main__":
    unittest.main()
