"""Model tools for visible preferences and an account balance query."""
from copy import deepcopy
from datetime import datetime
import threading
import time
from urllib.parse import urlsplit

import requests
from PySide6.QtCore import QObject, Qt, QSignalBlocker


PREFERENCES = {
    'thinking': ('deepseek', 'thinking_enabled', bool),
    'thinking_role_style': ('deepseek', 'thinking_role_style', bool),
    'voice_enabled': ('voice', 'enabled', bool),
    'speech_rate': ('voice', 'doubao_speech_rate', int),
    'notifications': ('proactive', 'notifications', bool),
    'interests_hint': ('proactive', 'interests_hint', str),
    'video_skipping': ('browsing', 'browse_skipping', bool),
    'video_watch_seconds': ('browsing', 'browse_watch_seconds', int),
    'video_enabled': ('browsing', 'browse_bilibili', bool),
    'bilibili_interaction': ('browsing', 'browse_allow_comments', bool),
    'share_discoveries': ('browsing', 'browse_share_local', bool),
    'self_directed': ('proactive', 'self_directed', bool),
    'observe_window': ('proactive', 'observe_window', bool),
    'observe_screen': ('proactive', 'observe_screen', bool),
    'away_activities': ('proactive', 'away_activities', bool),
    'auto_qzone': ('qq.account', 'auto_qzone', bool),
    'auto_profile': ('qq.account', 'auto_profile', bool),
    'post_topics': ('qq.account', 'topics', str),
}


def balance(api, cancelled=lambda: False):
    parsed = urlsplit(str(api.get('base_url') or ''))
    if parsed.scheme != 'https' or parsed.hostname != 'api.deepseek.com' or parsed.port not in (None, 443) or parsed.username or parsed.password:
        raise ValueError('当前连接不是DeepSeek官方HTTPS接口，无法查询官方余额。')
    key = str(api.get('api_key') or '').strip()
    if not key:
        raise ValueError('请先在设置中配置API密钥。')
    if cancelled():
        raise ValueError('余额查询已取消。')
    try:
        with requests.get('https://api.deepseek.com/user/balance',
                headers={'Authorization': 'Bearer '+key, 'Accept': 'application/json'},
                timeout=(4, 12), allow_redirects=False) as response:
            if response.status_code != 200:
                raise ValueError('余额接口未返回成功，请检查密钥或官方连接。')
            payload = response.json()
    except requests.RequestException:
        raise ValueError('余额服务暂时连接不上。') from None
    if cancelled():
        raise ValueError('余额查询已取消。')
    if not isinstance(payload, dict) or not isinstance(payload.get('balance_infos'), list):
        raise ValueError('余额接口返回格式无效。')
    return {'confirmed': True, 'is_available': payload.get('is_available') is True,
            'balance_infos': [{k: str(row.get(k, ''))[:60] for k in
                ('currency', 'total_balance', 'granted_balance', 'topped_up_balance')}
                for row in payload['balance_infos'][:8] if isinstance(row, dict)],
            'observed_at': datetime.now().astimezone().isoformat(timespec='seconds')}


def values(window):
    result = {'mode': window.settings.get('interaction', {}).get('mode', 'normal')}
    for name, (section, field, kind) in PREFERENCES.items():
        value = window.settings
        for part in section.split('.'):
            value = value.get(part, {})
        result[name] = value.get(field)
    return result


class AppControls(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window

    def dispatch(self, request):
        window, worker = self.window, request['worker']
        try:
            if (worker is not window.active_worker or worker.isInterruptionRequested() or request.get('cancelled')
                    or getattr(window, '_closing', False) or window._resetting_data):
                raise ValueError('这次对话已结束，没有更改设置。')
            peer = getattr(worker, 'qq_peer', '')
            if peer and not window.qq_account_service.computer_allowed(peer):
                raise ValueError('这个QQ会话尚未开放软件设置管理。')
            if request['action'] == 'read':
                request['result'] = {'confirmed': True, 'settings': values(window)}
                return
            changes = request.get('changes')
            if worker.proactive and not window.companion.options()['allow_actions']:
                raise ValueError('当前心跳没有开放自主动作，未更改设置。')
            if not isinstance(changes, dict) or not changes or any(k not in {*PREFERENCES, 'mode'} for k in changes):
                raise ValueError('请只修改工具列出的日常设置；连接密钥、信任名单和授权范围需在设置页管理。')
            for key, value in changes.items():
                if key == 'mode':
                    if value not in {'normal', 'work'}:
                        raise ValueError('模式应为 normal 或 work。')
                else:
                    kind = PREFERENCES[key][2]
                    if type(value) is not kind:
                        raise ValueError(key+' 的数值类型不正确。')
                    limits = {'speech_rate': (-50, 100), 'heartbeat_interval': (1, 120), 'video_watch_seconds': (15, 600),
                              'post_interval': (30, 10080)}
                    if key in limits and not limits[key][0] <= value <= limits[key][1]:
                        raise ValueError(key+' 超出可设置范围。')
                    if kind is str and len(value) > (500 if key in ('video_topics', 'interests_hint') else 1500):
                        raise ValueError('偏好内容过长。')
            old = deepcopy(window.settings)
            requested_mode = changes.get('mode')
            try:
                for key, value in changes.items():
                    if key == 'mode':
                        # Keep the current reply and its widgets in the original
                        # conversation; switch only once the worker has exited.
                        continue
                    section, field, _ = PREFERENCES[key]
                    target = window.settings
                    for part in section.split('.'):
                        target = target.setdefault(part, {})
                    target[field] = value
                window.write_config()
            except Exception:
                window.settings = old
                raise
            if requested_mode:
                window._pending_interaction_mode = requested_mode
            widgets = {'thinking': window.thinkingEnabledCheckBox, 'voice_enabled': window.voiceEnabledCheckBox,
                       'thinking_role_style': window.thinkingRoleStyleCheckBox,
                       'speech_rate': window.doubaoSpeechRateSpin}
            for name, widget in widgets.items():
                if name in changes:
                    blocker = QSignalBlocker(widget)
                    widget.setValue(changes[name]) if name == 'speech_rate' else widget.setChecked(changes[name])
                    del blocker
            if 'thinking' in changes:
                window.thinkingRoleStyleCheckBox.setEnabled(changes['thinking'])
            window.qq_account_service.configure(window.settings['qq']['account'])
            window.qq_account_service.configure_browsing(window.settings['browsing'])
            if changes.get('voice_enabled') is False:
                window.stop_speech()
            panel = window.qq_account_panel
            for key, widget in (('video_topics', panel.browse_topics), ('video_skipping', panel.browse_skipping),
                                ('video_watch_seconds', panel.browse_seconds), ('video_enabled', panel.browse_enabled),
                                ('bilibili_interaction', panel.browse_comments), ('share_discoveries', panel.browse_local),
                                ('auto_qzone', panel.auto), ('auto_profile', panel.auto_profile)):
                if key in changes:
                    blocker = QSignalBlocker(widget)
                    widget.setText(changes[key]) if key == 'video_topics' else (
                        widget.setValue(changes[key]) if key == 'video_watch_seconds' else widget.setChecked(changes[key]))
                    del blocker
            if 'post_topics' in changes:
                panel.topics.setPlainText(changes['post_topics'])
            if 'post_interval' in changes:
                panel.interval.setValue(changes['post_interval'])
            heartbeat = window.heartbeat_panel
            for key, widget in (('notifications', heartbeat.checks['notifications']),
                                ('heartbeat_interval', heartbeat.interval), ('interests_hint', heartbeat.interests),
                                *((key, heartbeat.checks[key]) for key in ('self_directed', 'observe_window', 'observe_screen', 'away_activities'))):
                if key in changes:
                    blocker = QSignalBlocker(widget)
                    if key in ('self_directed', 'observe_window', 'observe_screen', 'away_activities'):
                        widget.setChecked(changes[key])
                    elif key == 'notifications':
                        widget.setChecked(changes[key])
                        heartbeat.checks['notification_sound'].setEnabled(changes[key])
                    elif key == 'heartbeat_interval':
                        widget.setValue(changes[key])
                    else:
                        widget.setPlainText(changes[key])
                    del blocker
            if any(k in changes for k in ('interests_hint', 'heartbeat_interval')):
                window.companion.invalidate_decision()
            window.companion.refresh()
            if any(key in changes for key in ('self_directed', 'observe_window', 'observe_screen', 'away_activities')):
                window.companion.invalidate_decision()
            if changes.get('video_enabled') is False:
                window.bilibili_visits.stop_session(cancel_share=True)
            if 'heartbeat_interval' in changes:
                window.companion._schedule_next()
            window.interaction_modes.render()
            request['result'] = {'confirmed': True, 'changed': changes, 'settings': values(window),
                                 'note': '日常设置已保存；模式在当前回复和排队任务结束后切换，模型思考设置从下一次请求生效。'}
        except Exception as error:
            request['result'] = {'error': str(error)[:200]}
        finally:
            request['ready'].set()

    def install(self, toolkit, worker):
        from chat_tools import function
        peer = getattr(worker, 'qq_peer', '')
        if peer and not self.window.qq_account_service.computer_allowed(peer):
            return
        worker.app_control_requested.connect(self.dispatch, Qt.ConnectionType.QueuedConnection)
        def execute(name, args):
            if peer and not self.window.qq_account_service.computer_allowed(peer):
                return {'error': '这个QQ会话的软件管理权限已关闭。'}
            if name == 'query_api_balance':
                try:
                    return {**balance(worker.api_settings, worker.isInterruptionRequested),
                            'token_usage': toolkit.database.api_usage_summary()}
                except ValueError as error:
                    return {'error': str(error)}
            request = {'worker': worker, 'action': 'read' if name == 'read_app_settings' else 'change',
                       'changes': args.get('changes'), 'ready': threading.Event()}
            worker.app_control_requested.emit(request)
            deadline = time.monotonic()+10
            while not request['ready'].wait(0.1):
                if worker.isInterruptionRequested() or time.monotonic() > deadline:
                    request['cancelled'] = True
                    return {'error': '没有取得设置保存结果。'}
            return request['result']
        toolkit.app_actions = execute
        properties = {'mode': {'type': 'string', 'enum': ['normal', 'work']}}
        descriptions = {'thinking': '启用思考：普通模式为角色演绎，工作模式为模型深度思考', 'voice_enabled': '自动语音回复', 'speech_rate': '豆包语速百分比：-50至100',
            'thinking_role_style': '普通模式展示“思考”角色演绎；普通模式不请求或保存原始推理，工作模式不展示演绎',
            'notifications': '后台消息通知', 'heartbeat_interval': '空闲心跳参考间隔，1至120分钟', 'interests_hint': '自主兴趣提示，最多500字',
            'video_skipping': '视频允许跳看', 'video_watch_seconds': '单片停留上限15至600秒',
            'post_topics': '空间动态主题偏好，最多1500字', 'post_interval': '自主发布最短间隔30至10080分钟',
            'video_enabled': 'B站浏览功能总开关', 'bilibili_interaction': 'B站后台评论与点赞',
            'share_discoveries': '向主人分享实际发现', 'self_directed': '自主选事做',
            'observe_window': '按需了解窗口标题', 'observe_screen': '按需查看桌面',
            'away_activities': '主人离开时仍可做后台活动', 'auto_qzone': '自主空间动态', 'auto_profile': '自主打理QQ昵称和头像'}
        for key, (_, _, kind) in PREFERENCES.items():
            properties[key] = {'type': {bool: 'boolean', int: 'integer', str: 'string'}[kind], 'description': descriptions[key]}
        toolkit.definitions.extend([
            function('read_app_settings', '读取可管理的日常软件设置，不返回密钥、登录态或信任名单。', {}, []),
            function('change_app_settings', '保存并实际应用软件日常设置。结合用户意图可自行调整适合的普通偏好；不要为了执行别的操作擅自扩大权限。', {
                'changes': {'type': 'object', 'properties': properties, 'additionalProperties': False}}, ['changes']),
            function('query_api_balance', '实时查询当前官方DeepSeek API余额及本机Token使用统计，不透露密钥，不猜余额。', {}, []),
        ])
