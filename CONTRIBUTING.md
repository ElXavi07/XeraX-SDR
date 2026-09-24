# Contributing to XeraX SDR

English and Spanish reports and contributions are welcome. Reproducible receiver results are especially useful during community testing.

## Report a problem

Include the installed version/ABI, phone and Android version, SDR model, USB/network connection, frequency/mode, steps, expected result and actual behavior. For no audio, include whether **Test sound** plays, whether the spectrum moves and whether PCM is reported. Control traffic without voice is different from a player failure.

Use the hardware-result form for successful tests too. Explain exactly what worked and for how long. Review attachments: remove passwords, API/radio keys, personal labels and private location/network details. Share recordings only when you have permission to redistribute them. Synthetic fixtures are welcome.

## Propose changes

Open a focused pull request against main, explain the resulting behavior and include relevant checks. Distinguish host/synthetic tests from actual hardware results. Claims about sensitivity or intelligibility need reproducible comparisons.

The full engine is under upstream/dsd-neo; UPSTREAM.json pins the original commit. Its source manifest describes the released baseline. After editing that baseline, build directly: prepare_source.py intentionally refuses a changed archive tree instead of resetting it. Preserve attribution and license notices.

See [BUILD](docs/BUILD.md) and [phone acceptance](docs/PHONE-ACCEPTANCE.md). Check Spanish and narrow screens for UI work. Do not commit signing material, credentials, personal captures or APKs; distribution packages belong in release assets.

Contributions use the applicable GPL-3.0-or-later terms, retaining compatible third-party notices and your authorship.
