"""Reproducible channel-filter parity and impaired CQPSK comparisons. No RF claims."""
from pathlib import Path
import argparse,cmath,hashlib,json,math,random,re,subprocess
p=argparse.ArgumentParser()
p.add_argument('runner',type=Path)
p.add_argument('converter',type=Path)
p.add_argument('--output',type=Path,default=Path('build/reception-41-benchmark'))
a=p.parse_args(); a.output.mkdir(parents=True,exist_ok=True)
root=Path(__file__).resolve().parents[1]
fixtures=root/'upstream/dsd-neo/android/package/assets/iq-lab'
manifest=json.loads((fixtures/'manifest.json').read_text())
reports=[]
def run(name,meta,flag,expected,equalizer=False,mod=None):
    cmd=[str(a.runner.resolve()),str(int(equalizer)),'0','0','--frontend','none',
         '--iq-replay',str(meta.resolve()),'--iq-replay-rate','fast','-o','null',flag]
    if mod: cmd.append(mod)
    r=subprocess.run(cmd,capture_output=True,timeout=120)
    log=(r.stdout+r.stderr).decode('utf-8',errors='replace')
    (a.output/(name+'.log')).write_text(log,encoding='utf-8')
    match=re.search(r'XeraX P25 FEC: accepted=(\d+) rejected=(\d+); voice_accepted=(\d+) voice_rejected=(\d+)',log)
    result=dict(name=name,equalizer=equalizer,exitCode=r.returncode,matched=bool(re.search(expected,log)),
                fec=list(map(int,match.groups())) if match else None,
                iqSha256=hashlib.sha256(meta.with_suffix('').read_bytes()).hexdigest())
    reports.append(result); print(name,result['matched'],result['fec']); return result
for stem,flag,expected in [('p25p1_c4fm_cc','-f1','NAC/CC: 140'),
                            ('p25p1_cqpsk_cc','-f1','WACN: 92065; SYS: 0D5'),
                            ('dmr_voice','-fs','Color Code=02'),('nxdn48','-fi','Src=901'),
                            ('nxdn96','-fn','RAN 00')]:
    data=a.output/(stem+'-channel.iq')
    subprocess.run([str(a.converter.resolve()),str(fixtures/(stem+'.iq')),str(data)],check=True)
    meta=json.loads((fixtures/(stem+'.iq.json')).read_text())
    meta.update(sample_rate_hz=192000,base_decimation=4,fs4_shift_enabled=True,
                capture_center_frequency_hz=meta['center_frequency_hz']+48000,
                data_file=data.name,data_bytes=data.stat().st_size)
    path=data.with_suffix('.iq.json');path.write_text(json.dumps(meta,indent=2)+'\n')
    result=run(stem+'-channel',path,flag,expected,mod='-mq' if 'cqpsk' in stem else None)
    result['kind']='shared-channel-parity'
stem='p25p1_cqpsk_cc_simulcast'
source=(fixtures/(stem+'.iq')).read_bytes()
assert hashlib.sha256(source).hexdigest()==manifest['sha256'][stem+'.iq']
samples=[complex(source[i]-127.5,source[i+1]-127.5) for i in range(0,len(source),2)]
# The seed, additive noise level, carrier offset and extra echo are recorded.
# These are comparison scenarios; a hard case may correctly fail to decode.
for name,noise,offset,echo,delay in [('reference',0,0,0,0),('noise-mild',7,0,0,0),
    ('noise-heavy',20,0,0,0),('offset-echo',7,150,0.25,3),('strong-echo',10,-150,0.65,5)]:
    rng=random.Random(4100);data=bytearray();step=cmath.exp(2j*math.pi*offset/48000);phase=1+0j
    for i,x in enumerate(samples):
        y=(x+(samples[i-delay]*echo*cmath.exp(0.7j) if echo and i>=delay else 0))*phase/(1+echo)
        y+=complex(rng.gauss(0,noise),rng.gauss(0,noise));phase*=step
        data.extend((max(0,min(255,round(y.real+127.5))),max(0,min(255,round(y.imag+127.5)))))
    iq=a.output/(name+'.iq');iq.write_bytes(data)
    meta=json.loads((fixtures/(stem+'.iq.json')).read_text());meta.update(data_file=iq.name,data_bytes=len(data))
    path=iq.with_suffix('.iq.json');path.write_text(json.dumps(meta,indent=2)+'\n')
    for eq in [False,True]:
        result=run(name+('-equalizer' if eq else '-bypass'),path,'-f1','Group Voice Channel Grant Update - Implicit',eq,'-mq')
        result.update(kind='simulcast-comparison',seed=4100,noiseSigmaCu8=noise,offsetHz=offset,echoAmplitude=echo,echoDelaySamples=delay)
output=dict(schema=1,hardwareAcceptance=False,sourceRevision=manifest['revision'],
            sourceSha256=hashlib.sha256(source).hexdigest(),tests=reports)
(a.output/'report.json').write_text(json.dumps(output,indent=2)+'\n')
assert all(r['exitCode']==0 for r in reports),'Decoder crashed'
assert all(r['matched'] for r in reports if r['kind']=='shared-channel-parity'),'Channel filter lost a baseline'
