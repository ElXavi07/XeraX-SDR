"""Include the notices for the exact native dependencies shipped in the APK."""
from pathlib import Path
import argparse
import json
import shutil
import sys
import requests

root = Path(__file__).resolve().parents[1]
release = json.loads((root / 'UPSTREAM.json').read_text())
parser = argparse.ArgumentParser()
parser.add_argument('cache', type=Path)
parser.add_argument('--abi', choices=['arm64-v8a', 'armeabi-v7a'], default='arm64-v8a')
args = parser.parse_args()
cache = args.cache.resolve()
installed = 'installed-armeabi-v7a/arm-android-static' if args.abi == 'armeabi-v7a' else 'installed/arm64-android-static'
kit = 'android_armv7' if args.abi == 'armeabi-v7a' else 'android_arm64_v8a'
target = root / 'upstream/dsd-neo/android/package/assets/doc/xerax'
target.mkdir(parents=True, exist_ok=True)
for notice in (cache / installed / 'share').glob('*/copyright'):
    destination = target / 'third-party' / notice.parent.name / 'LICENSE.txt'
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(notice, destination)
hackrf_notice = target / 'third-party/libhackrf/LICENSE.txt'
shutil.copyfile(root / 'docs/AI-4.2.0.md', target / 'AI-4.2.0.md')
shutil.copyfile(root / 'docs/RANGE-SCANNER-4.3.0.md', target / 'RANGE-SCANNER-4.3.0.md')
shutil.copyfile(root / 'upstream/dsd-neo/PRIVACY_POLICY.md', target / 'PRIVACY_POLICY.md')
hackrf_notice.parent.mkdir(parents=True, exist_ok=True)
shutil.copyfile(root / 'upstream/dsd-neo/android/third_party/libhackrf/LICENSE', hackrf_notice)
for name in ['LGPL-3.0-only.txt', 'GPL-3.0-only.txt', 'Qt-GPL-exception-1.0.txt']:
    destination = target / 'qt' / name
    if not destination.exists():
        response = requests.get('https://raw.githubusercontent.com/qt/qtbase/v6.11.2/LICENSES/' + name, timeout=45)
        response.raise_for_status()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(response.content)
for sbom in (cache / 'QtKits/6.11.2' / kit / 'sbom').glob('*'):
    if sbom.is_file():
        destination = target / 'qt/sbom' / args.abi / sbom.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(sbom, destination)
(target / 'NOTICE.txt').write_text(
    f'XeraX SDR {release["version"]}\n'
    'Independent derivative of DSD-neo, https://github.com/arancormonk/dsd-neo\n'
    'Engine source: 8c9c120389401fc2db3ef52869e13d555712e5fb\n'
    'XeraX modifications and build scripts: GPL-3.0-or-later.\n'
    'Upstream copyright and third-party notices remain applicable.\n'
    'DCS parity matrix and code set: SDRangel, Copyright (C) 2021 Edouard Griffiths, F4EXB, GPL-3.0-or-later.\n'
    'https://github.com/f4exb/sdrangel/tree/master/sdrbase\n'
    'MDC-1200 and FleetSync layouts/CRC/deinterleaving adapted from SDRTrunk, Copyright (C) 2014-2018 Dennis Sheirer, GPL-3.0-or-later.\n'
    'https://github.com/DSheirer/sdrtrunk (80360029efb008dca993938d1e34ad4a7a8c15bd)\n'
    'Qt 6.11.2 sources: https://download.qt.io/official_releases/qt/6.11/6.11.2/submodules/\n'
    'Source and build instructions accompany this APK in the XeraX SDR source bundle.\n', encoding='utf-8')
print('Staged dependency notices:', target)
