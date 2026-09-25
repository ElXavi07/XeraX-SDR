"""Verify paired replay evidence and decoded PCM before promoting an optimization."""
import argparse
import hashlib
import json
from pathlib import Path
import wave

FIELDS = ('assertions_passed', 'frame_payload_sha256', 'decoded_vocoder_frames',
          'frame_error_sum', 'p25_fec', 'dmr_evidence', 'audio_errors_reported', 'audio')


def pcm_hash(path):
    with wave.open(str(path), 'rb') as wav:
        fmt = (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getnframes())
        digest = hashlib.sha256()
        while block := wav.readframes(16384):
            digest.update(block)
    return fmt, digest.hexdigest()


def check(report_path, baseline='baseline', candidate='candidate'):
    report_path = Path(report_path).resolve()
    report = json.loads(report_path.read_text(encoding='utf-8'))
    rows = {}
    for row in report['runs']:
        if row['warmup'] or row['variant'] not in (baseline, candidate):
            continue
        key = (row['case'], row['repeat'], row['variant'])
        if key in rows:
            raise ValueError('Duplicate measured run: ' + repr(key))
        rows[key] = row
    pairs = sorted({(case, repeat) for case, repeat, _ in rows})
    if not pairs or baseline == candidate:
        raise ValueError('Distinct variants and at least one measured pair are required')
    differences, pcm_pairs, payload_pairs = [], 0, 0
    for case, repeat in pairs:
        a, b = rows.get((case, repeat, baseline)), rows.get((case, repeat, candidate))
        if not a or not b or a['status'] != 'completed' or b['status'] != 'completed':
            differences.append([case, repeat, 'missing or failed process'])
            continue
        for field in ('stage', 'case_sha256', 'duration_seconds'):
            if a[field] != b[field]:
                differences.append([case, repeat, 'input mismatch: ' + field])
        for field in FIELDS:
            if a['metrics'][field] != b['metrics'][field]:
                differences.append([case, repeat, field])
        payload_pairs += bool(a['metrics']['frame_payload_sha256'] and b['metrics']['frame_payload_sha256'])
        paths = [report_path.parent / r['directory'] / 'audio.wav' for r in (a, b)]
        if paths[0].exists() != paths[1].exists():
            differences.append([case, repeat, 'audio availability'])
        elif all(p.exists() for p in paths):
            pcm_pairs += 1
            if pcm_hash(paths[0]) != pcm_hash(paths[1]):
                differences.append([case, repeat, 'decoded PCM bytes or format'])
    return {'schema': 1, 'paired_runs': len(pairs), 'pcm_pairs': pcm_pairs,
            'nonempty_payload_pairs': payload_pairs, 'differences': differences,
            'exact_observation_parity': not differences,
            'scope': 'Same observed decoder results, including existing failures; not proof of correct off-air bits'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    result = check(args.report)
    encoded = json.dumps(result, indent=2) + '\n'
    if args.out:
        args.out.write_text(encoded, encoding='utf-8', newline='\n')
    print(encoded)
    raise SystemExit(0 if result['exact_observation_parity'] else 1)
