"""Audit the experimental recovery release without converting software tests into RF claims."""
from pathlib import Path
import hashlib, json, os, re, struct, subprocess, zipfile
root=Path(__file__).resolve().parents[1]
src=root/'upstream/dsd-neo';dist=root/'dist'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def log(n):return (root/'build'/n).read_text(encoding='utf-8-sig')
def executable_segments(data):
    is64=data[4]==2
    # LLD can include the ELF header in an executable LOAD. llvm-strip changes
    # only section-table bookkeeping there, not runtime code/program headers.
    data=bytearray(data)
    for start,length in ([(40,8),(60,4)] if is64 else [(32,4),(48,4)]):
        data[start:start+length]=bytes(length)
    offset=struct.unpack_from('<Q' if is64 else '<I',data,32 if is64 else 28)[0]
    size,count=struct.unpack_from('<HH',data,54 if is64 else 42)
    result=[]
    for i in range(count):
        p=struct.unpack_from('<IIQQQQQQ' if is64 else '<IIIIIIII',data,offset+i*size)
        kind,flags,start,length=(p[0],p[1],p[2],p[5]) if is64 else (p[0],p[6],p[1],p[4])
        if kind==1 and flags&1:result.append(hashlib.sha256(data[start:start+length]).hexdigest())
    assert result
    return result
release=json.loads((root/'UPSTREAM.json').read_text())
assert release['version']=='4.1.5' and release['versionCode']==40105
assert '100% tests passed out of 31' in log('receiver-415-checks.log')
assert '70 passed, 0 failed, 0 skipped' in log('receiver-415-qml.txt')
assert '65536 complete seed/format cases; 500000 random frames; 13 context/quality boundaries' in log('receiver-415-search.log')
assert 'PASS: native NXDN FEC -> recovered seed -> exact AMBE payload -> nonzero finite PCM' in log('receiver-415-native.log')
assert re.findall(r'100% tests passed out of (\d+)',log('receiver-415-full-iq.log'))==['30','1']
lab=json.loads((root/'build/iq-lab-report/report.json').read_text())
assert all(t['exitCode']==0 for t in lab['tests'])
assert all(t['passed'] for t in lab['tests'] if not t.get('exploratory') and not t.get('equalizer'))
speech=json.loads((root/'build/nxdn-research/speech-replay-report.json').read_text())
assert speech['ciphertextSynthetic'] and len(speech['tests'])==2
assert [t['keysRecovered'] for t in speech['tests']]==[64,0]
assert all(t['wrongKeys']==0 for t in speech['tests'])
archive=dist/'XeraX-SDR-4.1.5-source.zip'
credential=(root/'.local/radioreference-app-key.txt').read_bytes().strip()
assert credential
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    prefix='XeraX-SDR/upstream/dsd-neo/'
    manifest=json.loads(z.read(prefix+'XERAX_SOURCE_MANIFEST.json'))
    for name,sha in manifest['files'].items():
        assert hashlib.sha256(z.read(prefix+name)).hexdigest()==sha
        assert digest(src/name)==sha,name
    for name in ['include/dsd-neo/platform/nxdn_search.h','src/platform/nxdn_search.cpp','tests/engine/nxdn_search_voice.c']:
        assert name in manifest['files'],name
    for name in z.namelist():
        assert '/.local/' not in name and not name.endswith(('.jks','.dpapi'))
        assert credential not in z.read(name),'Credential found in source archive'
certificate='43044bacd6d5ac2e407952e07a59e57dce06409f030408e84b79283dcfa765b5'
aapt=Path(os.environ['LOCALAPPDATA'])/'Android/Sdk/build-tools/36.0.0/aapt2.exe'
packages=[]
for suffix,abi,cache,logname in [('arm64','arm64-v8a','app','arm64'),('armeabi-v7a','armeabi-v7a','app-armeabi-v7a','armv7')]:
    stem='XeraX-SDR-4.1.5-'+suffix;apk=dist/(stem+'.apk')
    build=log(logname+'-415-final-build.log')
    assert 'BUILD SUCCESSFUL' in build and 'lintVitalRelease' in build
    sign=log(logname+'-415-signing.log')
    assert certificate in sign and 'Verified using v3 scheme (APK Signature Scheme v3): true' in sign
    package=json.loads((dist/(stem+'-package-verification.json')).read_text())
    assert package['sha256']==digest(apk) and package['abi']==abi
    metadata=subprocess.check_output([str(aapt),'dump','badging',str(apk)],text=True,encoding='utf-8')
    for expected in ["name='com.xerax.sdr'","versionCode='40105'","versionName='4.1.5'","minSdkVersion:'29'","targetSdkVersion:'36'",f"native-code: '{abi}'"]:
        assert expected in metadata,expected
    with zipfile.ZipFile(apk) as z:
        apps=[z.read(n) for n in z.namelist() if n.startswith('lib/') and 'dsd-neo-app' in n]
        assert apps and any(credential in data for data in apps)
        # APK packaging strips local symbol names. Verify the linked recovery
        # symbol in the unstripped binary and exact executable code identity.
        binary=Path(os.environ['LOCALAPPDATA'])/'XeraXSDR-build'/cache/'android'/f'libdsd-neo-app_{abi}.so'
        nm=Path(os.environ['LOCALAPPDATA'])/'Android/Sdk/ndk/28.2.13676358/toolchains/llvm/prebuilt/windows-x86_64/bin/llvm-nm.exe'
        symbols=subprocess.check_output([str(nm),str(binary)],text=True,encoding='utf-8')
        assert 'dsd_nxdn_search_step' in symbols
        assert len(apps)==1 and executable_segments(apps[0])==executable_segments(binary.read_bytes())
    stage=Path(os.environ['LOCALAPPDATA'])/'XeraXSDR-build'/cache/'android/android-build'
    for name in ['ReceiverWorkers.kt','SiteAudioSelector.kt','DsdNative.kt','DecoderService.kt','ReceiverSession.kt']:
        rel=Path('src/io/github/arancormonk/dsdneo')/name
        assert digest(stage/rel)==digest(src/'android/package'/rel),name
    package.update(signingCertificateSha256=certificate,signatureV3Verified=True,androidReleaseLint=True)
    packages.append(package)
previous=0
for path in dist.glob('XeraX-SDR-*-verification.json'):
    if path.name=='XeraX-SDR-4.1.5-verification.json' or '-package-' in path.name:continue
    data=json.loads(path.read_text())
    for p in data.get('packages',[]):
        assert digest(dist/p['apk'])==p['sha256'];previous+=1
    if data.get('sourceArchive') and data.get('sourceSha256'):
        assert digest(dist/data['sourceArchive'])==data['sourceSha256'];previous+=1
assert previous>=9
report=dict(version='4.1.5',versionCode=40105,experimentalNxdnRecovery=True,
    exhaustiveSeedLayoutCases=65536,randomRejectFrames=500000,contextAndQualityCases=13,
    nativeFecRecoveryPcmTest=True,speechParameterReplay=speech,hostTestGroups=31,qmlCases=70,fullIqCases=30,
    atomicVoiceTuneCases=1,spanishTranslations=len(json.loads((src/'src/ui/qt/i18n/es.json').read_text(encoding='utf-8'))),
    packages=packages,sourceArchive=archive.name,sourceSha256=digest(archive),
    sourceManifestVerified=True,sourceLocalCredentialsExcluded=True,previousArtifactsVerified=previous,
    hardwareAcceptance=False,unknownScramblerRadioRecordingVerified=False,
    limitations=['Inference is statistical and may produce a wrong candidate or no result.',
                 'Requires two separate stable-pitch windows and confirmed NXDN cipher-1 superframe signaling.',
                 'Main receiver only; DES/AES recovery and non-superframe/DCR-specific search are excluded.',
                 'The short real-speech NXDN96 parameter extract did not provide enough evidence to accept any of 64 synthetic test keys.',
                 'No phone timing or scrambled-radio speech acceptance has been performed.'])
(dist/'XeraX-SDR-4.1.5-verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
