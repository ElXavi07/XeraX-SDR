"""Verify the two 4.1.2 packages against corresponding source and fresh evidence."""
from pathlib import Path
import hashlib, json, os, re, subprocess, xml.etree.ElementTree as ET, zipfile
root=Path(__file__).resolve().parents[1]
src=root/'upstream/dsd-neo'
dist=root/'dist'
release=json.loads((root/'UPSTREAM.json').read_text())
assert release['version']=='4.1.2' and release['versionCode']==40102
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def log(name): return (root/'build'/name).read_text(encoding='utf-8-sig')
assert '100% tests passed out of 30' in log('receiver-412-checks.log')
assert '69 passed, 0 failed, 0 skipped' in log('receiver-412-qml.txt')
assert re.findall(r'100% tests passed out of (\d+)',log('receiver-412-full-iq.log'))==['30','1']
assert '100% tests passed out of 3' in log('receiver-412-ppm.log')
assert '100% tests passed out of 2' in log('receiver-412-core.log')
lab=json.loads((root/'build/iq-lab-report/report.json').read_text())
assert all(t['exitCode']==0 for t in lab['tests'])
assert all(t['passed'] for t in lab['tests'] if not t.get('exploratory') and not t.get('equalizer'))
archive=dist/'XeraX-SDR-4.1.2-source.zip'
key=(root/'.local/radioreference-app-key.txt').read_bytes().strip()
assert key
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    prefix='XeraX-SDR/upstream/dsd-neo/'
    manifest=json.loads(z.read(prefix+'XERAX_SOURCE_MANIFEST.json'))
    for name,sha in manifest['files'].items():
        assert hashlib.sha256(z.read(prefix+name)).hexdigest()==sha
        assert digest(src/name)==sha,name
    for name in z.namelist():
        assert '/.local/' not in name and not name.endswith(('.jks','.dpapi'))
        assert key not in z.read(name),'Credential found in source archive'
    for name in ['src/io/radio/hackrf_source.cpp','src/io/radio/hackrf_source.h',
                 'android/third_party/libhackrf/hackrf.c','android/third_party/libhackrf/LICENSE',
                 'android/third_party/libhackrf/README.dsd-neo','vcpkg-triplets/arm-android-static.cmake']:
        assert name in manifest['files'],name
certificate='43044bacd6d5ac2e407952e07a59e57dce06409f030408e84b79283dcfa765b5'
packages=[]
for suffix,abi in [('arm64','arm64-v8a'),('armeabi-v7a','armeabi-v7a')]:
    stem=f'XeraX-SDR-4.1.2-{suffix}'
    log_prefix='arm64' if suffix=='arm64' else 'armv7'
    build=log(f'{log_prefix}-412-android.log')
    assert 'BUILD SUCCESSFUL' in build and 'Task :lintVitalRelease' in build
    signing=log(f'{log_prefix}-412-signing.log')
    assert certificate in signing
    assert 'Verified using v3 scheme (APK Signature Scheme v3): true' in signing
    p=json.loads((dist/(stem+'-package-verification.json')).read_text())
    apk=dist/(stem+'.apk')
    assert p['sha256']==digest(apk) and p['abi']==abi
    with zipfile.ZipFile(apk) as z:
        assert any(key in z.read(n) for n in z.namelist() if n.startswith('lib/') and 'dsd-neo-app' in n)
        assert any(n.endswith('third-party/libhackrf/LICENSE.txt') for n in z.namelist())
        fixtures=json.loads((src/'android/package/assets/iq-lab/manifest.json').read_text())
        for name,sha in fixtures['sha256'].items():
            assert hashlib.sha256(z.read('assets/iq-lab/'+name)).hexdigest()==sha
    aapt=Path(os.environ['LOCALAPPDATA'])/'Android/Sdk/build-tools/36.0.0/aapt2.exe'
    metadata=subprocess.check_output([str(aapt),'dump','badging',str(apk)],text=True,encoding='utf-8')
    assert "name='com.xerax.sdr'" in metadata and "versionCode='40102'" in metadata
    assert "versionName='4.1.2'" in metadata and "minSdkVersion:'29'" in metadata
    assert f"native-code: '{abi}'" in metadata
    p.update(minimumAndroidApi=29,signingCertificateSha256=certificate,signatureV3Verified=True,androidReleaseLint=True)
    packages.append(p)
ids_source=(src/'android/package/src/io/github/arancormonk/dsdneo/UsbSourceManager.kt').read_text(encoding='utf-8').split('private val KNOWN_IDS')[1].split(').toHashSet()')[0]
ids={int(x,16) for x in re.findall(r'0x([0-9a-f]{8})',ids_source)}
xmlids={(int(d.attrib['vendor-id'])<<16)|int(d.attrib['product-id']) for d in ET.parse(src/'android/package/res/xml/device_filter.xml').getroot()}
assert ids==xmlids and {0x0bda2838,0x1d506089,0x1d5060a1}<=ids
for name,sha in {
    'XeraX-SDR-4.1.1-arm64.apk':'1760472840007316c4a1b4d9866d8304051f04c0b7a93d4b985113563aa4c1b1',
    'XeraX-SDR-4.1.1-source.zip':'5259e6c00f45bfafcc33f93d4dd6d361dc40f7b0793d4feb248339478e9b9590',
    'XeraX-SDR-4.1.0-arm64.apk':'47d2490e398384278afcf1c0e60a42fc2bb5161a8d15ee9da956c76e109b1f88',
    'XeraX-SDR-4.1.0-source.zip':'0314547dde35b7084b815a627df1c2121461e10bb8d0fec3fa55b184dffc336d'
}.items(): assert digest(dist/name)==sha,name
report=dict(version='4.1.2',versionCode=40102,packages=packages,hostTestGroups=30,qmlCases=69,
    fullIqCases=30,atomicVoiceTuneCases=1,ppmEngineCases=3,coreInputAndAudioCases=2,
    labCases=sum(not t.get('exploratory',False) for t in lab['tests']),hackrfUsbMocked=True,
    sourceArchive=archive.name,sourceSha256=digest(archive),sourceManifestFiles=len(manifest['files']),
    sourceManifestVerified=True,sourceLocalCredentialsExcluded=True,previousReleasesPreserved=True,
    usbIdParity=True,usbIds=len(ids),hardwareAcceptance=False,
    limitations=['Physical V4/HackRF/ARMv7 and phone audio tests pending.',
                 'HackRF One reception is experimental and limited to approximately 1 MHz–2 GHz.',
                 'Direct drivers for SDRplay, LimeSDR, Airspy HF+ and arbitrary Soapy devices are not included.'])
(dist/'XeraX-SDR-4.1.2-verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,indent=2))
