// SPDX-License-Identifier: GPL-3.0-or-later
/* Explicit no-voice study boundary. Real sample, sync, frame, whitening,
 * channel/FEC/CRC and confirmation code remain linked. Semantic dispatch,
 * vocoding, file output and unused privacy side effects are capture sinks.
 * No sink reports CRC evidence or changes frame confirmation. */
#include "side_effect_sinks.h"
#include <dsd-neo/core/opts.h>
#include <dsd-neo/core/state.h>
#include <dsd-neo/core/events.h>
#include <dsd-neo/core/file_io.h>
#include <dsd-neo/protocol/nxdn/nxdn_deperm.h>
#include <dsd-neo/protocol/nxdn/nxdn_voice.h>
#include <dsd-neo/protocol/nxdn/nxdn_lfsr.h>
#include <dsd-neo/protocol/nxdn/nxdn_alias_decode.h>
#include <string.h>

xerax_side_effect_observations xerax_effects;
void NXDN_SACCH_Full_decode(dsd_opts* opts, dsd_state* state) {
    (void)opts; (void)state; xerax_effects.other_side_effects++;
}
void NXDN_decode_scch(dsd_opts* opts, dsd_state* state, const uint8_t* message, uint8_t direction) {
    (void)opts; (void)state; (void)message; (void)direction; xerax_effects.other_side_effects++;
}
void nxdn_alias_reset(dsd_state* state) { (void)state; xerax_effects.other_side_effects++; }
void rotate_symbol_out_file(dsd_opts* opts, dsd_state* state) {
    (void)opts; (void)state; xerax_effects.other_side_effects++;
}
void NXDN_Elements_Content_decode(dsd_opts* opts, dsd_state* state, const uint8_t* bits, size_t count) {
    (void)opts; (void)state;
    if (!bits || count > 512U || xerax_effects.count >= 64U) { xerax_effects.errors++; return; }
    xerax_content_observation* observation = &xerax_effects.content[xerax_effects.count++];
    observation->length = count;
    for (size_t n = 0; n < count; n++) {
        if (bits[n] > 1U) { xerax_effects.errors++; return; }
        observation->bits[n] = (char)('0' + bits[n]);
    }
    observation->bits[count] = '\0';
}
void nxdn_voice(dsd_opts* opts, dsd_state* state, int voice, uint8_t dibits[182], const uint8_t* reliability) {
    (void)opts; (void)state; (void)voice; (void)dibits; (void)reliability;
    xerax_effects.voice_requests++;
}
void LFSRN(const char* input, char* output, dsd_state* state) {
    (void)input; (void)state; memset(output, 0, 49U); xerax_effects.other_side_effects++;
}
void LFSR128n(dsd_state* state) { (void)state; xerax_effects.other_side_effects++; }
void openMbeOutFile(dsd_opts* opts, dsd_state* state) {
    (void)opts; (void)state; xerax_effects.other_side_effects++;
}
void closeMbeOutFile(dsd_opts* opts, dsd_state* state) {
    (void)opts; (void)state; xerax_effects.other_side_effects++;
}
int dsd_event_enrich_alias(dsd_state* state, uint8_t slot, uint64_t epoch, const char* alias) {
    (void)state; (void)slot; (void)epoch; (void)alias; xerax_effects.other_side_effects++; return 0;
}
