"""Known synthetic scrambling of real voice parameters; no RF-encryption claim."""
from pathlib import Path
import argparse, subprocess, re, json
p=argparse.ArgumentParser();p.add_argument('decoder',type=Path);p.add_argument('checker',type=Path);a=p.parse_args()
root=Path(__file__).resolve().parents[1];out=root/'build/nxdn-research';out.mkdir(exist_ok=True)
reports=[]
for rate,flag in [(48,'-fi'),(96,'-fn')]:
    capture=root/f'upstream/dsd-neo/android/package/assets/iq-lab/nxdn{rate}.iq.json'
    run=subprocess.run([str(a.decoder.resolve()),'--frontend','none','--iq-replay',str(capture),
        '--iq-replay-rate','fast','-o','null',flag,'-Z'],capture_output=True,timeout=90,check=True)
    text=(run.stdout+run.stderr).decode(errors='replace');records=[];position=-1
    for m in re.finditer(r'PF ([1-4X])/4|AMBE ([0-9A-F]+) err = \[(\w+)\] \[(\w+)\]',text):
        if m[1]:position=-1 if m[1]=='X' else (int(m[1])-1)*4
        elif 0<=position<16:
            records.append(f'{position} {int(m[4],16)} {m[2]}');position+=1
    payload=out/f'public{rate}-parameters.txt';payload.write_text('\n'.join(records)+'\n')
    result=subprocess.run([str(a.checker.resolve()),str(payload),str(rate)],capture_output=True,text=True,check=True)
    report=json.loads(result.stdout);reports.append(report);print(result.stdout.strip())
(out/'speech-replay-report.json').write_text(json.dumps(dict(ciphertextSynthetic=True,hardwareAcceptance=False,tests=reports),indent=2)+'\n')
