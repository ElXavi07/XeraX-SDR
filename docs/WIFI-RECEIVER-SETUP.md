# XeraX SDR over home Wi-Fi

If the phone connects but receives no samples, the server may have a stale USB handle. Stop other applications using the dongle and restart the server. The helper's Status action reports recent USB errors; a listening port alone does not prove that I/Q samples are arriving.

The RTL-SDR plugs into the Windows computer; the phone receives raw I/Q over the local network. The phone and computer must be on the same home network. The receiver/antenna location determines the signals you hear. Keep the computer awake and powered while listening.

This setup uses the RTL-SDR Blog Windows V1.4.0 release:
https://github.com/rtlsdrblog/rtl-sdr-blog/releases/tag/V1.4.0

Downloaded `Release.zip` SHA-256, verified against the published GitHub asset digest:
`7ef33f1304647f65e5e0fde43637a73d54f076e91e651a3cecc4f55a17fd9815`

Software directory: `%LOCALAPPDATA%\XeraXSDR-remote\rtl-sdr-blog-V1.4.0\x64`.
The setup does not alter the XeraX APK or its saved radio systems.

The helper does **not** download the receiver utilities or install Windows USB drivers. Before using it, download the linked manufacturer's release, verify its checksum, and place its x64 utilities and required DLLs in the directory above. Follow the manufacturer's WinUSB instructions for the actual RTL device. The helper expects `rtl_tcp.exe` there. A separately configured compatible server is also supported; enter its address/port in the app.

## Computer controls

From the SDR project directory in PowerShell:

```powershell
./scripts/remote-receiver.ps1 -Action Status
./scripts/remote-receiver.ps1 -Action Firewall -Elevate
./scripts/remote-receiver.ps1 -Action Start
./scripts/remote-receiver.ps1 -Action Stop
```

The firewall step needs Windows administrator approval. It adds one inbound TCP rule for this exact executable and port 1234, limited to private networks and local-subnet clients. No router port forwarding is needed.

Status reads the saved firewall configuration if Windows denies the firewall cmdlet to a standard user. If both checks are denied, it reports an unknown result rather than incorrectly reporting a missing rule. A saved rule alone does not confirm that the phone can connect.

Start selects the current private-network IPv4 address. If there is more than one, specify `-ListenAddress <your-home-network-IP>`. The server starts hidden and logs to `%LOCALAPPDATA%\XeraXSDR-remote\server-output.log` and `server-error.log`. Stop only targets the process recorded by this launcher, with executable and start-time verification.

## Phone

1. Connect the phone to the same home Wi-Fi, outside any isolated guest network.
2. Open XeraX → Explore and choose **RTL-TCP** as the source.
3. Enter the host address printed by Start and port **1234**. Use your computer's current LAN address; DHCP may change it.
4. Choose a known frequency and the appropriate mode. For VHF/UHF analog two-way voice choose **Analog NFM**.
5. Start listening, choose **Phone speaker**, raise media volume and temporarily open squelch if testing audio. Return squelch to a suitable level afterward.

Only one ordinary rtl_tcp client can control this server at a time. Close other SDR applications using the dongle before starting. A server connection test is separate from intelligible RF reception. For an internet connection later, use a private VPN and assess raw-I/Q bandwidth; this setup is local Wi-Fi only.

## Connected but silent

Stop the session and reopen Explore with the same RTL-TCP host and port. For a specific local test, NOAA lists Coachella weather radio at **162.400 MHz**, and its Spanish service at **162.525 MHz**: https://www.weather.gov/psr/nwr . Reception depends on the antenna, location and transmitter availability.

Choose **Analog FM (NFM)**, start listening, turn squelch off, unmute and select **Phone speaker**. Raise the phone's media volume. Listen for either the weather broadcast or channel noise, and check whether the spectrum is updating. Auto digital does not play analog weather broadcasts. The monitor's "waiting for signal" message is based on call/carrier status; it is not a test of the analog speaker path.

If the spectrum moves but the speaker remains completely silent with those settings, inspect Radio's reported audio output and reception check. If the spectrum has no incoming data, inspect the receiver connection and logs first.

## Receiver detection

The device must appear in Windows before a receiver-specific driver can be configured. If the RTL-SDR utility says `No supported devices found`, check the physical dongle, USB port or hub first. Do not replace a driver on an unrelated USB device. For a confirmed RTL-SDR with an incorrect driver, follow the manufacturer's WinUSB setup: https://www.rtl-sdr.com/rtl-sdr-quick-start-guide/ .
