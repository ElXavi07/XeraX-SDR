import copy
import hashlib
from pathlib import Path
import unittest
from unittest.mock import patch

import policy


def frame(source, end):
    return {'source_frame': source, 'exact_channels': True, 'current_proof': True,
            'source_truncated': False, 'expected_variant': 'valid', 'end_consumed': end}


def pair():
    baseline, candidate = [], []
    for s, r, o, c in sorted(policy.MATRIX):
        identity = '%s-r%d-o%d-c%d' % (s, r, o, c)
        b = {'id': identity, 'scenario': s, 'frames': [frame(1, 8000), frame(2, 11840)] if s == 'valid' else []}
        a = copy.deepcopy(b)
        if s == 'valid':
            a['frames'].insert(0, frame(0, 4160))
        baseline.append(b)
        candidate.append(a)
    return {'cases': baseline, 'receiver_gate_pass': True}, {'cases': candidate, 'receiver_gate_pass': True}


class EntryPolicyTests(unittest.TestCase):
    def test_grid_and_exact_inspector_adapter(self):
        self.assertEqual(len(policy.OFFSETS), 20)
        self.assertEqual(len(set(policy.OFFSETS)), 20)
        self.assertEqual(len(policy.MATRIX), 156)
        function = policy.inspector()
        self.assertEqual(function.__globals__['MATRIX'], policy.MATRIX)
        self.assertEqual(function.__globals__['WAVEFORM_SAMPLES'], 16640)
        self.assertEqual(policy.digest(policy.ROOT / policy.INSPECTOR), policy.INSPECTOR_SHA)

    def test_frozen_source_change_rejected(self):
        with patch.object(policy, 'INSPECTOR_SHA', '0' * 64):
            with self.assertRaisesRegex(ValueError, 'Frozen source changed'):
                policy.inspector()

    def test_runner_records_adapter_and_all_exact_output_names(self):
        namespace = policy.runner()
        for name in policy.ADAPTER_INPUTS:
            self.assertIn(name, namespace['SOURCE_FILES'])
        paths = namespace['output_paths'](Path('artifacts'))
        self.assertEqual(len(paths), 163)
        self.assertEqual(len(set(paths)), 163)
        self.assertIn(Path('artifacts/valid-r14-o4480-c512.u32le'), paths)
        self.assertNotIn(Path('artifacts/valid-r14-o18-c512.u32le'), paths)

    def test_known_qualifying_pair(self):
        result = policy.quality(*pair())
        self.assertTrue(result['progression_pass'])
        self.assertEqual(len(result['qualifying_held_out_offsets']), 17)

    def test_later_baseline_frame_loss_is_not_hidden_by_early_gain(self):
        b, c = pair()
        case = next(x for x in c['cases'] if x['scenario'] == 'valid')
        case['frames'].pop()
        result = policy.quality(b, c)
        self.assertFalse(result['progression_pass'])
        self.assertTrue(any(x['reason'] == 'lost_or_delayed_baseline_frame' for x in result['failures']))

    def test_one_symbol_delay_boundary(self):
        b, c = pair()
        case = next(x for x in c['cases'] if x['scenario'] == 'valid')
        case['frames'][-1]['end_consumed'] += 20
        self.assertTrue(policy.quality(b, c)['progression_pass'])
        case['frames'][-1]['end_consumed'] += 1
        self.assertFalse(policy.quality(b, c)['progression_pass'])

    def test_anchor_only_gain_cannot_pass(self):
        b, c = pair()
        for case in c['cases']:
            if case['scenario'] == 'valid' and int(case['id'].split('-o')[1].split('-')[0]) not in policy.ANCHORS:
                case['frames'].pop(0)
        self.assertFalse(policy.quality(b, c)['progression_pass'])

    def test_all_six_cases_required_for_one_held_out_offset(self):
        b, c = pair()
        for case in c['cases']:
            if case['scenario'] == 'valid' and case['id'].endswith('-c512'):
                case['frames'].pop(0)
        self.assertEqual(policy.quality(b, c)['qualifying_held_out_offsets'], [])

    def test_historical_or_truncated_or_corrupt_result_cannot_preserve_frame(self):
        for field in ('current_proof', 'source_truncated', 'exact_channels'):
            b, c = pair()
            case = next(x for x in c['cases'] if x['scenario'] == 'valid')
            case['frames'][-1][field] = field == 'source_truncated'
            self.assertFalse(policy.quality(b, c)['progression_pass'], field)

    def test_false_proof_gate_is_absolute(self):
        b, c = pair()
        b['receiver_gate_pass'] = c['receiver_gate_pass'] = False
        self.assertFalse(policy.quality(b, c)['progression_pass'])

    def test_duplicate_frame_identity_rejected(self):
        case = {'frames': [frame(0, 4160), frame(0, 8000)]}
        with self.assertRaisesRegex(ValueError, 'Duplicate successful'):
            policy.good_frames(case)

    def test_incomplete_comparison_rejected(self):
        b, c = pair()
        c['cases'].pop()
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            policy.quality(b, c)


if __name__ == '__main__':
    unittest.main()
