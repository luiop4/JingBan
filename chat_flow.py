"""Short messages during real actions and persistent conversational hand-offs."""
from __future__ import annotations

import base64
from contextlib import closing
from datetime import datetime
import hashlib
import json
import re
import threading
import time
import uuid


def flow_prompt(tools_available=True):
    text = ('\n聊天节奏：日常像发即时消息，只说此刻想说的一两句，讲到点上就停，给对方接话空间。'
            '先辨别对方这句是在逗你、接梗、随口一说、认真交代还是难受，再决定怎么接；'
            '语气词、乱敲的字和熟悉后的轻微互损，不当成需要解释的知识问题，也不自动安慰或训人。'
            '没有明确技术上下文的一串数字或缩写，先按紧邻话题理解，实在不明白就几个字问清，'
            '不要擅自补出某种专业问题开始科普；没有真的调用搜索工具，不写“查了资料”“查了一下”。'
            '熟悉时可以嘴硬、回一个轻巧的梗、嫌弃一下再翻篇；力度顺着当前关系，不主动恶意羞辱。'
            '认真或难受时收住玩笑，技术问题仍然认真处理。'
            '有时候几个字、一个反问或一张贴切表情就够，不必每条都凑满20至60字。'
            '学的是接话的分寸，不复读同一句梗；不要把“碳基生物”“本鲸”等词塞进每条回复。'
            '不把想法、计划、执行、感想、总结全挤成一大段，不每次列点或最后再追问一个问题。'
            '情绪自然接住，不固定三段式，不轮播台词，也不为了显得像人机械拆成多条。'
            '亲近感来自接住对方的话、自己的明确偏好和眼前细节；不要每条都喊称呼、强调人设或插科打诨。'
            '普通聊天不说“排上了、等跑起来、稍后汇报、本轮状态”等后台流程话；'
            '用户问进度或执行失败时才清楚交代实际状态。不要刻意造口误再括号纠正，也不要套固定卖萌句。'
            '对方指出卡住、暂停或出错时，直接接这个具体问题，先查能查的状态并处理；'
            '不要把对方的观察当作新命令，不背诵内部规则，不用一段自责再一段免责声明回应。'
            '不为凑人味伪造情绪、口癖或经历，允许有自己的简短偏好，也允许一句话就结束。'
            '判断能不能做时先看本轮实际工具：专用视频工具只覆盖B站，不等于浏览器和电脑只能访问B站。'
            '其他网站可在已授权的电脑工具范围尝试，必须实际打开、观察后才谈看到的内容；'
            '没有对应工具、登录受限或无法读取画面时如实说，不凭空承诺能刷、能听或支持所有平台。'
            '用户要解释、教程、代码、报告时按问题充分展开，不截断必要信息。')
    text += ('有真实表情工具时可以选贴切的图接话，文字和表情不重复解释；想看清表情再inspect_qq_sticker。'
             'send_sticker实际成功后，闲聊可以只用这张图回应，最终写[[sent]]，不用补“给你发了张表情”。'
             '未成功发送、没有工具或用户交代的任务尚未处理时，不能拿[[sent]]交差。') if tools_available else ''
    return text + (('有行动时可用 chat_message 当下说一句，真正操作后再接着聊；只分享实际看到的图片或结果。'
            '后续行动需要对方选择、评价或回应时，使用 chat_message 并设 wait_for_reply=true，说完就真的停下来等，不能自问自答。'
            '普通已授权的操作直接做，不为每个动作索要许可。不要预写不存在的对方回复。'
            'chat_message 已经发送的内容不再重复到最终正文；没有新话要说时只输出 [[sent]]。'
            '工具调用时正文留空。没有使用 chat_message 时直接自然回复，不要输出 [[sent]]。') if tools_available else '')


def pending(database, conversation):
    keys = database.context_keys(conversation)
    with closing(database._connect()) as connection:
        row = connection.execute('SELECT * FROM interaction_waits WHERE conversation_key IN ('+
            ','.join('?' for _ in keys)+') ORDER BY message_id DESC LIMIT 1', list(keys)).fetchone()
    return dict(row) if row else None


def answer_wait(database, conversation, message_id):
    """A new human message is an answer, never an automatic approval of an action."""
    value = pending(database, conversation)
    if not value or message_id <= value['message_id']:
        return None
    with closing(database._connect()) as connection, connection:
        connection.execute('DELETE FROM interaction_waits WHERE conversation_key=? AND message_id=?',
                           (value['conversation_key'], value['message_id']))
        # Only the local identity (or its explicitly bound owner) resumes local plans.
        if value['conversation_key'] in database.context_keys('local'):
            row = connection.execute('SELECT payload FROM agency_state WHERE id=1').fetchone()
            state = json.loads(row[0]) if row else {}
            if not isinstance(state, dict):
                state = {}
            if state.get('status') == 'waiting':
                reply = database.get_message(message_id)
                declined = bool(reply and re.match(r'^\s*(?:不行|不可以|不能|不要|先别|不买|别买|算了|停止|暂停)', reply['content']))
                state.update(status='blocked' if declined else 'planned', resume_at='', plan_revision=uuid.uuid4().hex)
                if declined:
                    state['next_step'] = ''
                connection.execute('UPDATE agency_state SET payload=? WHERE id=1',
                                   (json.dumps(state, ensure_ascii=False),))
    return {**value, 'answer_message_id': message_id}


def wait_for_reply(database, job, message_id, question):
    from agency import state
    value = state(database)
    local_identity = job['conversation_key'] in database.context_keys('local')
    with closing(database._connect()) as connection, connection:
        connection.execute('INSERT INTO interaction_waits VALUES(?,?,?,?,?,?) '
            'ON CONFLICT(conversation_key) DO UPDATE SET message_id=excluded.message_id,question=excluded.question,'
            'goal=excluded.goal,next_step=excluded.next_step,created_at=excluded.created_at',
            (job['conversation_key'], message_id, question,
             value['goal'] if local_identity else '',
             value['next_step'] if local_identity else '', database._now()))
        if local_identity:
            value.update(status='waiting', resume_at='', plan_revision=uuid.uuid4().hex)
            connection.execute('INSERT INTO agency_state VALUES(1,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',
                               (json.dumps(value, ensure_ascii=False),))


def install(toolkit, worker, service, account_authorized=False):
    from chat_tools import function
    toolkit.definitions.append(function('chat_message',
        '行动过程中现在就发一条自然短消息。share_screen 可附刚刚实际观察的屏幕或其中一块；'
        'wait_for_reply=true 会发完并结束当前执行，等真实用户新消息。不是模拟双方对话。', {
            'text': {'type': 'string', 'description': '此刻要说的话，日常简短；不能捏造操作或写用户回复'},
            'wait_for_reply': {'type': 'boolean'},
            'share_screen': {'type': 'boolean'},
            'video_id': {'type': 'string', 'description': '可选，鲸鱼心跳真实观看事件中的 video_id，附上那次实际截图；与 share_screen 二选一。'},
            'image_title': {'type': 'string'},
            'crop': {'type': 'object', 'properties': {
                'x': {'type': 'integer'}, 'y': {'type': 'integer'},
                'width': {'type': 'integer'}, 'height': {'type': 'integer'}},
                'required': ['x', 'y', 'width', 'height'],
                'description': '可选，按最近 observe_desktop 截图像素裁取实际想分享的区域'},
        }, ['text']))
    worker.flow_messages = []
    worker.waiting_for_reply = False
    worker.flow_attempts = {}

    def request(stage, **values):
        data = {'stage': stage, 'worker': worker, 'ready': threading.Event(), 'result': {}, **values}
        worker.interaction_requested.emit(data)
        deadline = time.monotonic()+20
        while not data['ready'].wait(0.1):
            if worker.isInterruptionRequested() or time.monotonic() >= deadline:
                data['cancelled'] = True
                return {'error': '没有取得聊天消息回执，请勿重复发送。', 'outcome_unknown': True}
        return data['result']

    def permitted():
        if worker.isInterruptionRequested():
            return False
        peer = getattr(worker, 'qq_peer', '')
        if not peer:
            return not worker.proactive or getattr(worker, 'agency_permitted', lambda: True)()
        if service.closed:
            return False
        options = service.snapshot()[0]
        return (service.reply_enabled and peer in service.reply_allowlist or
                account_authorized and peer in options['account_allowlist'])

    def send(args):
        if not permitted():
            return {'cancelled': True}
        text = str(args.get('text') or '').strip()
        if not text or len(text) > 2000 or re.search(r'\[\[(?:sent|silent|voice|quote|/?character_aside)', text):
            return {'error': '请提供此刻自然要说的话；长报告用最终正文，不发送内部标记。'}
        if worker.api_settings.get('interaction_mode', 'normal') == 'normal' and len(text) > 120:
            return {'error': '这条日常消息太长，缩成一两句再发；详细说明可以放在最终答复。尚未发送。'}
        problem = toolkit.evidence.violation(text, visual_input=toolkit.current_desktop_input,
            image_count=int(bool(args.get('share_screen') or args.get('video_id'))))
        if problem:
            return {'error': problem}
        signature = hashlib.sha256(json.dumps(args, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        if signature in worker.flow_attempts:
            return {**worker.flow_attempts[signature], 'duplicate_prevented': True}
        image = None
        if args.get('video_id') and args.get('share_screen'):
            return {'error': '一次选择分享视频截图或当前屏幕。'}
        if args.get('video_id'):
            capture = request('video', args=args)
            if capture.get('error') or capture.get('cancelled'):
                return capture
            image = capture['image']
        if args.get('share_screen'):
            capture = request('capture', args=args)
            if capture.get('error') or capture.get('cancelled'):
                return capture
            image = capture['image']
        delivery = {'confirmed': True}
        peer = getattr(worker, 'qq_peer', '')
        if peer:
            bridge = service.bridge
            if bridge is None or not permitted():
                return {'error': 'QQ桥接不可用或权限已撤销，未发送。'}
            from qq_delivery import split_reply
            messages = [[{'type': 'text', 'data': {'text': part}}] for part in split_reply(text,
                compact=worker.api_settings.get('interaction_mode', 'normal') == 'normal')]
            if image:
                path = toolkit.root / image['path']
                messages.append([{'type': 'image', 'data': {'file':
                    'base64://'+base64.b64encode(path.read_bytes()).decode('ascii')}}])
            # Save the question before sending: a fast human answer must be
            # ordered after the question, even if the bridge ack arrives later.
            prepared = request('deliver', text=text, image=image, delivery={'confirmed': False, 'pending': True},
                               wait=bool(args.get('wait_for_reply')))
            if not prepared.get('message_id'):
                return prepared
            worker.flow_messages.append(prepared['message_id'])
            worker.waiting_for_reply = bool(args.get('wait_for_reply'))
            worker.flow_attempts[signature] = {'message_id': prepared['message_id'],
                'error': '发送结果未确认，不自动重发。', 'outcome_unknown': True}
            try:
                delivery = bridge.send_bundle_wait(peer, messages, permitted, worker.isInterruptionRequested)
            except Exception as error:
                delivery = {'confirmed': False, 'error': str(error)[:200],
                            'outcome_unknown': bool(getattr(error, 'outcome_unknown', True))}
            request('receipt', message_id=prepared['message_id'], delivery=delivery)
            result = {**prepared, 'confirmed': bool(delivery.get('confirmed')),
                      'image_shared': bool(image and delivery.get('confirmed'))}
            if not delivery.get('confirmed'):
                result.update(error=delivery.get('error') or 'QQ发送结果未确认，请勿重发或声称已发送。',
                              outcome_unknown=bool(delivery.get('outcome_unknown')))
            worker.flow_attempts[signature] = result
            return result
        if (not delivery.get('confirmed') and not delivery.get('outcome_unknown')
                and not delivery.get('sent_parts')):
            result = {'error': delivery.get('error', '消息未发出。')}
        else:
            result = request('deliver', text=text, image=image, delivery=delivery,
                             wait=bool(args.get('wait_for_reply')))
            if result.get('message_id'):
                worker.flow_messages.append(result['message_id'])
                if args.get('wait_for_reply'):
                    worker.waiting_for_reply = True
            if not delivery.get('confirmed'):
                result.update(error='QQ发送结果未确认，请勿重发或声称已发送。', outcome_unknown=True)
        worker.flow_attempts[signature] = result
        return result
    toolkit.chat_message = send


def capture_view(window, worker, args):
    """Persist only a real, freshly observed image. No fabricated product cards."""
    from PySide6.QtGui import QImage
    from companionship import foreground_state
    snapshot = worker.desktop_snapshot
    frame = getattr(worker, 'desktop_frame', None)
    if not getattr(worker, 'permission_check', lambda: False)():
        return {'error': '电脑观察权限未开启，未分享画面。'}
    if not snapshot or not frame or time.monotonic()-snapshot.get('captured_at', 0) > 30:
        return {'error': '先 observe_desktop 看实际画面，再分享这张图。'}
    current = foreground_state(True)
    if not current.get('available') or any(current.get(key) != snapshot.get(key)
            for key in ('window_id', 'window_rect', 'monitor_rect')):
        return {'error': '窗口已改变或桌面不可读取，请重新观察，未分享旧画面。'}
    image = QImage.fromData(base64.b64decode(frame['image_url']['url'].split(',', 1)[1]))
    if image.isNull():
        return {'error': '实际截图不可读取。'}
    crop = args.get('crop')
    if crop is not None:
        x, y, width, height = (int(crop[key]) for key in ('x', 'y', 'width', 'height'))
        if min(x, y) < 0 or min(width, height) <= 0 or x+width > image.width() or y+height > image.height():
            return {'error': '分享区域超出了实际截图范围。'}
        image = image.copy(x, y, width, height)
    folder = window.database.database_path.parent / 'attachments'
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / ('shared-view-'+uuid.uuid4().hex+'.jpg')
    if not path.resolve().is_relative_to(window.database.database_path.parent.resolve() / 'attachments'):
        return {'error': '图片保存路径异常。'}
    if not image.save(str(path), 'JPEG', 88):
        return {'error': '真实截图保存失败。'}
    return {'image': {'path': path.relative_to(window.database.database_path.parent.parent).as_posix(),
            'title': str(args.get('image_title') or '刚看到的画面')[:100], 'label': '实际屏幕画面',
            'observed_at': datetime.now().astimezone().isoformat(timespec='seconds')}}


def deliver(window, worker, request):
    job = window.active_job
    text, image = request['text'], request.get('image')
    created_at = window.database._now()
    message_id = window.database.save_message(job['conversation_key'], job['source'], 'assistant', text,
        job.get('peer_id', ''), job.get('peer_name', ''), created_at)
    receipts = list(worker.toolkit.evidence.receipts)
    extras = [{'kind': 'tool_receipts', 'target': json.dumps(receipts, ensure_ascii=False)},
              {'kind': 'chat_flow', 'target': 'wait' if request.get('wait') else 'message'}]
    if image:
        extras.append({'kind': 'image', 'target': json.dumps(image, ensure_ascii=False)})
        path = worker.toolkit.root / image['path']
        window.database.save_attachment(message_id, {'file_name': path.name, 'kind': 'image',
            'local_path': image['path'], 'mime_type': 'image/jpeg', 'extracted_text': '', 'size_bytes': path.stat().st_size})
    if job.get('user_message_id'):
        extras.append({'kind': 'request_origin', 'target': str(job['user_message_id'])})
    if job.get('proactive'):
        extras.append({'kind': 'proactive', 'target': 'local'})
    if job['source'] == 'qq':
        extras.append({'kind': 'qq_delivery', 'target': 'pending' if request['delivery'].get('pending') else
                       'sent' if request['delivery'].get('confirmed') else 'unknown'})
    window.database.save_extras(message_id, extras)
    if window.stream_speech_enabled:
        window._add_text_to_speech_buffer(text, flush=True)
        if window.active_speech_batch_id is not None:
            window.database.link_audio_batch(window.active_speech_batch_id, message_id)
        window._prepare_stream_speech()
    body = window.active_label
    if body is not None:
        window._chat_flush_timer.stop()
        window._chat_pending.clear()
        window._reasoning_pending.clear()
        window._chat_text = ''
        body.setText(text)
        body.finish_reasoning()
        window._register_message_for_deletion(body, message_id, created_at)
        window.database.bind_command_traces(message_id, list(getattr(body, 'command_cards', {})))
        from message_cards import render_extras
        render_extras(window, body, message_id, worker.toolkit.root)
        window._show_message_row(body)
    else:
        window.add_message('assistant', text, source=job['source'], peer_id=job.get('peer_id', ''),
                           created_at=created_at, message_id=message_id)
    job.setdefault('flow_message_ids', []).append(message_id)
    window._plugin_message(message_id)
    if request.get('wait'):
        wait_for_reply(window.database, job, message_id, text)
    window.active_label = window.add_message('assistant', '正在继续…', source=job['source'],
        peer_id=job.get('peer_id', ''), peer_name=job.get('peer_name', ''))
    window.active_label.message_row.hide()
    window.scroll_to_bottom()
    if job.get('proactive'):
        window.companion.delivered(text)
    return {'confirmed': bool(request['delivery'].get('confirmed')), 'message_id': message_id,
            'waiting_for_reply': bool(request.get('wait')), 'image_shared': bool(image)}


def record_delivery(window, request):
    mid, result = request['message_id'], request['delivery']
    if not window.database.get_message(mid):
        return {'cancelled': True}
    status = 'sent' if result.get('confirmed') else 'unknown' if result.get('outcome_unknown') or result.get('sent_parts') else 'failed'
    extras = [row for row in window.database.get_extras(mid) if row['kind'] != 'qq_delivery']
    window.database.save_extras(mid, [*extras, {'kind': 'qq_delivery', 'target': status}])
    row = window.message_rows.get(mid)
    body = getattr(row, 'message_body', None) if row else None
    if body is not None:
        from message_cards import render_extras
        render_extras(window, body, mid, window.database.database_path.parent.parent)
    if status == 'failed':
        with closing(window.database._connect()) as connection, connection:
            window.database._clear_interaction_wait(connection, mid)
    return {'confirmed': bool(result.get('confirmed')), 'message_id': mid, 'status': status}
