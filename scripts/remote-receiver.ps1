param(
    [ValidateSet('Status','Start','Stop','Restart','Firewall')][string]$Action='Status',
    [string]$ListenAddress,
    [ValidateRange(1,65535)][int]$Port=1234,
    [switch]$Elevate
)
$ErrorActionPreference='Stop'
$taskRoot=Join-Path $env:LOCALAPPDATA 'XeraXSDR-remote'
$taskExe=Join-Path $taskRoot 'rtl-sdr-blog-V1.4.0\x64\rtl_tcp.exe'
$taskRecord=Join-Path $taskRoot 'server.json'
$taskFirewallName='XeraXSDR-rtl-tcp-LAN'
function Get-XeraXUsbFault {
    $taskLog=Join-Path $taskRoot 'server-error.log'
    if(!(Test-Path -LiteralPath $taskLog)) { return $false }
    $taskLines=Get-Content -LiteralPath $taskLog -Tail 80 -ErrorAction SilentlyContinue
    return [bool]($taskLines -match 'rtlsdr_demod_(write|read)_reg failed|r82xx_write:.*failed|Failed to submit transfer')
}
function Get-XeraXFirewallStatus {
    try {
        $taskRules=@(Get-NetFirewallRule -PolicyStore PersistentStore -ErrorAction Stop)
        return [pscustomobject]@{Installed=(@($taskRules | Where-Object { $_.Name -eq $taskFirewallName }).Count -gt 0);Source='Firewall cmdlet';Error=$null}
    } catch {
        # Windows can deny the firewall cmdlet to a standard user. Read the
        # saved rule instead; an unreadable configuration is not a missing rule.
        try {
            $taskKey=Get-Item -LiteralPath 'HKLM:\SYSTEM\CurrentControlSet\Services\SharedAccess\Parameters\FirewallPolicy\FirewallRules' -ErrorAction Stop
            return [pscustomobject]@{Installed=($null -ne $taskKey.GetValue($taskFirewallName));Source='Saved firewall configuration';Error=$null}
        } catch {
            return [pscustomobject]@{Installed=$null;Source='Unavailable';Error=$_.Exception.Message}
        }
    }
}
function Get-XeraXServer {
    if(!(Test-Path -LiteralPath $taskRecord)) { return $null }
    $taskSaved=Get-Content -LiteralPath $taskRecord -Raw | ConvertFrom-Json
    $taskProcess=Get-Process -Id $taskSaved.processId -ErrorAction SilentlyContinue
    if($taskProcess -and $taskProcess.Path -eq $taskExe -and
        $taskProcess.StartTime.ToUniversalTime().Ticks -eq ([datetime]$taskSaved.startTime).ToUniversalTime().Ticks) { return $taskProcess }
    return $null
}
function Get-XeraXAddress {
    if($ListenAddress) {
        $taskMatch=Get-NetIPAddress -AddressFamily IPv4 -IPAddress $ListenAddress -ErrorAction SilentlyContinue
        if(!$taskMatch) { throw 'The requested address is not assigned to this computer.' }
        $taskProfile=Get-NetConnectionProfile -InterfaceIndex $taskMatch.InterfaceIndex -ErrorAction SilentlyContinue
        if($taskProfile.NetworkCategory -ne 'Private') { throw 'Choose the address of your private home network.' }
        return $ListenAddress
    }
    $taskCandidates=@(Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway } | Where-Object {
        (Get-NetConnectionProfile -InterfaceIndex $_.InterfaceIndex -ErrorAction SilentlyContinue).NetworkCategory -eq 'Private'
    })
    if($taskCandidates.Count -ne 1) { throw 'Select one private home-network IPv4 address using -ListenAddress.' }
    return [string]$taskCandidates[0].IPv4Address.IPAddress
}
switch($Action) {
    'Restart' {
        # Stop only the process whose executable AND creation time match our record.
        # Recover a stale USB handle without changing drivers or firewall policy.
        & $PSCommandPath -Action Stop
        $taskStartArgs=@{Action='Start';Port=$Port}
        if($ListenAddress) { $taskStartArgs.ListenAddress=$ListenAddress }
        & $PSCommandPath @taskStartArgs
    }
    'Status' {
        $taskCurrent=Get-XeraXServer
        $taskFirewall=Get-XeraXFirewallStatus
        $taskInfo=if(Test-Path -LiteralPath $taskRecord) { Get-Content -LiteralPath $taskRecord -Raw | ConvertFrom-Json } else { $null }
        [pscustomobject]@{
            SoftwareInstalled=(Test-Path -LiteralPath $taskExe)
            Running=($null -ne $taskCurrent)
            Address=Get-XeraXAddress
            Port=$Port
            ProcessId=if($taskCurrent) { $taskCurrent.Id } else { $null }
            UsbErrorsInRecentLog=Get-XeraXUsbFault
            HealthNote=if(Get-XeraXUsbFault) { 'USB errors recorded. Use Restart Receiver after checking the dongle connection.' } else { 'A listener alone does not prove radio samples or phone audio.' }
            LastSession=$taskInfo
            FirewallRuleInstalled=$taskFirewall.Installed
            FirewallCheckSource=$taskFirewall.Source
            FirewallCheckError=$taskFirewall.Error
            DetectedRtlDevices=@(Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -match '^USB\\VID_0BDA&PID_(2832|2838)' } | Select-Object Status,FriendlyName)
        } | ConvertTo-Json -Depth 4
    }
    'Start' {
        if(!(Test-Path -LiteralPath $taskExe)) { throw 'Install the verified RTL-SDR Blog V1.4.0 package first.' }
        $taskCurrent=Get-XeraXServer
        if($taskCurrent) {
            Write-Output 'The XeraX receiver server is already running.'
            if(Get-XeraXUsbFault) { Write-Output 'USB failures were recorded. Use Restart Receiver to reopen the dongle.' }
            return
        }
        if(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) { throw "Port $Port is already in use. No existing process was stopped." }
        $taskAddress=Get-XeraXAddress
        $taskOut=Join-Path $taskRoot 'server-output.log'; $taskErr=Join-Path $taskRoot 'server-error.log'
        # Bind only to the selected private-network interface. Bias tee stays off.
        $taskProcess=Start-Process -FilePath $taskExe -ArgumentList @('-a',$taskAddress,'-p',"$Port",'-s','1536000','-f','155000000','-d','0') `
            -WorkingDirectory (Split-Path $taskExe) -WindowStyle Hidden -PassThru -RedirectStandardOutput $taskOut -RedirectStandardError $taskErr
        $taskStart=$taskProcess.StartTime.ToUniversalTime().ToString('o')
        for($taskTry=0;$taskTry -lt 25;$taskTry++) {
            Start-Sleep -Milliseconds 200; $taskProcess.Refresh()
            if($taskProcess.HasExited) {
                $taskErrorText=Get-Content -LiteralPath $taskErr -Raw -ErrorAction SilentlyContinue
                throw "Receiver did not start. $taskErrorText"
            }
            if(Get-NetTCPConnection -LocalAddress $taskAddress -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) { break }
        }
        if(!(Get-NetTCPConnection -LocalAddress $taskAddress -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)) {
            $taskProcess.Kill(); throw 'The receiver did not open its listener. Check server-error.log.'
        }
        [pscustomobject]@{processId=$taskProcess.Id;startTime=$taskStart;address=$taskAddress;port=$Port;executable=$taskExe} |
            ConvertTo-Json | Set-Content -LiteralPath $taskRecord -Encoding UTF8
        Write-Output "Receiver listening. In XeraX select RTL-TCP, host $taskAddress, port $Port."
        $taskFirewall=Get-XeraXFirewallStatus
        if($false -eq $taskFirewall.Installed) {
            Write-Output 'The private-LAN firewall rule still needs administrator setup: use -Action Firewall -Elevate.'
        } elseif($null -eq $taskFirewall.Installed) {
            Write-Output 'Windows did not permit a firewall status check. Try connecting from the phone to confirm access.'
        }
    }
    'Stop' {
        $taskCurrent=Get-XeraXServer
        if($taskCurrent) {
            Stop-Process -InputObject $taskCurrent
            if(!$taskCurrent.WaitForExit(5000)) { throw 'Receiver did not stop; no replacement was started.' }
            Write-Output 'XeraX receiver stopped.'
        }
        else { Write-Output 'No matching XeraX receiver process is running.' }
    }
    'Firewall' {
        if(!(Test-Path -LiteralPath $taskExe)) { throw 'Receiver software is not installed.' }
        $taskAdmin=([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
        if(!$taskAdmin) {
            if(!$Elevate) { throw 'Windows requires administrator permission for the private-LAN firewall rule. Run again with -Elevate to show its UAC prompt.' }
            $taskShell=Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
            Start-Process -FilePath $taskShell -Verb RunAs -WindowStyle Hidden `
                -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',('"'+$PSCommandPath+'"'),'-Action','Firewall','-Port',"$Port") | Out-Null
            Write-Output 'Windows administrator approval requested. Run Status afterward to verify the rule.'
            return
        }
        try {
            $taskRule=Get-NetFirewallRule -Name $taskFirewallName -ErrorAction SilentlyContinue
            if($taskRule) {
                Set-NetFirewallRule -Name $taskFirewallName -Enabled True -Direction Inbound -Action Allow -Profile Private `
                    -Program $taskExe -Protocol TCP -LocalPort $Port -RemoteAddress LocalSubnet -EdgeTraversalPolicy Block | Out-Null
            } else {
                New-NetFirewallRule -Name $taskFirewallName -DisplayName 'XeraX SDR - RTL-TCP home network' `
                    -Description 'Allow the XeraX RTL-TCP receiver from the local subnet on private networks only.' `
                    -Enabled True -Direction Inbound -Action Allow -Profile Private -Program $taskExe `
                    -Protocol TCP -LocalPort $Port -RemoteAddress LocalSubnet -EdgeTraversalPolicy Block | Out-Null
            }
            'Private-network TCP rule installed.' | Set-Content -LiteralPath (Join-Path $taskRoot 'firewall-result.txt')
            Write-Output 'Private-network TCP rule installed.'
        } catch {
            $_.Exception.Message | Set-Content -LiteralPath (Join-Path $taskRoot 'firewall-result.txt')
            throw
        }
    }
}
