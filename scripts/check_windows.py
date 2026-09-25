"""Exercise the shipped Windows GUI host with local synthetic RF and real PortAudio.

No receiver, account, radio service or external network is used. Audio acceptance
is a software result, not a claim that a human heard intelligible radio traffic.
"""
import argparse, json, math, os, socket, struct, subprocess, threading, time, wave
from pathlib import Path

p=argparse.ArgumentParser()
p.add_argument('executable',type=Path)
p.add_argument('--output',type=Path,default=Path('build/windows-check'))
p.add_argument('--live-tls',action='store_true',help='Verify HTTPS provider rejection of invalid fixture keys; no paid API requests.')
a=p.parse_args(); a.output.mkdir(parents=True,exist_ok=True)
exe=a.executable.resolve(); out=a.output.resolve(); reports=[]

def run(name, arguments=(), seconds=3, language='en', extra_env=None):
    env=os.environ.copy()
    env.update(QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software',XERAX_SMOKE_LANGUAGE=language,
               XERAX_SMOKE_REPORT=str(out/f'{name}.json'),XERAX_SMOKE_SCREENSHOT=str(out/f'{name}.png'),XERAX_SMOKE_TRACE=str(out/f'{name}.trace'))
    if extra_env: env.update(extra_env)
    # Only the staged application and Windows runtime may satisfy DLL dependencies.
    env['PATH']=str(exe.parent)+';'+env['SYSTEMROOT']+'\\System32;'+env['SYSTEMROOT']
    cmd=[str(exe),'--smoke-seconds',str(seconds)]
    if arguments: cmd+=['--receiver-args',*arguments]
    with (out/f'{name}.log').open('wb') as log:
        result=subprocess.run(cmd,env=env,stdout=log,stderr=log,timeout=seconds+25)
    assert result.returncode==0, (name,result.returncode,(out/f'{name}.log').read_text(errors='replace')[-3000:])
    report=json.loads((out/f'{name}.json').read_text())
    warnings=(out/f'{name}.trace.qml.log').read_text(errors='replace')
    assert not any(s in warnings for s in ('ReferenceError:', 'TypeError:', 'Unable to assign', 'Binding loop', 'failed to load component')), (name,warnings)
    report.update(name=name,exitCode=result.returncode)
    reports.append(report)
    return report

assert run('ui-en')['state']==0
assert run('ui-es',language='es')['state']==0
r=run('home-es',language='es',extra_env={'XERAX_SMOKE_HOME':'1'})
assert r['state']==0 and r['details']['homeScreen']['visible'] and r['details']['homeScreen']['parentOpacity']==1,r
for name,route,language,extra in [
    ('home-en','','en',{}),('home-light','','en',{'XERAX_SMOKE_APPEARANCE':'1'}),
    ('home-compact','','es',{'XERAX_SMOKE_SIZE':'600x740'}),
    ('home-hidpi','','en',{'QT_SCALE_FACTOR':'1.5'}),
    ('close-from-setup','receiver','en',{'XERAX_SMOKE_NATIVE_CLOSE':'1'}),
    ('receiver-setup','receiver','en',{}),('range-setup','range','en',{}),
    ('range-close','range-close','en',{}),('scanner','scan','en',{}),
    ('scanner-es','scan','es',{}),('scanner-range','scan-range','en',{}),
    ('receiver-lab','lab','en',{}),('calls','calls','en',{}),('preferences','tools','en',{}),
    ('ai-connect','ai','en',{})]:
    r=run(name,language=language,extra_env={'XERAX_SMOKE_HOME':'1','XERAX_SMOKE_ROUTE':route,**extra})
    d=r['details']; assert d['windowIconAvailable'],r
    if route:assert d['routeActivated'],r
    if route in ('range','scan-range'):assert d['exploreSetupOpen'] and d['rangeMode'],r
    if route=='receiver':assert d['exploreSetupOpen'] and not d['rangeMode'],r
    if route=='range-close':assert not d['exploreSetupOpen'] and d['closeActivated'],r
    if route=='scan':assert d['currentTab']==3 and d['desktopScanScreen']['visible'],r
    if route=='lab':assert d['desktopLabOpen'] and d['desktopLabScreen']['visible'],r
    if route=='calls':assert d['currentTab']==1,r
    if route=='tools':assert d['currentTab']==2,r
    if route=='ai':assert d['aiReceiverScreen']['visible'],r
    if name=='home-compact':assert not d['desktopSidebar']['visible'],r
if a.live_tls:
    r=run('provider-https',seconds=12,extra_env={'XERAX_SMOKE_TLS':'1','XERAX_SMOKE_HOME':'1'})
    assert r['details']['openaiTlsHttpStatus']==401 and r['details']['deepseekTlsHttpStatus']==401,r
r=run('test-tones',extra_env={'XERAX_SMOKE_TONES':'1'})
assert 'accepted both test tones' in r['media']['audioTestStatus'] and r['pcmFrames']==0 and r['outputFrames']==0,r
with wave.open(str(out/'replay.wav'),'wb') as clip:
    clip.setparams((1,2,8000,0,'NONE','not compressed'))
    clip.writeframes(b''.join(struct.pack('<h',round(1500*math.sin(2*math.pi*440*i/8000))) for i in range(8000)))
r=run('wav-replay',extra_env={'XERAX_SMOKE_WAV':str(out/'replay.wav')})
assert r['details']['playbackStarted'] and not r['details']['playError'] and not r['media']['replaying'] and not r['suppressed'],r

for mode,flag,carrier,deviation in [('nfm','-fA',162400000,2500),('am','-fU',162400000,0),('wfm','-fW',100000000,25000)]:
    stop=threading.Event(); commands=[]; errors=[]
    settings={'rate':1536000,'center':carrier}
    server=socket.socket(); server.bind(('127.0.0.1',0)); server.listen(1); server.settimeout(15)
    def receive(conn):
        pending=b''
        while not stop.is_set():
            try:
                data=conn.recv(4096)
                if not data:return
                pending+=data
                while len(pending)>=5:
                    cmd,value=struct.unpack('!BI',pending[:5]);pending=pending[5:];commands.append([cmd,value])
                    if cmd==1:settings['center']=value
                    if cmd==2:settings['rate']=value
            except socket.timeout:pass
            except OSError:return
    def transmit():
        try:
            conn,_=server.accept()
            with conn:
                conn.settimeout(.5)
                header=b'RTL0'+struct.pack('!II',5,29)
                for chunk in (header[:1],header[1:5],header[5:]):conn.sendall(chunk);time.sleep(.01)
                threading.Thread(target=receive,args=(conn,),daemon=True).start()
                cached=None
                while not stop.is_set():
                    current=settings['rate'],settings['center']
                    if current!=cached:
                        rate,center=current; values=bytearray()
                        for i in range(rate//100):
                            voice=math.cos(2*math.pi*1000*i/rate)
                            phase=2*math.pi*(carrier-center)*i/rate-deviation/1000*voice
                            amp=75*(.7+.3*voice) if mode=='am' else 75
                            values.extend((round(127.5+amp*math.cos(phase)),round(127.5+amp*math.sin(phase))))
                        packet=bytes(values)*2;cached=current
                    start=time.monotonic();conn.sendall(packet);stop.wait(max(0,.02-(time.monotonic()-start)))
        except (ConnectionResetError,ConnectionAbortedError,BrokenPipeError):pass
        except Exception as e:
            if not stop.is_set():errors.append(str(e))
    thread=threading.Thread(target=transmit,daemon=True);thread.start()
    try:
        r=run('audio-'+mode,['--frontend','none',flag,'-i',f'rtltcp:127.0.0.1:{server.getsockname()[1]}:{carrier}:30:0:48:0:2','-o','pulse'],12,extra_env={'XERAX_SMOKE_GATE':'1'} if mode=='nfm' else None)
        r.update(commands=commands,serverErrors=errors)
        assert r['state']==2 and r['pcmFrames']>16000 and r['nonzeroFrames']>8000 and r['outputFrames']>8000 and not errors,r
        if mode=='nfm':assert r['details']['gateOutputDelta']<=2880 and r['details']['gatePcmDelta']>48000 and not r['suppressed'],r
    finally:stop.set();server.close();thread.join(timeout=2)

with socket.socket() as reserved:
    reserved.bind(('127.0.0.1',0))
    r=run('connection-refused',['--frontend','none','-fA','-i',f'rtltcp:127.0.0.1:{reserved.getsockname()[1]}:162400000:30:0:48:0:2','-o','pulse'],6)
    assert r['failure'] and r['pcmFrames']==0,r
r=run('unsupported-workers',['--xerax-site-capture'],3)
assert r['failure'] and r['pcmFrames']==0,r
for case in ['no-header','invalid-header']:
    done=threading.Event()
    server=socket.socket();server.bind(('127.0.0.1',0));server.listen(1);server.settimeout(12)
    def stalled():
        try:
            conn,_=server.accept()
            with conn:
                if case=='invalid-header':conn.sendall(b'NOTRTL______')
                done.wait(14)
        except OSError:pass
    thread=threading.Thread(target=stalled,daemon=True);thread.start()
    try:
        r=run(case,['--frontend','none','-fA','-i',f'rtltcp:127.0.0.1:{server.getsockname()[1]}:162400000:30:0:48:0:2','-o','pulse'],9)
        assert r['state']==4 and r['failure'] and r['pcmFrames']==0,r
    finally:done.set();server.close();thread.join(timeout=2)
(out/'summary.json').write_text(json.dumps({'passed':True,'tests':reports,'hardwareTest':False,'humanListeningTest':False},indent=2)+'\n')
print(f'{len(reports)} Windows application checks passed')
