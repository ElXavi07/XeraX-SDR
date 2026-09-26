# Private acquisition candidate provenance

Registration: `76e175aef1b8f30431c07cb3d4a50d431b858c02`. Baseline: `ec712a0869184c0b73ec06b1ce36d3d1bdaf6b04`.

Each original working-tree file was byte-copied before modification. Its normalized bytes were checked against the baseline Git blob. Only private copies change; no state-layout field or persistent availability state is added.

| Source | Original SHA256 | Git blob | Candidate SHA256 |
|---|---|---|---|
| `src/dsp/dsd_symbol.c` | `40da0a486400ed7f827edf601a8dab7b80f1f1ebb984ee2fcef9b365881cf4af` | `1b02f7567fbf3e48117a443942710c75101d8569` | `fb293a83dd2664d6da7b7e3a8ed4c9b22e3345c9f5077423a3f5a7f4d99abc5c` |
| `src/core/frames/dsd_dibit.c` | `3dc1412f6ef7732e81b726bb296b75849b7ed8eb61556a5d3e7f877f6ac4aa3b` | `4fb88807bc6b304feb0ae613e9f4e8b9d9087e4c` | `2477efa095dd80a4c1b868da50f1b052661634e0630e168a3492e86cbd68f851` |
| `include/dsd-neo/dsp/symbol.h` | `ae224cad71d8eb4305b86a2d6484cfe2b14d03586856b9d6c97153b9a4f2fbe5` | `206ea103d3fdba5f3009933c86afe8de87308065` | `36f587726c8fdecba7dd56280a800f5b632cf8ccd28e28f0f0193b9ad37b1a31` |
| `include/dsd-neo/core/dibit.h` | `ae102327c4e95f1ca34b8b71c1e3299ad1a86386501196e29f65598db00be0cc` | `a2213fc3ab37f9ac7ed5cafa146766bc391b6406` | `7beade73d3b2fba7c5377c2a6782707c9dd2cfa41969897bb97d0243858379ea` |

## Behavior and limits

- Both checked APIs use explicit per-call completion, not numerical zero, EOF, symbolcnt or soft reliability. Required numerical outputs and optional soft output are initialized to zero on failure.
- The common symbol core retains the old public getSymbol result and commit/cleanup path. Replay helpers now return actual record success. Even a replay EOF placeholder follows the original history/counter commit; it remains unavailable to the checked caller. A missing float FILE is guarded only by the checked API; the legacy undefined null-FILE path is untouched.
- Checked dibit processing uses the same successful slice/ring/capture logic as legacy reads. Unavailable input returns before that logic and does not reuse the previous soft record. The actual datascope counter reset is tested independently of availability.
- No additional replay record value validator is introduced: complete DSDNSYM2 records keep the original dibit masking, soft fields and floating-point interpretation; recognized unsupported or truncated headers fail through the original cleanup.
- The registered RTL discriminator/symbol-output path and finite headless WAV/replay contracts are covered. This study does not certify every backend: the existing Pulse adapter ignores read outcome and can return success without a stream; headful WAV EOF-to-live inherits its old open-input return semantics. Binary replay-to-frontend transition is explicitly unavailable. No broad audio-backend policy is added. The API comment states this limitation.
- The no-radio build exposed an existing unconditional analog-tone call to optional runtime metrics whose declaring header was inside USE_RADIO. The private copy moves only that header outside the guard; no function call/body or radio-path behavior changes.
- No receiver replay, corpus generation, native encoder, hardware call, app build or product promotion is performed by these tests. Fake input hooks are confined to dedicated tests. This is not a thread-safety or duplicate receiver-state claim.

## Actual unit results

Parent built the isolated Release targets in `C:/Users/el_go/AppData/Local/XeraXSDR-build/nxdn-availability-v1-20260925`. All eight dedicated CTest processes passed, including the six acquisition targets below and the separately owned frame/voice targets. This reviewer reopened the status JSON, log and JUnit XML, confirmed eight actual testcases without failure/error and verified the XML hash. No receiver process had been invoked at handoff.

`tests/acquisition.cmake` supplies:

- `xerax_availability_symbol_replay`
- `xerax_availability_symbol_replay_no_radio`
- `xerax_availability_symbol_wav`
- `xerax_availability_symbol_wav_no_radio`
- `xerax_availability_symbol_live`
- `xerax_availability_dibit`

The new tests include original replay/cache/WAV/dibit regression fixtures read-only and keep their assertions active under release NDEBUG. New checks cover actual zero/partial/exact finite input at SPS10/20, direct symbol-rate input, replay record/header boundaries, zero records, replay looping/reopen failure, binary EOF-to-frontend transition, rollover, no stale soft/ring/capture state and an actual datascope reset. No historical test is edited.

| Retained result | SHA256 |
|---|---|
| `build/nxdn-availability-v1-native-unit-status.json` | `0cffbb8550af311d7031d6236efdc128350152ede5543dcf65bf1bb3b8db7678` |
| `build/nxdn-availability-v1-native-unit.log` | `9c23e164b55a0ee36ff77fb55fa317ab5c07abc1012b043e2d037957ce47aad7` |
| `build/nxdn-availability-v1-native-unit-1.xml` | `6e0a45e1f7d09302e478e8ec006d54959e08169aba3f9b362aa80322cb372c2e` |

## Retained implementation failures

Before first compile, static review corrected a test-only non-existent NXDN48 sync identifier to the actual DSD_SYNC_NXDN_POS constant. No native result or gate was changed.

Parent preserved each failed preflight and its correction in `build/nxdn-availability-v1-preflight-notes.txt` and numbered configure/build logs:

1. Original baseline-copy lookup needed Windows-relative path normalization, before copying.
2. Original routing-extra replacement was nonunique; narrowed to the complete wrapper signature, before native build.
3. The RTL unit target was absent because DSD_HAS_RADIO was scoped inside the imported project. The acquisition fragment now obtains that exact variable from dsd-neo_feature_radio SOURCE_DIR; root also imports it explicitly.
4. The generated checked-reader wrapper lacked an external forward declaration under -Werror; parent corrected its observation-only generator.
5. No-radio symbol compilation exposed the inherited optional-metrics header issue described above; the private declaration-only correction retained the failing build log.
6. Dedicated unit linkage missed pthread mutex dependencies in platform/runtime archives; parent added Threads::Threads to the new unit targets. No receiver policy changed.

Build6 and the first dedicated CTest run then passed. All acquisition assertions remained in force; no receiver matrix was used as a smoke test or retry.

## Full normalized acquisition diff

```diff
--- baseline/src/dsp/dsd_symbol.c
+++ candidate/src/dsp/dsd_symbol.c
@@ -59,9 +59,10 @@
 #include "dsd-neo/platform/sockets.h"
 #include "pcm_input_staging.h"
 
+/* Analog tone bookkeeping queries optional metrics even without radio. */
+#include <dsd-neo/runtime/rtl_stream_metrics_hooks.h>
 #ifdef USE_RADIO
 #include <dsd-neo/runtime/rtl_stream_io_hooks.h>
-#include <dsd-neo/runtime/rtl_stream_metrics_hooks.h>
 #endif
 #include <fcntl.h> // IWYU pragma: keep
 
@@ -1857,7 +1858,7 @@
     if (opts->symbolfile == NULL) {
         DSD_FPRINTF(stderr, "Error Opening File %s\n", opts->audio_in_dev);
         *symbol_out = -1.0f;
-        return 1;
+        return 0;
     }
 
     int replay_retry_count = 0;
@@ -1868,7 +1869,7 @@
             opts->symbolfile = NULL;
             dsd_request_shutdown(opts, state);
             *symbol_out = 0.0f;
-            return 1;
+            return 0;
         }
 
         int read_ok = 0;
@@ -1899,23 +1900,23 @@
             if (opts->symbolfile == NULL) {
                 DSD_FPRINTF(stderr, "Error Opening File %s\n", opts->audio_in_dev);
                 *symbol_out = -1.0f;
-                return 1;
+                return 0;
             }
             if (replay_retry_count++ == 0) {
                 continue;
             }
             *symbol_out = 0.0f;
-            return 1;
+            return 0;
         }
         /* Frontend kind on purpose; same reasoning as the PCM end-of-file path above. */
         if (opts->audio_out_type == 0 && dsd_opts_frontend_active(opts)) {
             (void)symbol_open_pulse_input_and_reconfigure_output(opts, state);
             *symbol_out = 0.0f;
-            return 1;
+            return 0;
         }
         dsd_request_shutdown(opts, state);
         *symbol_out = 0.0f;
-        return 1;
+        return 0;
     }
 }
 
@@ -1926,7 +1927,7 @@
     if (read_count != 1) {
         dsd_exitflag_store(1);
         *symbol_out = 0.0f;
-        return 1;
+        return 0;
     }
     if (feof(opts->symbolfile)) {
         dsd_exitflag_store(1);
@@ -2129,14 +2130,18 @@
 }
 #endif
 
-static inline void
+/* A replay placeholder still follows the legacy commit path. Availability is
+ * separate: only a complete record, including an all-zero record, succeeds. */
+static inline int
 symbol_apply_replay_overrides(dsd_opts* opts, dsd_state* state, float* symbol) {
+    int available = 1;
     if (opts->audio_in_type == AUDIO_IN_SYMBOL_BIN) {
-        (void)symbol_process_symbol_bin_input(opts, state, symbol);
+        available = symbol_process_symbol_bin_input(opts, state, symbol);
     }
     if (opts->audio_in_type == AUDIO_IN_SYMBOL_FLT) {
-        (void)symbol_process_symbol_flt_input(opts, symbol);
-    }
+        available = symbol_process_symbol_flt_input(opts, symbol);
+    }
+    return available;
 }
 
 static inline float
@@ -2154,8 +2159,11 @@
     return symbol;
 }
 
-float
-getSymbol(dsd_opts* opts, dsd_state* state, int have_sync) {
+static float
+get_symbol_internal(dsd_opts* opts, dsd_state* state, int have_sync, int* out_available) {
+    if (out_available != NULL) {
+        *out_available = 0;
+    }
     symbol_work_ctx work;
     symbol_work_ctx_init(&work, state);
 
@@ -2166,6 +2174,9 @@
         return 0.0f;
     }
     if (fast_status > 0) {
+        if (out_available != NULL) {
+            *out_available = 1;
+        }
         return work.sample;
     }
     symbol_prepare_span(opts, state, &work, have_sync);
@@ -2179,6 +2190,35 @@
 
     float symbol = symbol_finalize_live_symbol(state, &work);
 
-    symbol_apply_replay_overrides(opts, state, &symbol);
+    int available = symbol_apply_replay_overrides(opts, state, &symbol);
+    if (out_available != NULL) {
+        *out_available = available;
+    }
     return symbol_commit_symbol(opts, state, have_sync, &work, symbol);
 }
+
+float
+getSymbol(dsd_opts* opts, dsd_state* state, int have_sync) {
+    return get_symbol_internal(opts, state, have_sync, NULL);
+}
+
+int
+dsd_get_symbol_checked(dsd_opts* opts, dsd_state* state, int have_sync, float* out_symbol) {
+    if (out_symbol != NULL) {
+        *out_symbol = 0.0f;
+    }
+    if (opts == NULL || state == NULL || out_symbol == NULL) {
+        return 0;
+    }
+    /* The legacy float reader requires an open FILE. Do not dereference a
+     * missing stream or manufacture a record for the checked API. */
+    if (opts->audio_in_type == AUDIO_IN_SYMBOL_FLT && opts->symbolfile == NULL) {
+        return 0;
+    }
+    int available = 0;
+    float symbol = get_symbol_internal(opts, state, have_sync, &available);
+    if (available) {
+        *out_symbol = symbol;
+    }
+    return available;
+}
--- baseline/src/core/frames/dsd_dibit.c
+++ candidate/src/core/frames/dsd_dibit.c
@@ -1008,17 +1008,9 @@
     return dibit;
 }
 
-int
-get_dibit_and_analog_signal(dsd_opts* opts, dsd_state* state, int* out_analog_signal) {
-    if (opts == NULL || state == NULL) {
-        return -1;
-    }
-
-    float symbol;
+static int
+consume_dibit_symbol(dsd_opts* opts, dsd_state* state, float symbol, int* out_analog_signal) {
     int dibit;
-
-    symbol = getSymbol(opts, state, 1);
-
     state->sbuf[state->sidx] = symbol;
 
     if (out_analog_signal != NULL) {
@@ -1041,6 +1033,39 @@
     write_symbol_capture_record(opts, state, dibit, symbol, capture_soft_p);
 
     return dibit;
+}
+
+int
+get_dibit_and_analog_signal(dsd_opts* opts, dsd_state* state, int* out_analog_signal) {
+    if (opts == NULL || state == NULL) {
+        return -1;
+    }
+    return consume_dibit_symbol(opts, state, getSymbol(opts, state, 1), out_analog_signal);
+}
+
+int
+dsd_get_dibit_soft_checked(dsd_opts* opts, dsd_state* state, int* out_dibit, dsd_dibit_soft_t* out_soft) {
+    if (out_dibit != NULL) {
+        *out_dibit = 0;
+    }
+    if (out_soft != NULL) {
+        DSD_MEMSET(out_soft, 0, sizeof(*out_soft));
+    }
+    if (opts == NULL || state == NULL || out_dibit == NULL) {
+        return 0;
+    }
+    float symbol = 0.0f;
+    if (!dsd_get_symbol_checked(opts, state, 1, &symbol)) {
+        return 0;
+    }
+    /* Do not slice an unavailable placeholder, commit it to either ring,
+     * capture it, or inherit the previous real dibit's soft metric. */
+    int dibit = consume_dibit_symbol(opts, state, symbol, NULL);
+    *out_dibit = dibit;
+    if (out_soft != NULL && !read_previous_dibit_soft(state, out_soft)) {
+        fallback_soft_from_dibit(dibit, 255, out_soft);
+    }
+    return 1;
 }
 
 int
--- baseline/include/dsd-neo/dsp/symbol.h
+++ candidate/include/dsd-neo/dsp/symbol.h
@@ -22,6 +22,13 @@
 
 float getSymbol(dsd_opts* opts, dsd_state* state, int have_sync);
 
+/** Return 1 only for a complete live symbol or actual replay record. The
+ * required output is zero on failure; a successfully read zero remains valid.
+ * Uses the same acquisition/cleanup path as getSymbol; no counter inference.
+ * Inherits adapter success semantics: Pulse read outcome and headful WAV
+ * EOF-to-live fallback are not a validated all-backend availability contract. */
+int dsd_get_symbol_checked(dsd_opts* opts, dsd_state* state, int have_sync, float* out_symbol);
+
 /**
  * @brief Forget which matched filter the symbol grid was reading through.
  *
--- baseline/include/dsd-neo/core/dibit.h
+++ candidate/include/dsd-neo/core/dibit.h
@@ -42,6 +42,10 @@
 
 int get_dibit_and_analog_signal(dsd_opts* opts, dsd_state* state, int* out_analog_signal);
 int getDibitSoft(dsd_opts* opts, dsd_state* state, dsd_dibit_soft_t* out_soft);
+/** Return 1 only when a complete symbol was acquired and sliced. out_dibit is
+ * required, out_soft optional; outputs are zero on failure. Unavailable input
+ * does not update slicer rings/capture or return a stale previous soft metric. */
+int dsd_get_dibit_soft_checked(dsd_opts* opts, dsd_state* state, int* out_dibit, dsd_dibit_soft_t* out_soft);
 int getDibitAndSoftSymbol(dsd_opts* opts, dsd_state* state, float* out_soft_symbol);
 void write_symbol_capture_record(dsd_opts* opts, dsd_state* state, int dibit, float symbol,
                                  const dsd_dibit_soft_t* soft);
```
