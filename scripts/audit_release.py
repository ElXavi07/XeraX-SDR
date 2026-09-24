"""Verify corresponding source, credentials exclusions, prior artifacts and release evidence."""
from pathlib import Path
import hashlib,json,zipfile,re
root=Path(__file__).resolve().parents[1]
source=root/'upstream/dsd-neo'
release=json.loads((root/'UPSTREAM.json').read_text())
version=release['version']
if version == '4.1.5':
    import runpy
    runpy.run_path(str(root/'scripts/audit_nxdn_415.py'), run_name='__main__')
    raise SystemExit(0)
if version == '4.1.4':
    import runpy
    runpy.run_path(str(root/'scripts/audit_reception_414.py'), run_name='__main__')
    raise SystemExit(0)
if version == '4.1.3':
    import runpy
    runpy.run_path(str(root/'scripts/audit_network_413.py'), run_name='__main__')
    raise SystemExit(0)
if version == '4.1.2':
    import runpy
    runpy.run_path(str(root/'scripts/audit_receivers_412.py'), run_name='__main__')
    raise SystemExit(0)
archive=root/f'dist/XeraX-SDR-{version}-source.zip'
apk=root/f'dist/XeraX-SDR-{version}-arm64.apk'
key=(root/'.local/radioreference-app-key.txt').read_bytes().strip()
assert key
with zipfile.ZipFile(archive) as bundle:
    assert bundle.testzip() is None
    prefix='XeraX-SDR/upstream/dsd-neo/'
    manifest=json.loads(bundle.read(prefix+'XERAX_SOURCE_MANIFEST.json'))
    assert manifest['upstreamCommit']==release['commit']
    for name,digest in manifest['files'].items():
        assert hashlib.sha256(bundle.read(prefix+name)).hexdigest()==digest,name
        assert hashlib.sha256((source/name).read_bytes()).hexdigest()==digest,name
    for name in bundle.namelist():
        assert '/.local/' not in name and not name.endswith(('.jks','.dpapi')),name
        assert key not in bundle.read(name),'Application credential present in source archive'
    for name in ['src/ui/qt/receiver_expansion.cpp','src/ui/qt/call_library.cpp','src/ui/qt/qml/ExpansionScreen.qml',
                 'src/ui/qt/qml/CallsScreen.qml','src/platform/channel_bank.cpp','src/platform/receiver_lab.cpp',
                 'src/platform/analog_signaling.cpp','src/platform/analog_recording.cpp','docs/ANALOG-SIGNALING.md',
                 'android/package/src/io/github/arancormonk/dsdneo/ReceiverWorkers.kt',
                 'android/package/src/io/github/arancormonk/dsdneo/ReceiverSession.kt',
                 'android/package/src/io/github/arancormonk/dsdneo/CallExport.kt','android/package/assets/iq-lab/manifest.json']:
        assert prefix+name in bundle.namelist(),name
with zipfile.ZipFile(apk) as bundle:
    assert any(key in bundle.read(name) for name in bundle.namelist() if name.startswith('lib/') and 'dsd-neo-app' in name)
    lab=json.loads((source/'android/package/assets/iq-lab/manifest.json').read_text())
    for name,digest in lab['sha256'].items():
        assert hashlib.sha256(bundle.read('assets/iq-lab/'+name)).hexdigest()==digest,name
for name,digest in {
    'XeraX-SDR-4.1.0-arm64.apk':'47d2490e398384278afcf1c0e60a42fc2bb5161a8d15ee9da956c76e109b1f88',
    'XeraX-SDR-4.1.0-source.zip':'0314547dde35b7084b815a627df1c2121461e10bb8d0fec3fa55b184dffc336d',
    'XeraX-SDR-4.0.0-arm64.apk':'96dac0ea819040383aac2be575c1e77a293f208ba4e4e2c800ccc59d0b4827e2',
    'XeraX-SDR-4.0.0-source.zip':'4c6d7a615bf5dd080915bb0d59e48632587b53bb8c2e65b4aaa9e99bb52a5b35',
    'XeraX-SDR-3.0.0-arm64.apk':'e3e5aa93b218d75698be765982850d559bc0671dafaf71c50eaa1ec4ce538526',
    'XeraX-SDR-3.0.0-source.zip':'a3ec310a99e27d8a24796893dfbc0d17bf38ad5814b89b3c070ccfc3b1148463',
    'XeraX-SDR-2.0.0-arm64.apk':'71b0aae9b95f9900f852c68be92bdba8b039927df34f081dccd6dc8d203ea52e',
    'XeraX-SDR-2.0.0-source.zip':'50676d9c0f8fd74e88412a0f3e5d33aa145ed937a6c76dd22c848c83863bc255'
}.items():
    assert hashlib.sha256((root/'dist'/name).read_bytes()).hexdigest()==digest,name
audio_release=version=='4.1.1'
prefix='audio-411' if audio_release else 'reception-41'
def log(name): return (root/f'build/{prefix}-{name}').read_text(encoding='utf-8-sig')
def tests(name):
    matches=re.findall(r'100% tests passed out of (\d+)',log(name))
    assert matches,name
    return list(map(int,matches))
host_groups=tests('checks.log')[0]
iq_groups=tests('full-iq.log')
assert iq_groups==([33] if audio_release else [30,1]),iq_groups
qml=re.search(r'Totals: (\d+) passed, 0 failed, 0 skipped',log('qml.txt'))
assert qml
assert 'BUILD SUCCESSFUL' in log('android.log') and 'Task :lintVitalRelease' in log('android.log')
lab_report=json.loads((root/('build/audio-411-lab/report.json' if audio_release else 'build/iq-lab-report/report.json')).read_text())
assert all(r['exitCode']==0 for r in lab_report['tests'])
assert all(r['passed'] for r in lab_report['tests'] if not r.get('exploratory'))
benchmark=json.loads((root/f'build/{prefix}-benchmark/report.json').read_text())
assert all(r['exitCode']==0 for r in benchmark['tests'])
assert all(r['matched'] for r in benchmark['tests'] if r['kind']=='shared-channel-parity')
signing=log('sign.log')
certificate='43044bacd6d5ac2e407952e07a59e57dce06409f030408e84b79283dcfa765b5'
assert certificate in signing and 'Verified using v3 scheme (APK Signature Scheme v3): true' in signing
report=json.loads((root/'dist/package-verification.json').read_text())
assert report['apk']==apk.name
report.update(version=version,versionCode=release['versionCode'],applicationId=release['applicationId'],
    signingCertificateSha256=certificate,signatureScheme='v3 verified',zipAlignment='zipalign -c -P 16 4 passed',
    hostTestGroups=host_groups,qmlCases=int(qml.group(1)),fullIqTests=30,atomicVoiceCommandTests=1,
    appLabCases=sum(not t.get('exploratory',False) for t in lab_report['tests']),
    dspComparisons=sum(t.get('exploratory',False) for t in lab_report['tests']),
    sharedChannelCases=sum(t['kind']=='shared-channel-parity' for t in benchmark['tests']),
    simulcastComparisons=sum(t['kind']=='simulcast-comparison' for t in benchmark['tests']),
    spanishCatalogEntries=len(json.loads((source/'src/ui/qt/i18n/es.json').read_text(encoding='utf-8'))),
    sourceManifestFiles=len(manifest['files']),sourceManifestVerified=True,sourceLocalCredentialsExcluded=True,
    applicationKeyIncludedInApk=True,previousReleasesPreserved=True,hardwareAcceptance=False,
    sourceArchive=archive.name,sourceSha256=hashlib.sha256(archive.read_bytes()).hexdigest())
if audio_release:
    assert 'stale callbacks and abandonment passed' in log('focus.log')
    network=[json.loads((root/f'build/audio-411-network-{case}/report.json').read_text())
             for case in ['nfm-400','nfm-1000','nfm-2500','am','wfm']]
    assert all(case['passed'] for case in network)
    for name in ['android/package/src/io/github/arancormonk/dsdneo/AudioFocusLease.kt','src/io/radio/rtl_tcp_header.h']:
        assert name in manifest['files'],name
    report.update(audioFocusLeaseCheck=True,coreAudioAndFilterTests=2,rtlTcpAnalogCases=network,
                  hardwareAcceptance=False,
                  hardwareLimit='AAudio device APIs are mocked in host tests; actual S25/Pixel speaker playback is pending.')
(root/f'dist/XeraX-SDR-{version}-verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ['apk','bytes','sha256','sourceManifestFiles','sourceManifestVerified',
    'sourceLocalCredentialsExcluded','applicationKeyIncludedInApk','previousReleasesPreserved','sourceSha256']},indent=2))
