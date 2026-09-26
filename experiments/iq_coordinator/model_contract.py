"""Bounded abstract ownership exploration, NOT a C++ memory-model proof.

Events are whole declared handoffs; no compiler, weak-memory, clock or RF
behavior is simulated. Three intentionally broken rules must produce witnesses.
The executable contract suite independently tests the actual implementation.
"""
from collections import deque
from dataclasses import dataclass, replace
import json


@dataclass(frozen=True)
class State:
    phase: str = 'Idle'
    issued: int = 0
    acknowledged: int = 0
    closing: bool = False
    cancelled: bool = False
    expired: bool = False
    owner: str = 'none'  # none, owner, mailbox, consumer
    pins: int = 0
    readable: bool = False
    reply: str = ''


def violation(s):
    if s.pins not in (0, 1):
        return 'pin cap'
    if (s.owner == 'none') != (s.pins == 0):
        return 'pin ownership mismatch'
    if s.readable and (s.owner != 'consumer' or s.pins != 1):
        return 'revoked readable payload'
    if s.issued - s.acknowledged not in (0, 1):
        return 'more than one request credit'
    if s.phase == 'Idle' and (s.owner != 'none' or s.issued != s.acknowledged):
        return 'reused slot before acknowledgement'
    if s.phase == 'Closed' and s.owner not in ('none', 'consumer'):
        return 'closed with undrained owner/reply'
    if s.phase == 'Closed' and s.issued != s.acknowledged:
        return 'closed with unacknowledged mailbox work'
    if s.owner == 'owner' and s.phase != 'Granted':
        return 'owner lease escaped grant phase'
    if s.owner == 'mailbox' and s.phase != 'Ready':
        return 'mailbox lease escaped reply phase'
    return None


def rejection(s):
    # Boundary checks only, not actual elapsed-time deadline guarantees.
    if s.closing:
        return 'Closed'
    if s.cancelled:
        return 'Cancelled'
    if s.expired:
        return 'Expired'
    return ''


def transitions(s, max_requests, mutant):
    out = []
    def add(label, **fields):
        out.append((label, replace(s, **fields)))

    if not s.closing:
        add('client.close', closing=True)
    if s.phase == 'Idle':
        if s.closing:
            add('owner.ack_close', phase='Closed')
        elif s.issued < max_requests:
            add('client.submit', phase='Pending', issued=s.issued + 1,
                cancelled=False, expired=False, reply='')
    if s.phase in ('Pending', 'Acquired', 'Granted', 'Ready'):
        if not s.cancelled:
            add('client.cancel', cancelled=True)
        if not s.expired:
            add('logical.deadline_boundary', expired=True)
    if s.phase == 'Pending':
        add('owner.acquire', phase='Acquired')
    if s.phase == 'Acquired':
        error = rejection(s)
        add('owner.grant', phase='Granted', reply=error or 'Ok',
            owner='none' if error else 'owner', pins=0 if error else 1)
        # Underlying history may reject, independently of mailbox outcomes.
        if not error:
            add('owner.source_reject', phase='Granted', reply='SourceRejected')
    if s.phase == 'Granted':
        error = rejection(s)
        success = not error and s.reply == 'Ok'
        add('owner.publish', phase='Ready', reply=error or s.reply,
            owner='mailbox' if success else 'none', pins=1 if success else 0)
    if s.phase == 'Ready':
        error = rejection(s)
        success = not error and s.reply == 'Ok'
        add('client.take', phase='Held' if success else 'Consumed',
            reply=error or s.reply, owner='consumer' if success else 'none',
            pins=1 if success else 0, readable=success)
        add('client.discard', phase='Consumed', owner='none', pins=0)
    if s.phase == 'Held':
        add('consumer.release', phase='Consumed', owner='none', pins=0, readable=False)
        if s.closing:
            # Mailbox quiescence may precede final payload reclamation.
            add('owner.ack_close_held', phase='Closed', acknowledged=s.issued)
    if s.phase == 'Consumed':
        add('owner.ack_release', phase='Closed' if s.closing else 'Idle',
            acknowledged=s.issued)
    if s.phase == 'Closed' and s.readable:
        add('consumer.release_after_shutdown', owner='none', pins=0, readable=False)

    if mutant == 'reuse_unclaimed' and s.phase == 'Ready':
        add('BROKEN.reuse_unclaimed', phase='Idle')
    if mutant == 'revoke_held' and s.phase == 'Held':
        add('BROKEN.cancel_revokes_pointer', pins=0, owner='none', cancelled=True)
    if mutant == 'close_before_drain' and s.phase == 'Granted':
        add('BROKEN.ack_close_before_drain', phase='Closed', closing=True,
            acknowledged=s.issued)
    return out


def explore(max_requests=2, mutant=None):
    if max_requests not in (1, 2, 3):
        raise ValueError('Bounded explorer supports one to three requests')
    if mutant not in (None, 'reuse_unclaimed', 'revoke_held', 'close_before_drain'):
        raise ValueError('Unknown negative control')
    initial = State()
    parents = {initial: None}
    queue = deque([initial])
    edges = terminals = 0
    def witness(state):
        path = []
        while parents[state] is not None:
            previous, label = parents[state]
            path.append(label)
            state = previous
        return list(reversed(path))
    while queue:
        s = queue.popleft()
        error = violation(s)
        choices = transitions(s, max_requests, mutant)
        if error:
            return {'ok': False, 'error': error, 'witness': witness(s),
                    'states': len(parents), 'transitions': edges}
        if not choices:
            if s.phase != 'Closed' or s.owner != 'none':
                return {'ok': False, 'error': 'nonterminal dead end', 'witness': witness(s)}
            terminals += 1
        for label, next_state in choices:
            edges += 1
            if next_state not in parents:
                parents[next_state] = (s, label)
                queue.append(next_state)
    return {'ok': True, 'states': len(parents), 'transitions': edges,
            'fully_released_terminal_states': terminals,
            'request_bound': max_requests,
            'scope': 'abstract boundary ownership only; not implementation or weak-memory proof'}


if __name__ == '__main__':
    print(json.dumps({'normal': explore(), 'negative_controls': {
        name: explore(mutant=name) for name in
        ('reuse_unclaimed', 'revoke_held', 'close_before_drain')}}, indent=2))
