# RC3 integration: NXDN confirmation across rejected frames

The next Android and Windows candidate integrates the exact frame-accounting
correction measured in the [LICH-gap study](NXDN-LICH-GAP-2026-09-25.md) and
[continuous-engine study](NXDN-ENGINE-GAP-2026-09-25.md). A rejected LICH now closes
the current frame's evidence accounting. Two weak CRC observations separated by
that rejection cannot count as consecutive frames. An already confirmed
transmission retains its historical confirmation; the rejected frame supplies
no current proof. Protocol decoding, CRC algorithms and key handling are unchanged.

The continuous-engine test's two strictly adjacent W/P/W/W cases changed returns
from `0/0/2/2` to `0/0/0/2`. Six additional parity sequences with incidental
rejections showed the same following-frame correction. Strong-frame and actual
no-carrier reset controls passed. These are controlled discriminator-stream
results, not a new RF sensitivity, decoding speed or voice-quality measurement.

## Source acceptance and frozen research

The pre-integration tree is
`9b6cf5c4c41d3d5f9496039b14e008435bbf4249`. Its original frame SHA-256 is
`9022df4c611a129332123f7062a99e478ea4d24e0ce6f6a5104b5cc7fb191192`.
The integrated source preserves the original CRLF line endings; its SHA-256 is
`a2c0d15efd6258c1469df2ebbb7dea05400f9e0ab74fba653c1e20125f04919a`.
After converting CRLF to LF only, its bytes exactly equal the measured candidate,
SHA-256 `457bc11c3672d7cffc6b70facd19afe1de3c6fa433d075d5f511bb44b8ad8181`.

The five completed frame-based study workflows reproduce that immutable full
tree. Their output is historical reproduction, not validation of the current
product. Published reports, preregistrations, preparer hash guards and evidence
remain unchanged. To reproduce locally, check out that commit into a separate
detached worktree and use a new out-of-tree build directory. Running the old
LICH/engine preparers against integrated source must continue to reject it.

A separate current-source workflow runs the actual product's routing,
confirmation, dispatcher and synchronization regressions in release and
ASan/UBSan configurations. The new caller regression checks parity, unsupported
LICH and direction rejection between weak frames, as well as sticky confirmation.
Its channel-evidence stubs isolate frame accounting; the previously published
studies separately establish behavior through real channel FEC and CRC paths.

## Candidate and compatibility policy

Version `4.3.2-rc.3` uses Android versionCode `40304`, retains application ID
`com.xerax.sdr`, the established Android signing identity and Windows installer
AppId. It requires no settings migration. Faster NXDN48 acquisition remains an
explicit experimental option, off by default. The accounting correction applies
whether that option is enabled or disabled.

Build Android arm64/armeabi-v7a and Windows into separate new caches; sign/package
only those caches. Verify APK manifests, signing certificates, dependency
closure and ELF alignment, and test the staged Windows executable before
checking every portable ZIP entry against the stage. Prior RC1/RC2 assets are
frozen and must retain all thirteen recorded artifact/verification hashes.

Actual build and test outcomes belong in the RC3 release verification record;
this integration note alone does not certify a binary. Physical phone/RF,
human intelligibility and installer execution remain separate acceptance work.
No default-on acquisition promotion, encryption recovery, GPU acceleration or
whole-application speed claim accompanies this correctness change.
