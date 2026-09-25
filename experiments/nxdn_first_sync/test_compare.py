import copy
import unittest
import compare

def fixtures():
    before, after, raw = [], [], []
    for scenario in ('valid', 'bad_crc', 'bad_lich', 'mixed', 'one_fsw', 'zero', 'random'):
        for ramp in (8, 14):
            for offset in range(20 if scenario == 'valid' else 1):
                for chunk in (1, 37, 512):
                    identity = f'{scenario}-r{ramp}-o{offset}-c{chunk}'
                    def frames(indices):
                        return [{'source_frame': i, 'end_consumed': 4480 + 3840*i,
                                 'expected_variant': 'valid', 'current_proof': True,
                                 'exact_channels': True, 'source_truncated': False} for i in indices]
                    before.append({'id': identity, 'scenario': scenario, 'frames': frames((1,2,3)) if scenario == 'valid' else []})
                    after.append({'id': identity, 'scenario': scenario, 'frames': frames((0,1,2,3)) if scenario == 'valid' else []})
                    observed = {'frames': [dict.fromkeys(compare.CACHE_FIELDS, chunk)], 'pop_count': 100}
                    raw.append({'kind': 'case', 'scenario': scenario, 'ramp': ramp, 'offset': offset, 'chunk': chunk, 'observed': observed})
    return {'receiver_gate_pass': True, 'cases': before}, {'receiver_gate_pass': True, 'cases': after}, raw

class ComparisonPolicies(unittest.TestCase):
    def setUp(self): self.before, self.after, self.raw = fixtures()
    def test_all_declared_pairs_gain_one_frame(self):
        cases, errors = compare.quality(self.before, self.after)
        self.assertEqual(errors, []); self.assertEqual(len(cases), 120)
        self.assertTrue(all(case['first_crc_gain_ms'] == 80 for case in cases))
    def test_no_gain_rejected(self):
        self.assertTrue(compare.quality(self.before, self.before)[1])
    def test_lost_later_frame_rejected(self):
        self.after['cases'][0]['frames'].pop(2)
        self.assertTrue(compare.quality(self.before, self.after)[1])
    def test_truncated_first_frame_never_counts(self):
        self.after['cases'][0]['frames'][0]['source_truncated'] = True
        self.assertTrue(compare.quality(self.before, self.after)[1])
    def test_historical_confirmation_never_counts(self):
        self.after['cases'][0]['frames'][0]['current_proof'] = False
        self.assertTrue(compare.quality(self.before, self.after)[1])
    def test_wrong_bits_never_count(self):
        self.after['cases'][0]['frames'][0]['exact_channels'] = False
        self.assertTrue(compare.quality(self.before, self.after)[1])
    def test_exactly_seventy_ms_is_not_more_than_seventy(self):
        self.after['cases'][0]['frames'][0]['end_consumed'] = 4960
        self.assertTrue(compare.quality(self.before, self.after)[1])
    def test_negative_receiver_gate_cannot_be_hidden_by_gain(self):
        self.after['receiver_gate_pass'] = False
        self.assertTrue(compare.quality(self.before, self.after)[1])
    def test_incomplete_grid_rejected(self):
        self.after['cases'].pop()
        with self.assertRaises(ValueError): compare.quality(self.before, self.after)
    def test_cache_differences_allowed_only(self):
        self.assertTrue(compare.chunk_gate(self.raw))
        self.raw[1]['observed']['pop_count'] = 99
        self.assertFalse(compare.chunk_gate(self.raw))
    def test_missing_chunk_rejected(self):
        self.raw.pop()
        self.assertFalse(compare.chunk_gate(self.raw))
    def test_chunk_trace_difference_rejected(self):
        hashes = {}
        for index, row in enumerate(self.raw):
            row['pop_trace'] = str(index)
            hashes[str(index)] = 'same'
        self.assertTrue(compare.chunk_gate(self.raw, hashes))
        hashes['1'] = 'different'
        self.assertFalse(compare.chunk_gate(self.raw, hashes))
    def test_historical_proof_cost_is_reported_separately(self):
        row = {'kind': 'case', 'scenario': 'mixed', 'observed': {'events': [], 'frames': [
            {'result': result, 'sync_consumed': 100, 'end_consumed': 200 + result}
            for result in (0, 1, 2)]}}
        result = compare.costs([row])['mixed']
        self.assertEqual(result['result0_body_samples'], 100)
        self.assertEqual(result['result1_body_samples'], 101)
        self.assertEqual(result['no_current_proof_body_samples'], 201)
        self.assertEqual(result['current_proof_calls'], 1)
    def test_duplicate_foreign_basenames_rejected(self):
        value = {'artifact_sha256': {'a/file': '1', 'b/file': '1'}, 'vector_sha256': {}}
        with self.assertRaises(ValueError): compare.normalized_analysis(value)
    def test_baseline_change_rejected(self):
        a = {'analysis': {'receiver_gate_pass': True}, 'rows': [1], 'report': {'output_sha256': {}}}
        b = copy.deepcopy(a); b['rows'] = [2]
        with self.assertRaises(ValueError): compare.baseline_matches(a, b)

if __name__ == '__main__': unittest.main()
