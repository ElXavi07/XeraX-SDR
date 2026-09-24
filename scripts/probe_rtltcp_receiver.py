"""Bounded actual RTL-TCP IQ/analog PCM probe; stop other clients first.

Stores aggregate measurements only, not received audio or IQ recordings.
"""
import argparse, array, json, math, socket, struct, subprocess, time
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('decoder',type=Path)
p.add_argument('--pcm-only',action='store_true')
p.add_argument('--host',default='127.0.0.1')
p.add_argument('--port',type=int,default=1235)
p.add_argument('--output',type=Path,default=Path('build/tcp-recovery-evidence'))
a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
report={'host':a.host,'port':a.port,'physicalReceiver':True,'phoneAudioVerified':False}
try:
    if not a.pcm_only:
        with socket.create_connection((a.host,a.port),timeout=4) as s:
            header=b''
            while len(header)<12:
                chunk=s.recv(12-len(header))
                if not chunk:break
                header+=chunk
            report['headerValid']=len(header)==12 and header[:4]==b'RTL0'
            report['headerHex']=header.hex()
            values=bytearray();start=time.monotonic()
            while time.monotonic()-start<1.5:
                data=s.recv(65536)
                if not data:break
                values.extend(data)
            report.update(iqBytes=len(values),iqBytesPerSecond=round(len(values)/(time.monotonic()-start)),
                          iqMinimum=min(values,default=0),iqMaximum=max(values,default=0),distinctIqValues=len(set(values)))
        # Allow rtl_tcp to release its previous client before using the production decoder.
        time.sleep(2)
    audio=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);audio.bind(('127.0.0.1',0));audio.settimeout(.25)
    audio_port=audio.getsockname()[1]
    cmd=[str(a.decoder.resolve()),'--frontend','none','-fA','-i',f'rtltcp:{a.host}:{a.port}:162400000:30:0:48:0:2',
         '-o',f'udp:127.0.0.1:{audio_port-2}']
    count=0;power=0;peak=0;nonzero=0
    with (a.output/'physical-decoder.log').open('wb') as output:
        process=subprocess.Popen(cmd,stdout=output,stderr=output)
        try:
            end=time.monotonic()+9
            while time.monotonic()<end and process.poll() is None:
                try:data=audio.recv(65536)
                except socket.timeout:continue
                v=array.array('h',data)
                count+=len(v);power+=sum(x*x for x in v);nonzero+=sum(x!=0 for x in v);peak=max(peak,max(map(abs,v),default=0))
        finally:
            if process.poll() is None:process.terminate()
            process.wait(timeout=5);audio.close()
    report.update(pcmSamples=count,pcmNonzeroSamples=nonzero,pcmPeak=peak,pcmRms=math.sqrt(power/count) if count else 0,
                  nfmFrequencyHz=162400000,squelch='off',termination='Bounded probe stops the live decoder')
    report['passed']=(a.pcm_only or (report['headerValid'] and report['iqBytes']>100000 and report['distinctIqValues']>16)) and count>48000 and nonzero>count*.5
except Exception as e:
    report.update(passed=False,error=str(e))
(a.output/'physical-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,indent=2))
raise SystemExit(0 if report['passed'] else 1)
