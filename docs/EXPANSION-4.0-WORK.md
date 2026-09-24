# XeraX SDR 4.0 work record

User authorized all ten proposed improvements. Work without subagents. Preserve 3.0 artifacts and signing identity. Do not describe device/RF acceptance as passed without hardware evidence.

- [x] Complete I/Q-to-protocol regression lab with captured/synthetic fixture provenance and result reports.
- [x] Simultaneous in-band channels using separate decoder processes and bounded input queues.
- [x] Two-device trunking: continuous control receiver plus a voice worker, explicit receiver selection.
- [x] Experimental P25 simulcast processing evaluated against fixtures, with bypass and measurable outcomes.
- [x] Saved-I/Q reprocessing trials with bounded candidate settings and evidence comparison.
- [x] NFM signaling: MDC-1200, FleetSync, DTMF and configurable two-tone detection, actual parser tests.
- [x] Searchable per-call recording library with metadata, favorites, retention and playback/export.
- [x] GPS-aware eligibility/ranking of saved sites/channels with permission, uncertainty and hold guards.
- [x] Band survey with measured activity, timestamps, protocol evidence, listen/save actions.
- [x] Service-owned capture deadline/recovery, UI reattachment, USB recovery and thermal load controls.
- [x] Simple Listen / Scan / Calls / Tools navigation; English/Spanish new screens.
- [x] Host/native/QML checks, signed APK, complete source archive and documented hardware limits.

Architecture: retain the existing main engine and isolate additional engines in Android worker processes. Keep secrets in private configuration transport and never in status or logs. Parallel channels require compatible capture bandwidth; expose resource exhaustion and out-of-band requests explicitly. Advanced processing remains experimental until comparative RF captures demonstrate improvement.

Implementation and software validation are complete. Physical device acceptance remains pending; see UPGRADES-4.0.md and PHONE-ACCEPTANCE.md. The versioned dist verification report records packaging and source checks.
