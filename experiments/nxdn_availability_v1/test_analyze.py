"""Counterexamples before candidate receiver execution; no native tools."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import types
import unittest

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('availability_analyze',HERE/'analyze.py')
a=importlib.util.module_from_spec(spec); spec.loader.exec_module(a)
path=HERE.parent/'nxdn_active_boundaries_v1/test_analyze.py'; raw=path.read_bytes()
if hashlib.sha256(raw).hexdigest()!='4c1476c7832327b5a525663048c245b52b7b5ff6929f449afaa9137e14968dee': raise ValueError('Frozen synthetic fixtures changed')
f=types.ModuleType('frozen_active_test_fixtures'); f.__file__=str(path)
exec(compile(raw,str(path),'exec'),f.__dict__)

def prefix(cut=6160):
    frames,_,_=f.prefix_fixture(cut)
    for frame in frames:
        for call,kind in zip(frame['end']['body_calls'],frame['classes']): call['available']=int(kind=='complete')
        for route in frame['routes']:
            for side in ('begin','end'): route[side]['available_slots']=1
    return {'frames':frames}

class AvailabilityTests(unittest.TestCase):
    def test_complete_early_slot_survives_later_eof(self):
        for cut in (6160,6161): self.assertEqual(a.explicit_availability(prefix(cut)),[])
    def test_no_complete_word_at_6159(self): self.assertEqual(a.explicit_availability(prefix(6159)),[])
    def test_delivered_zero_is_not_unavailable(self):
        v=prefix(); v['frames'][1]['end']['body']='0'*182
        self.assertEqual(a.explicit_availability(v),[])
    def test_complete_read_falsely_reported_missing(self):
        v=prefix(); v['frames'][1]['end']['body_calls'][73]['available']=0
        with self.assertRaises(ValueError): a.explicit_availability(v)
    def test_partial_read_falsely_reported_complete(self):
        v=prefix(6159); v['frames'][1]['end']['body_calls'][73]['available']=1
        with self.assertRaises(ValueError): a.explicit_availability(v)
    def test_empty_read_falsely_reported_complete(self):
        v=prefix(); v['frames'][1]['end']['body_calls'][74]['available']=1
        with self.assertRaises(ValueError): a.explicit_availability(v)
    def test_missing_checked_reader_observation_rejected(self):
        v=prefix(); del v['frames'][1]['end']['body_calls'][0]['available']
        with self.assertRaises(ValueError): a.explicit_availability(v)
    def test_mask_may_not_include_unavailable_later_slot(self):
        v=prefix(); r=v['frames'][1]['routes'][0]
        r['begin']['available_slots']=r['end']['available_slots']=3
        with self.assertRaises(ValueError): a.explicit_availability(v)
    def test_mask_may_not_omit_complete_slot(self):
        v=prefix(); r=v['frames'][1]['routes'][0]
        r['begin']['available_slots']=r['end']['available_slots']=0
        with self.assertRaises(ValueError): a.explicit_availability(v)
    def test_mask_may_not_change_during_route(self):
        v=prefix(); v['frames'][1]['routes'][0]['end']['available_slots']=0
        with self.assertRaises(ValueError): a.explicit_availability(v)
    def test_unavailable_route_fails_even_without_synthesis(self):
        v=prefix(6159); r=copy.deepcopy(prefix()['frames'][1]['routes'][0])
        r['begin']['available_slots']=r['end']['available_slots']=0; r['synthesis']=[]
        v['frames'][1]['routes']=[r]
        self.assertEqual(len(a.explicit_availability(v)),1)
    def test_status_and_flags_cannot_restore_missing_samples(self):
        for flags in (3,3|32,3|64,3|128):
            v=prefix(6159); r=copy.deepcopy(prefix()['frames'][1]['routes'][0])
            r['begin']['available_slots']=r['end']['available_slots']=0
            for row in r['synthesis']: row['status']=0; row['result_after']['flags']=flags
            v['frames'][1]['routes']=[r]
            self.assertTrue(a.explicit_availability(v))
    def test_only_added_observation_is_removed(self):
        baseline=[{'kind':'frame_end','body':'0123','body_calls':[{'before':1,'after':2}]}]
        candidate=copy.deepcopy(baseline); candidate[0]['body_calls'][0]['available']=1
        candidate[0].update(availability_schema=1,available_slots=1)
        self.assertTrue(a.compare_complete_baseline(candidate,baseline))
        candidate[0]['body']='0122'; self.assertFalse(a.compare_complete_baseline(candidate,baseline))
    def test_changed_call_identity_cannot_be_normalized_away(self):
        baseline=[{'kind':'route_begin','call':{'source':901}}]
        candidate=copy.deepcopy(baseline); candidate[0]['call']['source']=902
        self.assertFalse(a.compare_complete_baseline(candidate,baseline))
    def test_grid_is_exactly_twenty(self):
        cases=a.expected_cases(); self.assertEqual(len(cases),10)
        self.assertEqual(len({v['id'] for v in cases}),10)
        self.assertTrue(all(v['fast']==1 for v in cases))
    def grid(self):
        pairs={}
        for case in a.expected_cases():
            pairs[case['id']]={}
            for mode in (0,1):
                pairs[case['id']][mode]={'case':case,'summary':{'observed':mode},'measurement_pass':True,
                    **{k:True for k in ('routing_pass','exposure_pass','negative_pass','finite_voice_safety_pass','availability_guard_pass')},
                    'retention_pass':case['configuration']!='active_bad_lich','semantic':[],'chunk_semantic':[],'trace_sha256':'same'}
        return pairs,{'cases':a.expected_cases()}
    def test_targeted_pass_does_not_erase_recovery_failure(self):
        p,m=self.grid(); out=a.compare(p,m)
        self.assertTrue(out['targeted_guard_pass']); self.assertFalse(out['progression_pass']); self.assertFalse(out['product_promotion'])
    def test_missing_case_fails_measurement(self):
        p,m=self.grid(); p.pop(next(iter(p))); self.assertFalse(a.compare(p,m)['measurement_pass'])
    def test_duplicate_detail_type_cannot_collapse(self):
        p,m=self.grid(); item=next(iter(p.values())); item['0']=item[0]
        self.assertFalse(a.compare(p,m)['measurement_pass'])
    def test_detail_or_chunk_difference_fails(self):
        for field in ('semantic','chunk_semantic','trace_sha256'):
            p,m=self.grid(); p[next(iter(p))][0][field]='changed'
            self.assertFalse(a.compare(p,m)['measurement_pass'])
    def test_json_roundtrip_preserves_decision(self):
        p,m=self.grid(); self.assertEqual(a.compare(p,m),a.compare(json.loads(json.dumps(p)),m))

if __name__=='__main__': unittest.main()
