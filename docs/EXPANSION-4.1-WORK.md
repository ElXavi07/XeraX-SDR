# XeraX SDR 4.1 work record

Authorized scope: strengthen supplied-key P25 validation, DMR/RAS reception evidence,
simulcast evaluation, multichannel efficiency, continuous P25 voice following,
receiver optimization, and a reproducible SDS100 comparison workflow.

Work without agents. Preserve 4.0 artifacts and signing identity. User will test
the APK; no phone or SDS100 is available here. Software tests cannot establish
RF superiority or unknown-key recovery.

- [x] Independent AES-128/256 and legacy DES P25 payload vectors, both TDMA slots,
      wrong/missing keys and changing message indicators.
- [x] RAS fixture and explicit receive evidence, distinct from voice encryption.
- [x] Lower-rate filtered shared I/Q delivery and bounded shared capture storage.
- [x] Atomic in-process P25 voice retuning with result acknowledgement.
- [x] Reproducible impaired-signal comparisons and conservative DSP selection.
- [x] Reception checks, capture comparison and physical comparison report workflow.
- [x] English/Spanish UI, regression checks, signed APK and complete source.

Hardware acceptance and an actual SDS100 comparison remain unperformed until
measurements are supplied. Do not mark those as passed from synthetic fixtures.

Completed software deliverable: version 4.1.0 / 40100. Validation: 28 host groups,
67 QML cases, 30 full-I/Q cases, one atomic-command case, 15 app-lab cases,
four offset/filter comparisons, five shared-channel parity cases, ten
simulcast comparisons and 629 Spanish catalog checks. Android release/vital
lint and signing pass. Physical acceptance is still pending as stated above.
