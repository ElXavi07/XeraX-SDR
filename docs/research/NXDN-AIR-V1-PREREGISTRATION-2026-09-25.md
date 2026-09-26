# Independent clear NXDN air-frame construction: registered reference gate

Register before generating this corpus or executing a primary frame encoder.
Preserve receiver/source baseline `85bec0a62bb21f5f1bec75d6da9c65820462b39c`,
all earlier experiments and released Android/Windows artifacts. No receiver
candidate or app default changes in this stage.

## Hypothesis and fixed domain

H1: an arithmetic complete-frame builder agrees exactly with an independently
compiled pinned primary encoder for the following nine clear conventional
frames, before and after channel whitening. Every known source voice word must
occupy its registered payload interval, including both half-steal directions.
This supplies frame-level reference data, not receiver acquisition, semantic
call acceptance, voice synthesis, audio, I/Q, RF or throughput results.

Use the primary source manifest already frozen at SHA-256
`e5dda2c6b072ca4eda65d2c75c3f16550a6cafb52c8fd8e04f34c47363a24ca1`:
MMDVM-Host `590c531391dfd3146073afbc3956f70d42c62a46` and NXDNClients
`8950677e9876e577fb87b955cfa93bacd059209d`. Retain source bytes, Git blob
identities and original notices. Use the twenty source announcement words
already verified by the voice-word study, in their original zero-based order.
The earlier expected channel bytes must retain SHA-256
`05ed6f2d7c548e6b6e94e81bb12534afde0c2e13301791a8f1d4d2778dd6eed3`.
Do not use receiver output as source truth.

## Exact frames

Fix RDCH, outbound direction, RAN 1, source ID 901 and destination group 1201.
Clear VCALL information is ten bytes `01 00 20 03 85 04 B1 00 00 00`.
TX_REL differs only in its first byte, `08`. No privacy key, cipher or key
search is involved. The first 72 VCALL information bits supply four ordered
18-bit SACCH fragments. Header/trailer use the 18-bit SACCH IDLE information
beginning `10 00 00`, with single structure 0. Every unused padding bit is zero.

| ID | Profile | Full LICH | Structure / fragment | Source quartet | Voice words transmitted |
|---:|---|---|---|---|---|
| 0 | Full repeated FACCH VCALL header | 83 | 0 / IDLE | zero placeholder | none |
| 1 | Pure voice | AE | 3 / 0 | 0,1,2,3 | 0,1,2,3 |
| 2 | Pure voice | AE | 2 / 1 | 4,5,6,7 | 4,5,6,7 |
| 3 | Pure voice | AE | 1 / 2 | 8,9,10,11 | 8,9,10,11 |
| 4 | Pure voice | AE | 0 / 3 | 12,13,14,15 | 12,13,14,15 |
| 5 | Pure voice | AE | 3 / 0 | 16,17,18,19 | 16,17,18,19 |
| 6 | FACCH first half, voice second | A6 | 2 / 1 | 0,1,2,3 | 2,3 |
| 7 | Voice first half, FACCH second | AA | 1 / 2 | 4,5,6,7 | 4,5 |
| 8 | Full repeated FACCH TX_REL trailer | 83 | 0 / IDLE | zero placeholder | none |

LICH values in the table are hexadecimal. Half-steal FACCH carries the same
VCALL information as the header. Pure-voice FACCH input is ten zero placeholder
bytes and is not transmitted. Each nonzero quartet is two normalized 13-byte
source-word pairs; header/trailer supply 26 zero placeholder bytes. The second
SACCH cycle ends after fragments 0,1,2 before the trailer; no completed second
SACCH message or successfully reconstructed receiver call is claimed.

Each primary input record is exactly **41 bytes**: full LICH byte, four SACCH
raw bytes (26 information bits then six zero padding bits), ten FACCH information
bytes, and 26 source voice bytes. Total input is 369 bytes. Preserve IDs, profile
names, source indices and both transmitted/unused field expectations separately.

Each 48-byte complete frame contains 20 sync bits, 16 LICH bits, 60 SACCH bits,
and two 144-bit payload halves. FACCH offsets are 96 and 240 bits; voice pairs
start at byte offsets 12 and 30. There are nine SACCH, six FACCH channels and
24 transmitted voice words. Emit **96 bytes per record**, raw48 then air48;
nine outputs total 864 bytes, including 432 whitened air bytes. Preserve the
entire expected/output stream and inspect both forms independently.

## Primary encoder and minimal oracle corrections

Compile pinned NXDNLICH, NXDNSACCH, NXDNFACCH1, NXDNConvolution, NXDNCRC,
NXDNAudio, Golay24128 and Sync, required original headers, plus the exact pinned
countBits support already used by the voice-word wrapper. Do not compile the
host/network application or replace any encoding routine with a test stub.
Extract the original 48-byte channel-whitening constant from NXDNControl.cpp
into an explicitly attributed generated header; its first 20 bits must be zero.
Only the separate arithmetic builder generates the whitening recurrence.

Retain untouched original files and produce separate audit copies with exactly
these five encoding-path changes, checked by exact replacement count and diff:

1. In FACCH1::encode, replace `i != PUNCTURE_LIST[index]` with the equivalent
   bounded test `index >= 48U || i != PUNCTURE_LIST[index]`. The final puncture at
   coded bit 189 exhausts 48 entries; bits 190 and 191 remain transmitted.
2. Zero-initialize SACCH::encode's nine-byte convolution output temporary.
3. Zero-initialize SACCH::encode's eight-byte punctured output temporary.
4. Zero-initialize FACCH1::encode's 24-byte convolution output temporary.
5. Zero-initialize FACCH1::encode's 18-byte punctured output temporary.

The bit-writing macro reads/modifies destination bytes; deterministic temporary
initialization avoids relying on indeterminate values. No decoder method or
protocol behavior is patched. Initialize frame/output buffers, LICH state with
setRaw(0), and SACCH's used raw bytes before setters. FACCH setData supplies all
80 information bits. Preserve generated source/header hashes and link maps.

The primary wrapper must validate exact input dimensions and registered record
shape, reject reused outputs, and invoke each needed real encoder in one fixed
batch. Output summary includes frames9, input_bytes369, output_bytes864,
sacch_calls9, facch_calls6 and voice_pair_calls12. Preserve failed output and
never rerun the native batch for a favorable result.

## Independent construction and gate

The arithmetic side may reuse the previously frozen independent control CRC/
convolution/interleave primitives and voice-word arithmetic, with exact hashes
retained and historical files unchanged. It must not read primary encoding
tables or receiver/decoder outputs. Explicitly encode LICH parity only for the
four registered profiles; do not generalize the pinned limited parity rule.
Validate word IDs against the original source slice and previously agreed word
channels. Generate channel whitening arithmetically, reset for each frame,
leaving the sync unchanged. This operation is not traffic privacy.

Freeze input, expected raw/air bytes, source/index metadata, every harness source,
primary originals/audit copies, compiler/runtime/binary identities and checker
before the only new native execution. Require byte-exact agreement for all 864
output bytes, exact summary counts, expected source fields, every voice interval
and the original/frozen/historical preservation hashes. Any disagreement fails
this reference gate and blocks later receiver claims; no favorable subset.

Before execution, checker counterexamples must reject missing/extra/reordered
records, a changed raw byte, a changed air byte, omitted or misplaced whitening,
swapped half-steal payloads, changed source IDs/metadata and malformed summaries.
These are deliberately corrupted evidence controls, **not measured RF false
acceptance or receiver rejection tests**. Run guards normally and with Python
optimization. Retain all preflight failures/corrections separately.

After a pass, a separate registration is required for full-engine routing,
voice-word observation neutrality, clean/negative controls and impaired signals.
The previous malformed-header PCM episode and rejected boundary veto remain
unfixed. Physical device tests and independent I/Q stay pending; no APK/EXE
promotion, performance or audio-quality claim follows from this stage alone.
