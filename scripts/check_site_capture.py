"""Four actual channel filters and native protocol decoders; no hardware claim."""
import json,re,subprocess,hashlib
from pathlib import Path
r=Path(__file__).resolve().parents[1];out=r/'build/site-capture-414';out.mkdir(exist_ok=True)
fixtures=r/'upstream/dsd-neo/android/package/assets/iq-lab'
runner=r/'build/iq-lab-clang/tests/dsd-neo_test_receiver_lab.exe'
converter=r/'build/checks/site_capture.exe'
mixed=[('dmr_voice','-fs','Color Code=02'),('nxdn48','-fi','Src=901'),('nxdn96','-fn','RAN 00'),('p25p1_c4fm_cc','-f1','NAC/CC: 140')]
reports=[]
for scenario,tests in [('four-dmr',[mixed[0]]*4),('four-protocols',mixed)]:
 prefix=out/(scenario+'-')
 subprocess.run([str(converter),*[str(fixtures/(s+'.iq')) for s,_,_ in tests],str(prefix)],check=True,timeout=120)
 for lane,(stem,flag,expected) in enumerate(tests):
  data=Path(str(prefix)+str(lane)+'.iq');meta=json.loads((fixtures/(stem+'.iq.json')).read_text())
  meta.update(sample_rate_hz=192000,base_decimation=4,fs4_shift_enabled=True,capture_center_frequency_hz=meta['center_frequency_hz']+48000,data_file=data.name,data_bytes=data.stat().st_size)
  path=data.with_suffix('.iq.json');path.write_text(json.dumps(meta))
  run=subprocess.run([str(runner),'0','0','0','--frontend','none','--iq-replay',str(path),'--iq-replay-rate','fast','-o','null',flag],capture_output=True,timeout=120)
  log=(run.stdout+run.stderr).decode('utf-8',errors='replace');data.with_suffix('.log').write_text(log,encoding='utf-8')
  passed=run.returncode==0 and bool(re.search(expected,log))
  reports.append(dict(scenario=scenario,lane=lane,fixture=stem,passed=passed,exitCode=run.returncode,expected=expected,iqSha256=hashlib.sha256(data.read_bytes()).hexdigest()))
  print(scenario,lane,stem,'PASS' if passed else 'FAIL')
(out/'report.json').write_text(json.dumps(dict(hardwareAcceptance=False,spanHz=1025000,captureRate=1536000,tests=reports),indent=2)+'\n')
assert all(t['passed'] for t in reports)
