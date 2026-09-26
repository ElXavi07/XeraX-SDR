// SPDX-License-Identifier: GPL-3.0-or-later

#ifndef DSD_NEO_SRC_PROTOCOL_NXDN_NXDN_TEST_SUPPORT_H_
#define DSD_NEO_SRC_PROTOCOL_NXDN_NXDN_TEST_SUPPORT_H_

#if defined(DSD_NEO_TEST_HOOKS) && defined(XERAX_NXDN_FRAME_RESEARCH)
#include <dsd-neo/core/state_fwd.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    DSD_NXDN_TEST_CHANNEL_SACCH = 1,
    DSD_NXDN_TEST_CHANNEL_FACCH1 = 2
} dsd_nxdn_test_channel;

typedef struct {
    dsd_nxdn_test_channel channel;
    /* Original FACCH routing argument: 0=single, 1=A, 2=B; SACCH uses 0. */
    uint8_t frame_part;
    uint16_t computed_crc;
    uint16_t received_crc;
    int soft_crc_pass;
    int hard_fallback_used;
    size_t info_bit_count;
    /* Final decoded information bits only: 26 SACCH or 80 FACCH1 bits.
     * The unused SACCH suffix is zero, and no CRC/tail bits are included. */
    uint8_t info_bits[80];
} dsd_nxdn_test_crc_event;

/* Single-decoder-thread research seam at the final, post-fallback CRC gate,
 * before confirmation, duplicate suppression, or content dispatch. Equality
 * of computed_crc and received_crc is the actual final channel verdict.
 * Bits are copied synchronously into the event before calling the observer.
 * The event/state pointers are borrowed only during this call. Observers must
 * copy data they retain and must not mutate state or reenter decoder/setter
 * operations. There is no concurrent setter/callback synchronization. */
typedef void (*dsd_nxdn_test_crc_observer)(void* user, const dsd_state* state,
                                         const dsd_nxdn_test_crc_event* event);
/* A null observer also clears user; caller owns user storage/lifetime. */
void dsd_nxdn_test_set_crc_observer(dsd_nxdn_test_crc_observer observer, void* user);

#ifdef __cplusplus
}
#endif
#endif

#endif
