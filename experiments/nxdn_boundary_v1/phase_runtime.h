// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef XERAX_BOUNDARY_RUNTIME_H
#define XERAX_BOUNDARY_RUNTIME_H
#include "phase_policy.h"
#include <dsd-neo/core/opts_fwd.h>
#include <dsd-neo/core/state_fwd.h>
int nxdn_boundary_runtime_open(const char* path);
int nxdn_boundary_runtime_close(void);
void nxdn_boundary_runtime_reset(const char* reason);
nxdn_boundary_v1_context nxdn_boundary_runtime_context(const dsd_opts* opts, const dsd_state* state);
void nxdn_boundary_runtime_frame(const nxdn_boundary_v1_context* begin,
                                 const dsd_opts* opts, const dsd_state* state, int result);
int nxdn_boundary_runtime_allow(const dsd_opts* opts, const dsd_state* state, const char* pattern);
#endif
