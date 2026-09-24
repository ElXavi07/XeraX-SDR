function Get-XeraXAndroidTarget {
    param([ValidateSet('arm64-v8a', 'armeabi-v7a')][string]$Abi = 'arm64-v8a')
    if ($Abi -eq 'armeabi-v7a') {
        return @{ Abi=$Abi; Triplet='arm-android-static'; Kit='android_armv7'; Build='app-armeabi-v7a'; Installed='installed-armeabi-v7a'; Suffix='armeabi-v7a' }
    }
    return @{ Abi=$Abi; Triplet='arm64-android-static'; Kit='android_arm64_v8a'; Build='app'; Installed='installed'; Suffix='arm64' }
}
