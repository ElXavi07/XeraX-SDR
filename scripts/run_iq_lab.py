"""Exercise Android lab cases with the same engine and DSP, using the host parity runner."""
import argparse, hashlib, json, re, subprocess, wave
from pathlib import Path
parser=argparse.ArgumentParser()
parser.add_argument('runner',type=Path)
parser.add_argument('--output',type=Path,default=Path('build/iq-lab-report'))
args=parser.parse_args()
root=Path(__file__).resolve().parents[1]
assets=root/'upstream/dsd-neo/android/package/assets/iq-lab'
manifest=json.loads((assets/'manifest.json').read_text())
for name,digest in manifest['sha256'].items():
    assert hashlib.sha256((assets/name).read_bytes()).hexdigest()==digest,name
args.output.mkdir(parents=True,exist_ok=True)
reports=[]
tests=list(manifest['tests'])
# The frequency/BW trial knobs must reach the real DSP and still finish on valid input.
for offset,bw in [(-250,0),(250,0),(0,6000),(0,12000)]:
    tests.append(dict(name=f'P25 trial offset {offset} bandwidth {bw}',fixture='p25p1_cqpsk_cc',flag='-f1',mod='-mq',offset=offset,bandwidth=bw,exploratory=True))
for i,test in enumerate(tests):
    pcm=args.output/f'{i:02d}.wav'
    if pcm.exists(): pcm.unlink()
    command=[str(args.runner.resolve()),str(int(test.get('equalizer',False))),str(test.get('offset',0)),str(test.get('bandwidth',0)),
             '--frontend','none','--iq-replay',str(assets/(test['fixture']+'.iq.json')),'--iq-replay-rate','fast','-o','null','-w',str(pcm.resolve()),test['flag']]
    if test.get('mod'): command.append(test['mod'])
    if test.get('relaxedCrc'): command.append('-F')
    if test.get('ras'): command.append('--xerax-ras')
    result=subprocess.run(command,capture_output=True,timeout=120)
    evidence=(result.stdout+result.stderr).decode('utf-8',errors='replace')
    (args.output/f'{i:02d}.log').write_text(evidence,encoding='utf-8')
    matched=bool(re.search(test.get('expect','(?!)'),evidence))
    rejected=bool(test.get('reject') and re.search(test['reject'],evidence))
    pcmbytes=nonzero=peak=0
    if pcm.exists():
        import array,sys
        try:
            with wave.open(str(pcm),'rb') as wav:
                data=wav.readframes(wav.getnframes());pcmbytes=len(data)
                if wav.getsampwidth()==2:
                    values=array.array('h',data)
                    if sys.byteorder!='little': values.byteswap()
                    nonzero=sum(x!=0 for x in values);peak=max(map(abs,values),default=0)
        except (wave.Error,EOFError): pass
    metric=re.search(r'XeraX P25 FEC: accepted=(\d+) rejected=(\d+); voice_accepted=(\d+) voice_rejected=(\d+)',evidence)
    dmr=re.search(r'XeraX DMR evidence: checked=(\d+) suspected_ras=(\d+) rejected=(\d+)',evidence)
    report=dict(test,exitCode=result.returncode,passed=result.returncode==0 and matched and not rejected,
        pcmBytes=pcmbytes,nonzeroPcmSamples=nonzero,pcmPeak=peak,p25Fec=list(map(int,metric.groups())) if metric else None,
        dmrEvidence=list(map(int,dmr.groups())) if dmr else None)
    reports.append(report)
    print(test['name'], 'PASS' if report['passed'] else 'COMPARISON' if test.get('exploratory') or test.get('equalizer') else 'FAIL', f'PCM={pcmbytes} FEC={report["p25Fec"]}')
output=dict(schema=1,hardwareAcceptance=False,provenance=manifest['revision'],tests=reports)
(args.output/'report.json').write_text(json.dumps(output,indent=2)+'\n',encoding='utf-8')
assert all(r['passed'] for r in reports if not r.get('equalizer') and not r.get('exploratory')),'A baseline failed'
assert all(r['exitCode']==0 for r in reports),'A worker crashed'
