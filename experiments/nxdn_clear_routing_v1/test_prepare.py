"""Bounded waveform and corruption controls; no native receiver or real corpus."""
import struct
import unittest
import prepare

class WaveformTests(unittest.TestCase):
    def test_msb_first_dibit_identity(self):
        self.assertEqual(prepare.dibits(bytes.fromhex('1be4')), bytes([0,1,2,3,3,2,1,0]))

    def test_parity_corruption_changes_only_registered_bit(self):
        raw = bytes(range(48)); changed = prepare.mutated_lich(raw)
        differences = [(i, a ^ b) for i, (a, b) in enumerate(zip(raw, changed)) if a != b]
        self.assertEqual(differences, [(4, 0x20)])
        self.assertEqual((changed[4] ^ raw[4]) & 0x10, 0)  # unchanged spacer
        self.assertEqual(prepare.mutated_lich(changed), raw)

    def test_exact_eight_sample_filter_boundaries(self):
        raw = bytes(48)
        actual = struct.unpack('<' + 'f' * (len(prepare.shaped([raw])) // 4), prepare.shaped([raw]))
        self.assertEqual(len(actual), 5760)
        self.assertEqual(actual[:17], (24000.0,) * 17)
        self.assertEqual(actual[17:25], (18000.0,12000.0,6000.0,0.0,-6000.0,-12000.0,-18000.0,-24000.0))
        self.assertEqual(actual[644:], (8000.0,) * (5760 - 644))

    def test_prefix_is_literal_cut_not_reshaped_end(self):
        parent = prepare.shaped([bytes(48)] * 10)
        self.assertEqual(len(parent), 40320 * 4)
        for cut in (9999, 10000, 10001):
            self.assertEqual(len(parent[:cut * 4]), cut * 4)
            self.assertEqual(parent[:cut * 4][-4:], parent[(cut - 1) * 4:cut * 4])

    def test_nine_configurations_eight_waveforms_two_cold_options(self):
        rows = prepare.CONFIGURATIONS
        self.assertEqual(len(rows), 9)
        self.assertEqual(len({r[1] for r in rows}), 8)
        self.assertEqual([r for r in rows if r[1] == 'cold'], [('cold_default','cold',0),('cold_fast','cold',1)])

    def test_wrong_frame_dimensions_fail_closed(self):
        for value in (b'', bytes(47), bytes(49), bytearray(48)):
            with self.assertRaises(ValueError): prepare.shaped([value])
            with self.assertRaises(ValueError): prepare.mutated_lich(value)

if __name__ == '__main__': unittest.main()
