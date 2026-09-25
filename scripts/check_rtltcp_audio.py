"""Loopback RTL-TCP -> production FM demodulator -> UDP PCM regression.

No dongle, phone, account or external network is used. The synthetic transmitter
honors the client's real tuning/sample-rate commands and fragments its header.
"""
import argparse, array, json, math, socket, struct, subprocess, threading, time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('decoder', type=Path)
parser.add_argument('--output', type=Path, default=Path('build/network-audio-check'))
parser.add_argument('--header-delay', type=float, default=0)
parser.add_argument('--tone', type=int, choices=[400, 1000, 2500, 8000], default=1000)
parser.add_argument('--mode', choices=['nfm', 'am', 'wfm'], default='nfm')
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
stop = threading.Event()
commands = []
carrier = 100000000 if args.mode == 'wfm' else 162400000
settings = {'rate': 1536000, 'center': carrier}
errors = []
server = socket.socket()
server.bind(('127.0.0.1', 0))
server.listen(1)
server.settimeout(10)
audio = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
audio.bind(('127.0.0.1', 0))
audio.settimeout(.2)
audio_port = audio.getsockname()[1]

def read_commands(conn):
    pending = b''
    while not stop.is_set():
        try:
            data = conn.recv(4096)
            if not data: return
            pending += data
            while len(pending) >= 5:
                cmd, value = struct.unpack('!BI', pending[:5]); pending = pending[5:]
                commands.append([cmd, value])
                if cmd == 1: settings['center'] = value
                if cmd == 2: settings['rate'] = value
        except socket.timeout: pass
        except OSError: return

def transmit():
    try:
        conn, _ = server.accept()
        with conn:
            conn.settimeout(.5)
            if args.header_delay: time.sleep(args.header_delay)
            header = b'RTL0' + struct.pack('!II', 5, 29)
            for chunk in (header[:1], header[1:5], header[5:]):
                conn.sendall(chunk); time.sleep(.01)
            threading.Thread(target=read_commands, args=(conn,), daemon=True).start()
            cached = None
            while not stop.is_set():
                current = settings['rate'], settings['center']
                if current != cached:
                    rate, center = current
                    assert 100000 <= rate <= 4000000 and rate % 100 == 0, current
                    period = rate // 100
                    deviation = 25000 if args.mode == 'wfm' else 2500
                    # Ten milliseconds repeat continuously at these tone and center frequencies.
                    values = bytearray()
                    for i in range(period):
                        voice = math.cos(2*math.pi*args.tone*i/rate)
                        phase = 2*math.pi*(carrier-center)*i/rate
                        amplitude = 75
                        if args.mode == 'am':
                            amplitude *= .7 + .3*voice
                        else:
                            phase -= deviation/args.tone*voice
                        values.extend((round(127.5+amplitude*math.cos(phase)), round(127.5+amplitude*math.sin(phase))))
                    packet = bytes(values)*2
                    cached = current
                start = time.monotonic()
                conn.sendall(packet)
                stop.wait(max(0, .020-(time.monotonic()-start)))
    except Exception as error:
        if not stop.is_set(): errors.append(str(error))

thread = threading.Thread(target=transmit, daemon=True)
thread.start()
port = server.getsockname()[1]
flag = dict(nfm='-fA', am='-fU', wfm='-fW')[args.mode]
command = [str(args.decoder.resolve()), '--frontend', 'none', flag, '-i',
           f'rtltcp:127.0.0.1:{port}:{carrier}:30:0:48:0:2',
           '-o', f'udp:127.0.0.1:{audio_port-2}']
pcm = bytearray()
with (args.output/'decoder.log').open('wb') as log:
    process = subprocess.Popen(command, stdout=log, stderr=log)
    try:
        deadline = time.monotonic()+10
        while time.monotonic() < deadline:
            try: pcm.extend(audio.recv(65536))
            except socket.timeout: pass
            if process.poll() is not None: break
    finally:
        stop.set()
        if process.poll() is None: process.terminate()
        process.wait(timeout=10)
        thread.join(timeout=2)
        server.close(); audio.close()
values = array.array('h', pcm)
samples = list(values[-48000:])
peak = max(map(abs, samples), default=0)
rms = math.sqrt(sum(x*x for x in samples)/len(samples)) if samples else 0
# Quadrature correlation measures tone energy without assuming phase alignment.
def energy(f):
    return sum(x*math.cos(2*math.pi*f*i/48000) for i,x in enumerate(samples))**2 + sum(x*math.sin(2*math.pi*f*i/48000) for i,x in enumerate(samples))**2
tone = energy(args.tone)
neighbors = max(energy(args.tone-100), energy(args.tone+100), 1)
report = dict(pcmBytes=len(pcm), peak=peak, rms=rms, toneToNeighborDb=10*math.log10(max(tone,1)/neighbors),
              mode=args.mode, toneHz=args.tone, headerDelaySeconds=args.header_delay,
              commands=commands, serverErrors=errors, hardwareTest=False,
              termination='Harness stops the live receiver after the bounded sample window')
# WFM's existing output AGC targets a louder sine than NFM/AM. Keep the
# independent peak/headroom and spectral checks, with a mode-appropriate RMS bound.
max_rms = 23000 if args.mode == 'wfm' else 16000
report['passed'] = len(pcm)>48000 and 200<rms<max_rms and peak<32000 and report['toneToNeighborDb']>20 and not errors
(args.output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
assert report['passed'], 'RTL-TCP analog PCM regression failed'
