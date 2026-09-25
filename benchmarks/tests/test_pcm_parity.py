"""Regression gates must catch actual audio/input differences, not just counts."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import wave

spec = importlib.util.spec_from_file_location('pcm_parity', Path(__file__).resolve().parents[2] / 'scripts/check_iq_parity.py')
parity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parity)


class PcmParityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.report = self.root / 'report.json'
        self.rows = []
        for variant in ('baseline', 'candidate'):
            directory = self.root / variant
            directory.mkdir()
            self.audio(variant, b'\x01\x00' * 160)
            self.rows.append({'case': 'fixture', 'repeat': 0, 'variant': variant,
                              'warmup': False, 'status': 'completed', 'stage': 'iq',
                              'case_sha256': 'capture-hash', 'duration_seconds': 0.02,
                              'directory': variant,
                              'metrics': {field: None for field in parity.FIELDS}})

    def audio(self, variant, data):
        with wave.open(str(self.root / variant / 'audio.wav'), 'wb') as wav:
            wav.setparams((1, 2, 8000, 0, 'NONE', 'not compressed'))
            wav.writeframes(data)

    def check(self):
        self.report.write_text(json.dumps({'runs': self.rows}), encoding='utf-8')
        return parity.check(self.report)

    def test_matching_pcm(self):
        result = self.check()
        self.assertTrue(result['exact_observation_parity'])
        self.assertEqual(result['pcm_pairs'], 1)

    def test_one_changed_sample_is_detected(self):
        self.audio('candidate', b'\x02\x00' + b'\x01\x00' * 159)
        self.assertFalse(self.check()['exact_observation_parity'])

    def test_missing_audio_is_detected(self):
        (self.root / 'candidate/audio.wav').unlink()
        self.assertFalse(self.check()['exact_observation_parity'])

    def test_different_input_is_rejected(self):
        self.rows[1]['case_sha256'] = 'different-capture'
        self.assertFalse(self.check()['exact_observation_parity'])

    def test_decoder_failure_is_rejected(self):
        self.rows[1]['status'] = 'timeout'
        self.assertFalse(self.check()['exact_observation_parity'])

    def test_missing_pair_is_rejected(self):
        self.rows.pop()
        self.assertFalse(self.check()['exact_observation_parity'])

    def test_duplicate_run_is_rejected(self):
        self.rows.append(copy.deepcopy(self.rows[1]))
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            self.check()

    def test_warmup_and_unrelated_variants_are_excluded(self):
        extra = copy.deepcopy(self.rows[0]); extra['variant'] = 'unrelated'
        warmup = copy.deepcopy(self.rows[0]); warmup['warmup'] = True
        self.rows.extend([extra, warmup])
        self.assertTrue(self.check()['exact_observation_parity'])
