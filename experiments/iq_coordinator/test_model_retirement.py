import unittest
from model_retirement import explore


class RetirementModelTests(unittest.TestCase):
    def test_retired_weak_storage_remains_bounded(self):
        for bound in (1, 2, 3):
            for cap in (4, 7):
                with self.subTest(bound=bound, cap=cap):
                    result = explore(bound, cap)
                    self.assertTrue(result['ok'], result)
                    self.assertLessEqual(result['peak_reserved_units'], cap)
                    self.assertEqual(result['fully_released_terminal_states'], bound + 1)

    def test_deliberate_bad_admission_and_retirement_have_witnesses(self):
        for mutant in ('split_admission', 'release_at_object_destruction', 'destroy_ledger_with_facade'):
            with self.subTest(mutant=mutant):
                result = explore(mutant=mutant)
                self.assertFalse(result['ok'], result)
                self.assertTrue(any('BROKEN.' in event for event in result['witness']))

    def test_invalid_model_profiles_are_rejected(self):
        with self.assertRaises(ValueError): explore(0)
        with self.assertRaises(ValueError): explore(cap=3)
        with self.assertRaises(ValueError): explore(mutant='unknown')


if __name__ == '__main__':
    unittest.main()
