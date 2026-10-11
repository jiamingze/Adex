"""iOS preflight; never reports syntax checks as simulator/real-device acceptance."""
import json,plistlib,shutil,subprocess,os
from pathlib import Path
root=Path(__file__).resolve().parents[1]
config=json.loads((root/'apps/ios/capacitor.config.json').read_text())
assert config['appId']=='io.adex.personal'
scene=(root/'apps/ios/ios/App/App/SceneDelegate.swift').read_text()
assert 'AdexBridge()' in scene and 'import CapApp_SPM' in scene
bridge=root/'apps/ios/ios/App/CapApp-SPM/Sources/CapApp-SPM/AdexBridge.swift'
assert 'registerPluginInstance(SecureSessionPlugin())' in bridge.read_text()
assert 'requiresOnDeviceRecognition = true' in bridge.read_text()
with (root/'apps/ios/ios/App/App/Info.plist').open('rb') as f:
    plist=plistlib.load(f)
for key in ('NSCameraUsageDescription','NSMicrophoneUsageDescription','NSSpeechRecognitionUsageDescription','NSPhotoLibraryUsageDescription'):
    assert plist[key]
assert 'NSAllowsArbitraryLoads' not in str(plist)
subprocess.run(['swiftc','-frontend','-parse',str(bridge),str(root/'apps/ios/ios/App/App/SceneDelegate.swift'),str(root/'apps/ios/ios/App/App/AppDelegate.swift')],check=True)
print('PASS: native bridge wiring, permissions, on-device speech, Swift syntax')
selected=subprocess.check_output(['xcode-select','-p'],text=True).strip()
free=shutil.disk_usage(root).free//1024**3
print('Selected developer tools:',selected,'; free disk GiB:',free)
if 'Xcode.app/Contents/Developer' not in selected:
    print('BLOCKED: full Xcode/iOS SDK absent; no simulator build or device acceptance claimed')
    raise SystemExit(2)
subprocess.run(['xcodebuild','-project',str(root/'apps/ios/ios/App/App.xcodeproj'),'-scheme','App','-destination','generic/platform=iOS Simulator','-derivedDataPath',str(root/'.local-data/ios-derived'),'CODE_SIGNING_ALLOWED=NO','build'],check=True)
print('PASS: unsigned simulator build; interactive playback/camera/microphone still require simulator/device checks')
