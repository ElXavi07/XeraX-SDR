// SPDX-License-Identifier: GPL-3.0-or-later
import io.github.arancormonk.dsdneo.AudioFocusLease
fun main() {
    val lease = AudioFocusLease()
    check(!lease.blocked && !lease.granted)
    val initial = lease.begin()
    check(lease.blocked && !lease.granted)
    check(lease.change(initial, true) && lease.granted)
    check(lease.change(initial, false) && lease.blocked)
    check(lease.change(initial, true) && !lease.blocked)
    val retry = lease.begin()
    check(!lease.change(initial, true) && lease.blocked)
    check(lease.change(retry, true) && lease.granted)
    check(!lease.change(initial, false) && lease.granted)
    lease.abandon()
    check(!lease.change(retry, false) && !lease.blocked && !lease.granted)
    val denied = lease.begin()
    check(lease.change(denied, false) && lease.blocked)
    val recovery = lease.begin()
    check(lease.change(recovery, true) && lease.granted)
    check(!lease.change(denied, false) && lease.granted)
    println("Audio focus: grant, delayed grant, temporary loss, retry, stale callbacks and abandonment passed")
}
