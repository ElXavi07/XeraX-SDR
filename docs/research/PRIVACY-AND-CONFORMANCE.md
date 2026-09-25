# Privacy, encryption and controlled conformance research

Scope: receive-side identification and decryption using authorized supplied material or public synthetic test vectors. This program does not add unknown-key recovery. Existing experimental candidate-search functions are not enabled by its benchmark commands.

## Standards and implementation evidence are different

Track each path as documented, implemented, reference-vector tested, captured-frame tested, or hardware-interoperability tested. Do not label the whole application standards-certified from cipher tests. Vendor specifications and full conformance material are not all publicly available; exact behavior that cannot be verified remains an explicit gap.

The [DMR Association standards index](https://www.dmrassociation.org/dmr-standards.html) identifies ETSI air interface v2.7.1 (May 2026), voice/services, data and Tier III trunking documents. Capacity Plus and Connect Plus are vendor systems, not synonyms for ETSI Tier III. Capacity Max has Tier III interoperability and vendor modes. [Motorola system overview](https://www.motorolasolutions.com/content/dam/msi/docs/EA_Collaterals/ENGLISH/MOTOTRBO/MOTOTRBO_At_a_Glance_Brochure_ASIA-0823-ST06.pdf).

## Mechanisms, observable information and test requirements

| Family | Mechanism and interpretation | What may remain observable when decoded correctly | Controlled validation |
| --- | --- | --- | --- |
| DMR Basic Privacy | Manufacturer-specific legacy masking of encoded voice bits. In the inspected Motorola-compatible XeraX path, an index selects a fixed mask; it is not an arbitrary AES key. Index zero currently means no application in that function. Other vendors differ. | Burst structure, slot, color code and some call/control identifiers; Basic Privacy does not guarantee a separately usable on-air key ID | Known mask/index and known voice payload, wrong-index negatives, vendor/FID gating, both slots and transitions to clear voice |
| DMR Enhanced Privacy | Motorola describes 40-bit protection; compatible implementations use ARC4-derived keystream processing. “Enhanced” is not a universal cross-vendor algorithm name. | Privacy header algorithm/vendor information, key identifier and MI where present/recovered; some link-control metadata | Correct supplied value, MI handling, late entry, stream advancement, missing PI and slot isolation |
| DMR DES/AES profiles | Supported paths generate keystream using the correct key and protocol IV/state. The current parser normalizes several signaled IDs; raw and effective IDs should both be retained. | Algorithm/key identifiers and synchronization material where signaled; recovered identifiers are not secret key material | Independent cipher vectors plus full PI/embedded-signaling acquisition, packet/voice differences, IV progression and rollover |
| NXDN scrambler | A 15-bit digital voice scrambler, distinct from DES/AES. The receiver must use the applicable seed and frame progression. | RAN, frame/link-control structure and supported call identifiers; exact key/cipher signaling depends on format and received messages | Supplied seed including explicit zero semantics, frame placement, NXDN48/96, late entry and context loss |
| NXDN DES/AES | Forum documents DES and AES options in addition to scrambling. Current XeraX payload tests cover DES and AES-256 with established IVs. | Cipher/key fields and call metadata where transmitted outside encrypted content and successfully recovered | Establish the IV from actual signaling; test successive voice frames, loss/reacquisition and Type-C/Type-D distinctions |
| P25 ADP/ARC4 | Legacy vendor-specific stream protection supported with supplied material; do not confuse it with AES | Available algorithm ID, key ID and encryption synchronization information; NAC/network/call metadata where clear | Correct supplied key, Phase 1/2 frame positions, late entry and independent slot context |
| P25 DES/AES | Block-cipher-based voice protection with protocol-specific feedback/keystream and synchronization handling; key plus correct MI/IV/state required | ALGID/KID/MI when recovered; some channel, network and call signaling. Not every identity is always clear/available. | Reference cipher tests and complete HDU/LDU/ESS paths as applicable; corrupted/missing metadata, key changes and restarts |

Sources for the distinctions: [Motorola privacy feature descriptions](https://www.motorolasolutions.com/content/dam/msi/docs/mototrbo_at_a_glance_brochure_anz.pdf), [NXDN Forum FAQ](https://www.nxdn-forum.com/faq/), [NIST block-cipher modes](https://csrc.nist.gov/pubs/sp/800/38/a/final), [OP25 supplied-key scope](https://github.com/boatbod/op25/blob/71abcd0ead32f86f51615ea6cc8a6a4dba4c949a/README.md).

Implementation-specific details above come from pinned XeraX [DMR PI handling](../../upstream/dsd-neo/src/protocol/dmr/dmr_pi.c), [Basic Privacy transform](../../upstream/dsd-neo/src/crypto/crypt-etc.c), [NXDN element handling](../../upstream/dsd-neo/src/protocol/nxdn/nxdn_element.c), and [profile semantics](../../upstream/dsd-neo/docs/decryption-profiles.md). These source observations must not be presented as universal vendor specifications.

For the inspected DMR compatible path, the parser retains an 8-bit key identifier and 32-bit MI, and derives longer IV state for DES/AES. Its internal normalized algorithm values include 0x21 ARC4, 0x22 DES, 0x24 AES-128 and 0x25 AES-256. Preserve the original manufacturer/algorithm context before normalization; a bare number cannot identify all vendor formats. Exact packing, discarded keystream and frame cadence remain part of the per-protocol test vectors, not a generic “AES decrypt” toggle.

RAS is an access/signaling feature distinct from voice confidentiality. Keep a separate provenance flag for CRC-invalid or specially interpreted signaling; global checksum relaxation must not silently create trusted grants or identities. Color codes, RANs, talkgroups and key identifiers do not substitute for key material.

## Correct key lifecycle

Resolve material against protocol, algorithm, system/profile, identifier and current call/slot generation. On a missing or incompatible match, prevent reuse of stale material. On a changed MI, reacquisition or slot, establish the appropriate stream position before decoding. Distinguish configured, selected, applied and verified-with-reference statuses.

OFB/stream decryption generally does not authenticate a key merely by completing. FEC/CRC on ciphertext or clear signaling does not prove the decrypted speech is right. For a test with known plaintext, compare exact bits; for normal reception, report actual evidence without promoting plausible speech into authentication.

## Evidence already available and remaining work

Existing [preview 3 validation](../DECODER-QUALITY.md) includes independent payload vectors for P25 ADP/DES/AES, DMR ADP/DES/AES and NXDN scrambling/DES/AES. DMR/NXDN established-IV tests do not prove on-air IV acquisition. Preserve those tests and add complete signaling-to-audio captures before broader interoperability claims.

The profile documentation currently says radio key profiles are stored unencrypted in app-private files. That is different from the Windows protection used for AI provider keys. A later engineering milestone should protect radio keys with platform storage facilities and prevent material from appearing in exported captures/logs. The public benchmark accepts only synthetic fixture material; production key files are not benchmark artifacts.

Required additions: supported-vendor matrix; unknown/missing-algorithm negatives; correct and wrong authorized material; unsupported-algorithm refusal; both-slot isolation; retune/key-epoch invalidation; lost and corrupted MI; clear/encrypted transitions; byte/bit order; manufacturer reference captures where available. Explicitly mark absent cases pending.
