"""Persistent QQ intentions shared by heartbeat and the public-only social worker."""
from __future__ import annotations

from contextlib import closing
import hashlib
import json
import time
import uuid


def allowed_actions(options):
    actions = []
    if options['ai_qzone'] and options['auto_qzone']:
        actions.append('post')
    if options['ai_qzone'] and options['auto_qzone_reply']:
        actions.append('comments')
    if options['ai_profile'] and options['auto_profile']:
        actions.extend(('profile', 'avatar', 'status'))
    return actions


def public_experiences(database):
    """Only source-labelled public page facts, never chat, screens or reflections."""
    from urllib.parse import urlsplit
    import ipaddress
    from tool_context import source_url
    result, seen = [], set()
    with closing(database._connect()) as con:
        rows = con.execute("SELECT id,created_at,payload FROM companion_events WHERE kind IN "
                           "('experience','discovery') ORDER BY id DESC LIMIT 30").fetchall()
    for row in rows:
        try:
            payload = json.loads(row['payload'])
        except (ValueError, TypeError):
            continue
        if not isinstance(payload, dict):
            continue
        for receipt in payload.get('receipts', []):
            if not isinstance(receipt, dict) or receipt.get('status') != 'success' or receipt.get('tool') not in {
                    'read_webpage', 'browse_webpage', 'watch_video'}:
                continue
            facts = receipt.get('facts') or {}
            url = source_url(facts.get('url', ''))
            host = urlsplit(url).hostname or ''
            # Addresses to private services and authenticated account pages are
            # not public material, even if they were read successfully.
            if '.' not in host or host.endswith(('.local', '.localhost', '.internal')):
                continue
            try:
                if not ipaddress.ip_address(host).is_global:
                    continue
            except ValueError:
                pass
            path = urlsplit(url).path.lower()
            if any(word in path for word in ('account', 'settings', 'message', 'inbox', 'private', 'login', 'admin')):
                continue
            if not url or url in seen:
                continue
            seen.add(url)
            result.append({'id': str(row['id']), 'at': row['created_at'], 'title': str(facts.get('title') or '')[:160],
                           'url': url, 'scope': receipt.get('scope'),
                           'note': '只证明当时实际读取过该页面/抽样片段；标题不能代替正文。'})
            if len(result) == 6:
                return result
    return result


def attention_signature(database, service):
    material = public_experiences(database)
    from agency import state
    own = state(database)
    # Finishing a QQ action must not wake itself and override its chosen rest.
    interests = {k: own.get(k) for k in ('interests', 'mood')}
    return hashlib.sha256(json.dumps([material, interests], sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def enqueue(service, action, cancelled=lambda: False):
    if action not in allowed_actions(service.snapshot()[0]):
        return {'error': '这项QQ自主功能已关闭，未安排。'}
    observed = service.perform('qq_get_account', {}, origin='autonomous', cancelled=cancelled)
    if not observed.get('confirmed'):
        return observed
    account = service.snapshot()[1].get('user_id')
    with service.lock:
        if cancelled() or service.closed or action not in allowed_actions(service.options):
            return {'cancelled': True}
        requests = list(service.schedule.get('social_requests') or [])
        existing = next((r for r in requests if r.get('account') == account and r.get('action') == action
                         and r.get('status') == 'pending'), None)
        if existing:
            return {'queued': True, 'request_id': existing['id'], 'duplicate_prevented': True,
                    'note': '同一打算已在等待，尚未执行。'}
        request = {'id': uuid.uuid4().hex, 'action': action, 'account': account, 'at': time.time(), 'status': 'pending'}
        service.schedule['social_requests'] = (requests + [request])[-20:]
        service._save()
    service.social_attention.emit()
    return {'queued': True, 'request_id': request['id'], 'note': '打算已保存；由QQ自主回合核实并执行，尚未修改或发布。'}


def pending_request(service, account):
    with service.lock:
        # A request is bound to the account seen when it was made. It never
        # migrates to a different QR login or replays after an uncertain write.
        return next((dict(r) for r in service.schedule.get('social_requests', [])
                     if r.get('account') == account and r.get('status') == 'pending'
                     and time.time()-r.get('at', 0) < 86400), None)


def finish_request(service, identity, status):
    with service.lock:
        for row in service.schedule.get('social_requests', []):
            if row.get('id') == identity:
                row['status'] = status
        service._save()


def recover_requests(service):
    with service.lock:
        changed = False
        for row in service.schedule.get('social_requests', []):
            if row.get('status') == 'running':
                row['status'] = 'unknown'
                changed = True
        if changed:
            service._save()
