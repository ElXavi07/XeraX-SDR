"""Verify range scanner packages and corresponding source; software evidence is not RF acceptance."""
from pathlib import Path
import hashlib, json, os, struct, subprocess, zipfile
root=Path(__file__).resolve().parents[1]
src=root/'upstream/dsd-neo'; dist=root/'dist'
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def log(name): return (root/'build'/name).read_text(encoding='utf-8-sig')
def executable_segments(data):
    is64=data[4]==2; data=bytearray(data)
    for start,length in ([(40,8),(60,4)] if is64 else [(32,4),(48,4)]): data[start:start+length]=bytes(length)
    offset=struct.unpack_from('<Q' if is64 else '<I',data,32 if is64 else 28)[0]
    size,count=struct.unpack_from('<HH',data,54 if is64 else 42)
    result=[]
    for i in range(count):
        p=struct.unpack_from('<IIQQQQQQ' if is64 else '<IIIIIIII',data,offset+i*size)
        kind,flags,start,length=(p[0],p[1],p[2],p[5]) if is64 else (p[0],p[6],p[1],p[4])
        if kind==1 and flags&1: result.append(hashlib.sha256(data[start:start+length]).hexdigest())
    assert result; return result
release=json.loads((root/'UPSTREAM.json').read_text())
assert release['version']=='4.3.0' and release['versionCode']==40300
assert '100% tests passed out of 33' in log('range-430-full-checks.log')
assert '80 passed, 0 failed, 0 skipped' in log('range-430-qml.txt')
assert '0 range scan failures.' in log('range-430-controller-tests.log')
assert 'No live API requests.' in log('range-430-ai-regression.log')
credential=(root/'.local/radioreference-app-key.txt').read_bytes().strip()
archive=dist/'XeraX-SDR-4.3.0-source.zip'
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    prefix='XeraX-SDR/upstream/dsd-neo/'
    manifest=json.loads(z.read(prefix+'XERAX_SOURCE_MANIFEST.json'))
    for name,sha in manifest['files'].items():
        assert hashlib.sha256(z.read(prefix+name)).hexdigest()==sha
        assert digest(src/name)==sha,name
    for name in ['src/ui/qt/range_scanner.cpp','src/ui/qt/range_scanner.h','src/ui/qt/range_scan_math.h',
                 'src/ui/qt/qml/RangeScannerScreen.qml','src/ui/qt/qml/RangeScanSettings.qml']:
        assert name in manifest['files'],name
    for name in z.namelist():
        assert '/.local/' not in name and not name.endswith(('.jks','.dpapi'))
        assert not credential or credential not in z.read(name),'Credential found in source archive'
local=Path(os.environ['LOCALAPPDATA']); aapt=local/'Android/Sdk/build-tools/36.0.0/aapt2.exe'
certificate='43044bacd6d5ac2e407952e07a59e57dce06409f030408e84b79283dcfa765b5'
packages=[]
for suffix,abi,cache,label in [('arm64','arm64-v8a','app','arm64'),('armeabi-v7a','armeabi-v7a','app-armeabi-v7a','armv7')]:
    stem='XeraX-SDR-4.3.0-'+suffix; apk=dist/(stem+'.apk')
    build=log('range-430-'+label+'-release-build.log')
    assert 'BUILD SUCCESSFUL' in build and 'lintVitalRelease' in build
    sign=log('range-430-'+label+'-signing.log')
    assert certificate in sign and 'Verified using v3 scheme (APK Signature Scheme v3): true' in sign
    package=json.loads((dist/(stem+'-package-verification.json')).read_text())
    assert package['sha256']==digest(apk) and package['abi']==abi
    meta=subprocess.check_output([str(aapt),'dump','badging',str(apk)],text=True,encoding='utf-8')
    for expected in ["name='com.xerax.sdr'","versionCode='40300'","versionName='4.3.0'","minSdkVersion:'29'","targetSdkVersion:'36'",f"native-code: '{abi}'"]:
        assert expected in meta,expected
    with zipfile.ZipFile(apk) as z:
        apps=[z.read(n) for n in z.namelist() if n.startswith('lib/') and 'dsd-neo-app' in n]
        binary=local/'XeraXSDR-build'/cache/'android'/f'libdsd-neo-app_{abi}.so'
        assert len(apps)==1 and executable_segments(apps[0])==executable_segments(binary.read_bytes())
        dex=b''.join(z.read(n) for n in z.namelist() if n.endswith('.dex'))
        for value in [b'AiProviderBridge',b'AndroidKeyStore',b'api.openai.com',b'api.deepseek.com']:
            assert value in dex,value
        assert b'RangeScanner' in apps[0] and b'rangeTuneHz' in apps[0]
        assert b'fixture-openai-0123456789' not in dex and b'fixture-openai-0123456789' not in apps[0]
        for name in ['RANGE-SCANNER-4.3.0.md','AI-4.2.0.md','PRIVACY_POLICY.md']:
            assert z.read('assets/doc/xerax/'+name)==(src/'android/package/assets/doc/xerax'/name).read_bytes()
    stage=local/'XeraXSDR-build'/cache/'android/android-build'
    rel=Path('src/io/github/arancormonk/dsdneo/AiProviderBridge.kt')
    assert digest(stage/rel)==digest(src/'android/package'/rel)
    package.update(signingCertificateSha256=certificate,signatureV3Verified=True,androidReleaseLint=True,
                   nativeCodeMatchesBuild=True,aiBridgePackaged=True)
    packages.append(package)
previous=0
for path in dist.glob('XeraX-SDR-*-verification.json'):
    if path.name=='XeraX-SDR-4.3.0-verification.json' or '-package-' in path.name: continue
    data=json.loads(path.read_text())
    for p in data.get('packages',[]): assert digest(dist/p['apk'])==p['sha256']; previous+=1
    if data.get('sourceArchive') and data.get('sourceSha256'):
        assert digest(dist/data['sourceArchive'])==data['sourceSha256']; previous+=1
assert previous>=19
report=dict(version='4.3.0',versionCode=40300,rangeScanner=True,scannerRequiresAI=False,
    widebandGridDetection=True,holdSkipAvoid=True,analogAndDigitalAcquisition=True,
    scanBoundsMHz=[24,1766],maxSpanMHz=50,maxChannelPositions=10001,
    defaultStepKhz=12.5,hostTestGroups=33,qmlCases=80,
    spanishTranslations=len(json.loads((src/'src/ui/qt/i18n/es.json').read_text(encoding='utf-8'))),
    packages=packages,sourceArchive=archive.name,sourceSha256=digest(archive),sourceManifestVerified=True,
    sourceLocalCredentialsExcluded=True,previousArtifactsVerified=previous,hardwareAcceptance=False,
    limitations=['Synthetic FFT/clock tests establish scanner policy, not measured hardware sweep speed.',
        'Physical S25/Pixel USB, RTL-TCP, audio, thermal and screen-off tests remain pending.',
        'A single receiver cannot continuously monitor the whole range; brief or weak signals may be missed.',
        'Auto digital uses existing protocol decoders; analog NFM/AM are selected explicitly.',
        'Trunk following and P25 Phase 2 system parameters still require configured systems.',
        'No new encryption key recovery is part of this scanner release.'])
(dist/'XeraX-SDR-4.3.0-verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
