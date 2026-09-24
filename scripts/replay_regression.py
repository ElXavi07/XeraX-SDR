"""Replay one real I/Q recording through one or more desktop decoder builds.

Uses the upstream replay_ab log summary format, with rotated per-repeat order.
No capture is synthesized and no reception claim is produced without a recording.
"""
import argparse
import csv
import hashlib
import json
import re
import subprocess
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--capture', type=Path, required=True, help='DSD-neo I/Q sidecar JSON')
    p.add_argument('--mode', required=True, choices=['-fA','-fU','-fW','-f1','-ft','-fs','-fi','-fn'])
    p.add_argument('--repeats', type=int, default=12)
    p.add_argument('--timeout', type=int, default=900)
    p.add_argument('--out', type=Path, required=True, help='New directory for this run')
    p.add_argument('decoders', type=Path, nargs='+')
    a = p.parse_args()
    if not 1 <= a.repeats <= 100 or not 1 <= a.timeout <= 3600:
        p.error('repeats must be 1..100 and timeout 1..3600 seconds')
    if not a.capture.is_file() or not all(d.is_file() for d in a.decoders):
        p.error('capture and every decoder must exist')
    json.loads(a.capture.read_text(encoding='utf-8-sig'))
    a.out.mkdir(parents=True, exist_ok=False)
    decoders = [d.resolve() for d in a.decoders]
    (a.out/'inputs.json').write_text(json.dumps({'capture':str(a.capture.resolve()),
        'captureSidecarSha256':hashlib.sha256(a.capture.read_bytes()).hexdigest(),
        'mode':a.mode,'repeats':a.repeats,'decoders':[
            {'path':str(d),'sha256':hashlib.sha256(d.read_bytes()).hexdigest()} for d in decoders]},indent=2))
    failures = 0
    with (a.out/'summary.tsv').open('w',newline='',encoding='utf-8') as handle:
        writer = csv.writer(handle,delimiter='\t');writer.writerow(['variant','case','rep','errs','voice','sync','exit'])
        for rep in range(a.repeats):
            for k in range(len(decoders)):
                index = (k+rep)%len(decoders);decoder=decoders[index];name=f'{index+1}-{decoder.stem}'
                log = a.out/f'{name}-r{rep+1}.log'
                try:
                    with log.open('wb') as output:
                        result=subprocess.run([str(decoder),'--frontend','none',a.mode,'--iq-replay',
                            str(a.capture.resolve()),'--iq-replay-rate','realtime','-o','null'],
                            stdout=output,stderr=subprocess.STDOUT,timeout=a.timeout,check=False)
                        code=result.returncode
                except subprocess.TimeoutExpired:
                    code=124
                except OSError as error:
                    log.write_text(str(error));code=126
                text=log.read_text(encoding='utf-8',errors='replace')
                errors=re.findall(r'Total audio errors: ([0-9]+)',text)
                voice=sum('Voice' in line for line in text.splitlines())
                sync=sum('Sync: ' in line for line in text.splitlines())
                # A failed run must not enter the upstream report as a success.
                errs=errors[-1] if errors and code==0 else 'NA'
                writer.writerow([name,a.capture.name,rep+1,errs,voice,sync,code]);handle.flush()
                failures+=code!=0
                print(f'{name} repeat {rep+1}: voice={voice}, sync={sync}, errors={errs}, exit={code}',flush=True)
    print('Compare error/voice AND decoded voice counts with upstream/dsd-neo/tools/replay_ab_report.py.')
    return 1 if failures else 0

if __name__=='__main__':
    raise SystemExit(main())
