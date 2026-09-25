import re,json
from pathlib import Path
r=Path(__file__).resolve().parents[1]/'upstream/dsd-neo/src/ui/qt'
d=json.loads((r/'i18n/es.json').read_text(encoding='utf-8'))
missing_count=0
for file in ['range_scanner.cpp','qml/RangeScanSettings.qml','qml/RangeScannerScreen.qml','ai_receiver.cpp','qml/AiReceiverScreen.qml','receiver_assistant.cpp','receiver_tools.cpp','qml/ReceiverToolsScreen.qml','qml/AdvancedReceiverToolsScreen.qml','receiver_expansion.cpp','call_library.cpp','qml/ExpansionScreen.qml','qml/CallsScreen.qml','qml/BottomNav.qml','qml/AudioOutputPicker.qml']:
    strings=re.findall(r'(?:qsTr|tr)\("((?:[^"\\]|\\.)*)"', (r/file).read_text(encoding='utf-8'))
    missing=[s for s in strings if s.replace(r'\n','\n') not in d]
    if missing:
        print(file,json.dumps(missing,ensure_ascii=False))
        missing_count+=len(missing)
for key,value in d.items():
    assert sorted(re.findall(r'%[1-9n]',key))==sorted(re.findall(r'%[1-9n]',value)),key
for file in [r/'desktop_media.cpp', r/'../../../windows/desktop_host.cpp', r/'qml/OnboardingScreen.qml', r/'qml/DesktopSidebar.qml', r/'qml/DesktopWelcomeCard.qml', r/'qml/DesktopScanScreen.qml']:
    for s in re.findall(r'(?:qsTr|tr)\("((?:[^"\\]|\\.)*)"', file.read_text(encoding='utf-8')):
        assert s.replace(r'\n','\n') in d, f'Untranslated Windows message: {s}'
print(f'{len(d)} translation placeholder checks passed')
assert not missing_count, f'{missing_count} untranslated receiver-tool messages'
