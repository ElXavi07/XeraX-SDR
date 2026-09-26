# Boundary-policy study: pre-execution checks

The hypothesis and adverse retention control were registered in `b3ee410`
before generating the new inputs. The eighteen waveforms have manifest SHA-256
`11a9a496bc4671d174b4b7cce096598a44d7dd35b0378d63258ceddf652c7c08`.
An independent implementation reconstructed all 72 input files (8,173,904 binary
bytes), the inherited CRC/channel vectors, transformed sample lineage and both
new gap controls. The changed waveform pair differs at exactly 27 shaped sample
positions, 16117 through 16143. Only the designated sync dibit's sign changes;
the LICH and channel bodies remain identical. This validates construction, not
decoding success.

Thirty-one Python counterexample tests pass normally and with optimization
(24 analyzer tests and seven mocked execution/failure-retention tests). An early
test expected a later counter-mismatch message, but the deliberately tampered
record was correctly rejected by the earlier opening-match guard. Only that
test's expected message changed; the failed attempt and correction are retained.
No native replay was used to adjust these checks. Independent source/link review
reverses all three generated files to their registered parents, verifies matching
role builds apart from the enable macro, and binds eighteen checked symbols to
their intended implementations. Thirty-six explicit linked archive identities
are retained; implicit system libraries are outside that archive-hash inventory.

Preflight corrections are retained rather than hidden:

* The first file-creation command failed because the new directory did not yet
  exist. Its following Python invocation could not find the preparer. Neither
  created inputs. After creating the directory and script, input generation ran
  once successfully. `nxdn-boundary-v1-preflight-command-note.txt` records this.
* The first CMake configure could not resolve the imported `mbe_neo::mbe_static`
  target from the parent directory. Declaring the existing dependency packages
  at that directory fixes target visibility; it changes no decoder or library.
  The first log and successful second configure/build logs are retained. Both
  receiver executables and the pure-policy test built with warnings as errors.
* CMake reports path-length warnings for separately configured public-header
  smoke targets. The bounded targets requested here built successfully; this
  study makes no claim that every configured target was built.

The optimized native pure-policy test passes with explicit checks that remain
active under `NDEBUG`. It exercises window edges, canonical and relaxed patterns,
baseline bypass, reset and context changes, incomplete frame bodies, unsigned
rollover and expiry. It is not a receiver replay or RF acceptance test.

The sixteen archived observation-v2 anchor invocations also pass the new Python
input/observation adapter without native re-execution. Original recovery and
observation results remain frozen. The runner must copy their exact event and
sample-trace files before any new receiver process, then compare all sixteen
baseline invocations byte-for-byte. Its separate policy log does not change the
archived stdout contract.

Measurement and progression are separate gates. A correctly measured loss in
the deliberately off-phase relaxed-sync control must reject progression even
if corrupted-sync cases improve. The isolated runtime owns only one receiver;
hidden configuration changes between observed contexts, multireceiver ownership,
independent clear-speech truth and actual complex-IQ/RF/phone tests remain outside
this screen. No release defaults or user settings change.
