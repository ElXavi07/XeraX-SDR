import unittest
from model_contract import explore


class AbstractOwnershipTests(unittest.TestCase):
    def test_declared_boundaries_preserve_ownership(self):
        for bound in (1, 2, 3):
            with self.subTest(bound=bound):
                result = explore(bound)
                self.assertTrue(result['ok'], result)
                self.assertGreater(result['fully_released_terminal_states'], 0)

    def test_negative_controls_produce_actionable_witnesses(self):
        for mutant in ('reuse_unclaimed', 'revoke_held', 'close_before_drain'):
            with self.subTest(mutant=mutant):
                result = explore(mutant=mutant)
                self.assertFalse(result['ok'], result)
                self.assertTrue(result['witness'])
                self.assertIn('BROKEN.', result['witness'][-1])

    def test_invalid_exploration_inputs_are_rejected(self):
        with self.assertRaises(ValueError): explore(100)
        with self.assertRaises(ValueError): explore(mutant='unknown')


if __name__ == '__main__':
    unittest.main()
