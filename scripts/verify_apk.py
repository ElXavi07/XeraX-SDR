"""Inspect the packaged native payload, including Android 16 KB support."""
from pathlib import Path
import argparse
import hashlib
import json
import struct
import sys
import zipfile

parser = argparse.ArgumentParser()
parser.add_argument('apk', type=Path)
parser.add_argument('--abi', choices=['arm64-v8a', 'armeabi-v7a'], default='arm64-v8a')
args = parser.parse_args()
apk = args.apk.resolve()
is64 = args.abi == 'arm64-v8a'
required_alignment = 16384 if is64 else 4096
all_aligned_16k = True
with zipfile.ZipFile(apk) as bundle:
    assert bundle.testzip() is None, 'APK ZIP corruption'
    libs = [name for name in bundle.namelist() if name.startswith('lib/') and name.endswith('.so')]
    assert libs and all(name.startswith(f'lib/{args.abi}/') for name in libs), 'Unexpected ABI'
    assert any('dsd-neo-app' in name for name in libs), 'Missing decoder engine'
    provided = {name.rsplit('/', 1)[1] for name in libs}
    external = set()
    for name in libs:
        data = bundle.read(name)
        assert data[:6] == b'\x7fELF' + bytes([2 if is64 else 1, 1]), f'Wrong ELF class/endian: {name}'
        assert struct.unpack_from('<H', data, 18)[0] == (183 if is64 else 40), f'Wrong machine: {name}'
        phoff = struct.unpack_from('<Q' if is64 else '<I', data, 32 if is64 else 28)[0]
        phsize, phnum = struct.unpack_from('<HH', data, 54 if is64 else 42)
        headers = []
        for i in range(phnum):
            fields = struct.unpack_from('<IIQQQQQQ' if is64 else '<IIIIIIII', data, phoff + i * phsize)
            if not is64:
                # Normalize ELF32's p_flags location to the ELF64 tuple layout.
                fields = (fields[0], fields[6], fields[1], fields[2], fields[3], fields[4], fields[5], fields[7])
            headers.append(fields)
            if fields[0] == 1:
                assert fields[7] >= required_alignment, f'Insufficient ELF LOAD alignment: {name}'
                assert (fields[2] - fields[3]) % required_alignment == 0, f'Incongruent LOAD segment: {name}'
                all_aligned_16k &= fields[7] >= 16384 and (fields[2] - fields[3]) % 16384 == 0
        dynamic = next((p for p in headers if p[0] == 2), None)
        if dynamic:
            tags = [struct.unpack_from('<qQ' if is64 else '<iI', data, i)
                    for i in range(dynamic[2], dynamic[2] + dynamic[5], 16 if is64 else 8)]
            strings = next((value for tag, value in tags if tag == 5), None)
            if strings is not None:
                segment = next(p for p in headers if p[0] == 1 and p[3] <= strings < p[3] + p[5])
                offset = segment[2] + strings - segment[3]
                needed = {data[offset + value:data.index(b'\0', offset + value)].decode()
                          for tag, value in tags if tag == 1}
                external.update(needed - provided)
    system_libraries = {'libEGL.so', 'libGLESv2.so', 'libaaudio.so', 'libandroid.so',
                        'libc.so', 'libdl.so', 'libjnigraphics.so', 'liblog.so', 'libm.so', 'libz.so'}
    assert external <= system_libraries, f'Unpackaged native dependencies: {external - system_libraries}'
    names = bundle.namelist()
    assert any(name.endswith('doc/dsd-neo/LICENSE') for name in names), 'Missing GPL license'
    assert any(name.endswith('THIRD_PARTY.md') for name in names), 'Missing third-party notices'
    assert sum('/doc/xerax/' in name for name in names) >= 30, 'Missing dependency notices'
    assert 'classes.dex' in names, 'Missing Android bytecode'
    assert 'AndroidManifest.xml' in names, 'Missing manifest'
result = {
    'apk': apk.name,
    'bytes': apk.stat().st_size,
    'sha256': hashlib.sha256(apk.read_bytes()).hexdigest(),
    'abi': args.abi,
    'elfClass': 'ELF64' if is64 else 'ELF32',
    'nativeLibraries': len(libs),
    'nativeDependencyClosure': 'pass; remaining dependencies are Android system libraries',
    'androidSystemLibraries': sorted(external),
    'requiredNativeLoadAlignment': required_alignment,
    'allNativeLoadSegments16KiBAligned': bool(all_aligned_16k),
    'zipIntegrity': 'pass',
    'licenseAndNoticesPresent': True,
    'scope': 'Static package verification; no physical-device or over-the-air test.'
}
print(json.dumps(result, indent=2))
(apk.parent / 'package-verification.json').write_text(json.dumps(result, indent=2) + '\n')
(apk.parent / (apk.stem + '-package-verification.json')).write_text(json.dumps(result, indent=2) + '\n')
