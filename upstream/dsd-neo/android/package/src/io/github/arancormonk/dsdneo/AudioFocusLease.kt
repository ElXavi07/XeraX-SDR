// SPDX-License-Identifier: GPL-3.0-or-later
package io.github.arancormonk.dsdneo

/** Main-thread focus ownership. Ignore callbacks from an abandoned request. */
class AudioFocusLease {
    private var generation = 0L
    @Volatile var granted = false; private set
    @Volatile var blocked = false; private set
    fun begin(): Long {
        generation++; granted = false; blocked = true
        return generation
    }
    fun change(token: Long, gain: Boolean): Boolean {
        if (token != generation) return false
        granted = gain; blocked = !gain
        return true
    }
    fun abandon() {
        generation++; granted = false; blocked = false
    }
}
