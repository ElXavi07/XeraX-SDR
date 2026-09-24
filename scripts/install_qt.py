"""Install the pinned Qt kits, verifying the publisher's checksums.

Qt 6.11's per-toolchain repository layout is not understood by aqt 3.3.
Downloads only the modules needed for XeraX SDR. Run with the build cache path.
"""
import concurrent.futures
import argparse
import hashlib
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
import requests

parser = argparse.ArgumentParser()
parser.add_argument('cache', type=Path)
parser.add_argument('--abi', choices=['arm64-v8a', 'armeabi-v7a'], default='arm64-v8a')
parser.add_argument('--skip-host', action='store_true', help='Keep an already installed Windows host kit.')
args = parser.parse_args()
cache = args.cache.resolve()
out = cache / 'QtKits'
archives = cache / 'qt-archives'
archives.mkdir(parents=True, exist_ok=True)
seven = next((cache / 'vcpkg/downloads/tools').glob('7zip*/7z.exe'))
android_kit = 'armv7' if args.abi == 'armeabi-v7a' else 'arm64_v8a'
roots = [] if args.skip_host else [
    'https://download.qt.io/online/qtsdkrepository/windows_x86/desktop/qt6_6112/qt6_6112_mingw/']
roots.append(f'https://download.qt.io/online/qtsdkrepository/all_os/android/qt6_6112/qt6_6112_{android_kit}/')

def get(url):
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    return response.content

jobs = []
for base in roots:
    metadata = get(base + 'Updates.xml')
    expected = get(base + 'Updates.xml.sha256').decode().split()[0]
    assert hashlib.sha256(metadata).hexdigest() == expected, 'Qt metadata checksum mismatch'
    for package in ET.fromstring(metadata).findall('PackageUpdate'):
        name = package.findtext('Name', '')
        if 'debug' in name:
            continue
        for archive in package.findtext('DownloadableArchives', '').split(','):
            archive = archive.strip()
            if not archive.startswith(('qtbase-', 'qtdeclarative-', 'qtshadertools-', 'qtsvg-', 'qttools-', 'MinGW-', 'd3dcompiler_')):
                continue
            url = base + name + '/' + package.findtext('Version') + archive
            jobs.append((url, archives / archive))

def download(job):
    url, path = job
    expected = get(url + '.sha1').decode().split()[0]
    if not path.exists() or hashlib.sha1(path.read_bytes()).hexdigest() != expected:
        data = get(url)
        assert hashlib.sha1(data).hexdigest() == expected, f'Qt archive checksum mismatch: {url}'
        path.write_bytes(data)
    print('Verified', path.name, path.stat().st_size, flush=True)
    return path

with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    downloaded = list(pool.map(download, jobs))
for archive in downloaded:
    kit_name = 'android_' + android_kit if '-Android-' in archive.name else 'mingw_64'
    destination = out / '6.11.2' / kit_name
    if archive.name.startswith(('MinGW-', 'd3dcompiler_')):
        destination = destination / 'bin'
    subprocess.run([str(seven), 'x', '-y', '-bso0', '-bsp0', '-o' + str(destination), str(archive)], check=True)
for kit in (out / '6.11.2').iterdir():
    if kit.is_dir():
        (kit / 'bin').mkdir(exist_ok=True)
        (kit / 'bin/qt.conf').write_text('[Paths]\nPrefix=..\n', encoding='utf-8')
print('Qt kits installed:', out, flush=True)
