"""Abstract reservation/weak-retirement model, not allocator or C++ proof.

Integer units stand for measured allocator requests plus declared reservations.
Private C++ allocation steps and scheduler fairness are not simulated.
"""
from collections import deque
from dataclasses import dataclass, replace
import json

LEDGER = 1
DOMAIN = 3


@dataclass(frozen=True)
class Domain:
    stage: str = 'Reserved'
    facade: bool = False
    reply: bool = False
    weak: int = 0


@dataclass(frozen=True)
class State:
    budget_facade: bool = True
    ledger_alive: bool = True
    charged: int = LEDGER
    domains: tuple = ()


def violation(s, cap):
    if not 0 <= s.charged <= cap:
        return 'reservation outside cap'
    physical = (LEDGER if s.ledger_alive else 0) + DOMAIN * sum(
        d.stage in ('Allocated', 'Retired') for d in s.domains)
    if physical > s.charged:
        return 'live allocation lost its reservation'
    if not s.ledger_alive and any(d.stage != 'Gone' for d in s.domains):
        return 'allocator outlived ledger'
    for d in s.domains:
        if d.stage in ('Retired', 'FreedPending', 'Gone') and (d.facade or d.reply):
            return 'retired while a strong owner remains'
        if d.stage in ('FreedPending', 'Gone') and d.weak:
            return 'freed before final weak identity'
    return None


def transitions(s, cap, bound, mutant):
    out = []
    def add(label, **fields): out.append((label, replace(s, **fields)))
    def update(index, label, domain, **fields):
        items = list(s.domains)
        items[index] = domain
        add(f'{index}:{label}', domains=tuple(items), **fields)
    if s.budget_facade:
        add('destroy_budget_facade', budget_facade=False)
        if len(s.domains) < bound and s.charged + DOMAIN <= cap:
            add('reserve_before_allocate', charged=s.charged + DOMAIN,
                domains=s.domains + (Domain(),))
            if mutant == 'split_admission':
                add('BROKEN.check_without_reserving', domains=s.domains + (Domain(stage='Unreserved'),))
    if not s.budget_facade and s.ledger_alive and all(d.stage == 'Gone' for d in s.domains):
        add('free_ledger_after_allocators', ledger_alive=False, charged=s.charged - LEDGER)
    for index, d in enumerate(s.domains):
        if d.stage in ('Reserved', 'Unreserved'):
            delta = DOMAIN if d.stage == 'Unreserved' else 0
            update(index, 'allocate_success', Domain(stage='Allocated', facade=True), charged=s.charged + delta)
            update(index, 'allocation_failure_rollback', Domain(stage='Gone'),
                   charged=s.charged - (DOMAIN if d.stage == 'Reserved' else 0))
        if d.stage == 'Allocated':
            if d.facade and not d.reply:
                update(index, 'take_reply', replace(d, reply=True))
            if d.facade:
                update(index, 'destroy_mailbox', replace(d, facade=False,
                    stage='Allocated' if d.reply else 'Retired'))
            if d.reply:
                update(index, 'release_reply', replace(d, reply=False,
                    stage='Allocated' if d.facade else 'Retired'))
        if d.weak < 2 and (d.facade or d.reply or d.weak):
            update(index, 'retain_ticket_identity', replace(d, weak=d.weak + 1))
        if d.weak:
            update(index, 'release_ticket_identity', replace(d, weak=d.weak - 1))
        if d.stage == 'Retired' and d.weak == 0:
            # Preserve charge while physical deallocation is in progress.
            update(index, 'allocator_frees_storage', replace(d, stage='FreedPending'))
        if d.stage == 'FreedPending':
            update(index, 'allocator_releases_charge', replace(d, stage='Gone'), charged=s.charged - DOMAIN)
        if mutant == 'release_at_object_destruction' and d.stage == 'Retired' and d.weak:
            update(index, 'BROKEN.release_while_weak_storage_remains', d, charged=s.charged - DOMAIN)
        if mutant == 'destroy_ledger_with_facade' and not s.budget_facade and s.ledger_alive:
            add('BROKEN.free_ledger_with_live_allocator', ledger_alive=False, charged=s.charged - LEDGER)
    return out


def explore(bound=2, cap=LEDGER + DOMAIN, mutant=None):
    if bound not in (1, 2, 3) or cap not in (LEDGER + DOMAIN, LEDGER + 2 * DOMAIN):
        raise ValueError('Unsupported finite exploration profile')
    if mutant not in (None, 'split_admission', 'release_at_object_destruction', 'destroy_ledger_with_facade'):
        raise ValueError('Unknown negative control')
    initial = State()
    parents = {initial: None}
    queue = deque([initial])
    edges = terminals = peak = 0
    while queue:
        state = queue.popleft()
        error = violation(state, cap)
        if error:
            trace, cursor = [], state
            while parents[cursor] is not None:
                previous, action = parents[cursor]
                trace.append(action)
                cursor = previous
            return {'ok': False, 'error': error, 'witness': list(reversed(trace)),
                    'states': len(parents), 'transitions': edges}
        peak = max(peak, state.charged)
        choices = transitions(state, cap, bound, mutant)
        if not choices:
            if state.ledger_alive or state.charged:
                return {'ok': False, 'error': 'terminal charge leak'}
            terminals += 1
        for action, next_state in choices:
            edges += 1
            if next_state not in parents:
                parents[next_state] = state, action
                queue.append(next_state)
    return {'ok': True, 'states': len(parents), 'transitions': edges,
            'fully_released_terminal_states': terminals, 'peak_reserved_units': peak,
            'capacity_units': cap, 'domain_attempt_bound': bound,
            'scope': 'abstract allocator lifetime boundaries only; not C++ implementation proof'}


if __name__ == '__main__':
    print(json.dumps({'normal': [explore(2), explore(3, 7)], 'negative_controls': {
        name: explore(mutant=name) for name in
        ('split_admission', 'release_at_object_destruction', 'destroy_ledger_with_facade')}}, indent=2))
