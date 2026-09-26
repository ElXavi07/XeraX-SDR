import struct
import unittest
import prepare

class ShapingTests(unittest.TestCase):
    def values(self, frames):
        return [v[0] for v in struct.iter_unpack('<f', prepare.shaped(frames))]

    def test_known_preamble_transition_and_clamped_endpoints(self):
        values = self.values([bytes(192)])
        self.assertEqual(len(values), 5760)
        self.assertEqual([values[i] for i in (0, 19, 20, 21, 800, 5759)], [24000, 6000, 0, -6000, 8000, 8000])

    def test_one_parity_bit_has_only_declared_filter_support(self):
        original = [bytes(192), bytes(192)]
        altered = bytearray(original[1]); altered[17] ^= 2
        before = self.values(original); after = self.values([original[0], altered])
        differences = [b-a for a,b in zip(before, after)]
        changed = [i for i, value in enumerate(differences) if value]
        self.assertEqual(changed, list(range(4817, 4844)))
        self.assertEqual(differences[4817], -2000)
        self.assertEqual(differences[4843], -2000)
        self.assertEqual(min(differences), -16000)
        self.assertEqual(sum(differences), -320000)

    def test_invalid_frame_or_escaped_reference_is_rejected(self):
        for frame in (bytes(191), bytes([4])*192):
            with self.assertRaises(ValueError): prepare.shaped([frame])
        with self.assertRaises(ValueError): prepare.packed_path(prepare.ROOT, '../escaped')

if __name__ == '__main__': unittest.main()
