import requests
import xml.etree.ElementTree as ET

for base in [
    'https://download.qt.io/online/qtsdkrepository/windows_x86/desktop/qt6_6112/qt6_6112_mingw/',
    'https://download.qt.io/online/qtsdkrepository/all_os/android/qt6_6112/qt6_6112_arm64_v8a/',
]:
    print(base)
    response = requests.get(base + 'Updates.xml', timeout=30)
    response.raise_for_status()
    for package in ET.fromstring(response.content).findall('PackageUpdate'):
        archives = package.findtext('DownloadableArchives')
        if archives:
            print(package.findtext('Name'), package.findtext('Version'), archives)
