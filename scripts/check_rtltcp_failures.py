"""Production decoder must exit stalled/invalid TCP sessions instead of silent live state."""
import argparse,concurrent.futures,json,socket,struct,subprocess,threading,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('decoder',type=Path)
p.add_argument('--output',type=Path,default=Path('build/tcp-413-failures'))
a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
def check(case):
    server=socket.socket();server.bind(('127.0.0.1',0));server.listen(8);server.settimeout(.2)
    port=server.getsockname()[1];done=threading.Event();clients=[]
    def accept():
        while not done.is_set():
            try:
                client,_=server.accept();clients.append(client)
                if case=='invalid-header':client.sendall(b'NOTRTL______')
                elif case=='header-without-iq':client.sendall(b'RTL0'+struct.pack('!II',5,29))
                elif case=='early-close':client.close()
            except socket.timeout:continue
            except OSError:break
    thread=threading.Thread(target=accept,daemon=True);thread.start()
    start=time.monotonic();timeout=False
    try:
        r=subprocess.run([str(a.decoder.resolve()),'--frontend','none','-fA','-i',f'rtltcp:127.0.0.1:{port}:162400000:30:0:48:0:2','-o','null'],capture_output=True,timeout=40)
        text=(r.stdout+r.stderr).decode('utf-8',errors='replace');exit_code=r.returncode
    except subprocess.TimeoutExpired as error:
        timeout=True;exit_code=None;text=((error.stdout or b'')+(error.stderr or b'')).decode('utf-8',errors='replace')
    finally:
        done.set();server.close()
        for client in clients:client.close()
        thread.join(timeout=1)
    (a.output/(case+'.log')).write_text(text,encoding='utf-8')
    result=dict(case=case,seconds=round(time.monotonic()-start,2),forcedTimeout=timeout,exitCode=exit_code,
                acceptedConnections=len(clients),reportedFailure='no usable radio stream' in text or (case=='early-close' and exit_code==1 and 'Failed to open radio stream' in text))
    result['passed']=not timeout and result['reportedFailure'] and exit_code is not None and exit_code>=0
    return result
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
    results=list(executor.map(check,['no-header','invalid-header','early-close','header-without-iq']))
(a.output/'report.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8')
print(json.dumps(results,indent=2));assert all(r['passed'] for r in results)
