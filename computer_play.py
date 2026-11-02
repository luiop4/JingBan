"""Real, short Win32 mouse/window play with immediate cancellation."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import math
import re
import threading
import time
import uuid

from PySide6.QtCore import QObject, QTimer, Qt


class WindowsPlayDriver:
    def __init__(self):
        self.api = ctypes.WinDLL('user32', use_last_error=True)
        a = self.api
        a.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
        a.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
        a.GetAsyncKeyState.argtypes = [ctypes.c_int]
        a.GetAsyncKeyState.restype = ctypes.c_short
        a.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        a.GetForegroundWindow.restype = wintypes.HWND
        a.IsWindow.argtypes = a.IsZoomed.argtypes = a.IsIconic.argtypes = [wintypes.HWND]
        a.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        a.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_int, ctypes.c_int, wintypes.UINT]

    def snapshot(self):
        from companionship import foreground_state
        return foreground_state(False)

    def cursor(self):
        point = wintypes.POINT()
        if not self.api.GetCursorPos(ctypes.byref(point)):
            raise ValueError('没有读到鼠标位置。')
        return point.x, point.y

    def move_cursor(self, point):
        return bool(self.api.SetCursorPos(*point))

    def escape(self):
        return bool(self.api.GetAsyncKeyState(0x1B) & 0x8000)

    def mouse_down(self):
        return any(self.api.GetAsyncKeyState(key) & 0x8000 for key in (1, 2, 4))

    def movable(self, hwnd):
        if not self.api.IsWindow(hwnd) or self.api.IsZoomed(hwnd) or self.api.IsIconic(hwnd):
            return False
        name = ctypes.create_unicode_buffer(128)
        self.api.GetClassNameW(hwnd, name, len(name))
        return name.value not in {'Progman', 'WorkerW', 'Shell_TrayWnd', '#32770'}

    def move_window(self, hwnd, point):
        # No resizing, focus change, minimize/close or injected keystrokes.
        return bool(self.api.SetWindowPos(hwnd, None, *point, 0, 0, 0x0001 | 0x0004 | 0x0010 | 0x4000))


class ComputerPlay(QObject):
    def __init__(self, window, driver=None, clock=time.monotonic):
        super().__init__(window)
        self.window, self.driver, self.clock = window, driver, clock
        self.active = None
        self.timer = QTimer(self)
        self.timer.setInterval(35)
        self.timer.timeout.connect(self.step)
        self.paused = False

    def chat_signal(self, text, peer=''):
        if peer and not self.window.qq_account_service.computer_allowed(peer):
            return False
        value = str(text).strip().strip('，。！!？?~～')
        if re.fullmatch(r'(?:停|停止|停下|别闹|别动鼠标|别动窗口|不要捣乱|停止捣乱|停止电脑玩闹)(?:了|吧|一下)?', value):
            self.stop('你说停，已放开电脑操作。', pause=True)
            return True
        if re.fullmatch(r'(?:继续玩|恢复电脑玩闹|可以继续玩)(?:吧|了)?', value):
            self.paused = False
            return True
        return False

    def allowed(self, worker):
        from interaction_modes import is_work
        window = self.window
        if (self.paused or is_work(window) or getattr(window, '_closing', False) or window._resetting_data
                or not window.companion.options().get('playful_computer', False)
                or worker is not window.active_worker or worker.isInterruptionRequested()):
            return False
        if worker.proactive and not (worker.self_directed and window.companion.options()['enabled'] and window.companion.options()['allow_actions']):
            return False
        peer = getattr(worker, 'qq_peer', '')
        return window.qq_account_service.computer_allowed(peer) if peer else window.agentEnabledCheckBox.isChecked()

    def dispatch(self, request):
        if request.get('cancelled') or not self.allowed(request['worker']):
            request['result'] = {'cancelled': True, 'note': '电脑玩闹已关闭、已暂停或本轮没有电脑权限。'}
            request['ready'].set()
            return
        if self.active:
            request['result'] = {'error': '已经有一个电脑动作在进行，不重复启动。'}
            request['ready'].set()
            return
        try:
            args = request['args']
            action = args.get('action')
            duration = float(args.get('seconds', 2.5))
            if action not in {'cursor_tease', 'window_nudge'} or not math.isfinite(duration) or not 0.5 <= duration <= 5:
                raise ValueError('请选择鼠标逗弄或窗口挪动，单次0.5至5秒。')
            if self.driver is None:
                self.driver = WindowsPlayDriver()
            state = self.driver.snapshot()
            if not state.get('available'):
                raise ValueError('当前桌面不可操作。')
            if action == 'window_nudge' and not self.driver.movable(state['window_id']):
                raise ValueError('当前窗口不适合挪动，可以选择鼠标动作。')
            self.active = {'request': request, 'state': state, 'action': action, 'duration': duration,
                           'start': self.clock(), 'last_cursor': self.driver.cursor(), 'anchor': self.driver.cursor(),
                           'last_rect': tuple(state['window_rect']), 'moves': 0, 'verified': 0,
                           'restorable': True, 'id': uuid.uuid4().hex}
            self.timer.start()
        except Exception as error:
            request['result'] = {'error': str(error)[:180]}
            request['ready'].set()

    def step(self):
        play = self.active
        if not play:
            return
        request, driver = play['request'], self.driver
        try:
            if driver.escape():
                self.stop('Esc停止了电脑玩闹。', pause=True)
                return
            if request.get('cancelled') or not self.allowed(request['worker']):
                self.stop('当前对话或电脑权限已结束。')
                return
            elapsed = self.clock()-play['start']
            state = driver.snapshot()
            if not state.get('available') or state['window_id'] != play['state']['window_id']:
                self.stop('前台窗口改变，已放开操作。')
                return
            if elapsed >= play['duration']:
                self.stop('动作结束。', completed=True)
                return
            if driver.mouse_down():
                self.stop('你开始点击或拖动，已放开操作。')
                return
            phase = elapsed * 9
            if play['action'] == 'cursor_tease':
                current = driver.cursor()
                # Follow the human's intended movement; ordinary mouse movement
                # does not cancel the playful offset or pull to an old anchor.
                dx, dy = current[0]-play['last_cursor'][0], current[1]-play['last_cursor'][1]
                play['anchor'] = (play['anchor'][0]+dx, play['anchor'][1]+dy)
                x, y = play['anchor']
                left, top, right, bottom = state['monitor_rect']
                point = (max(left, min(right-1, round(x+22*math.sin(phase)))),
                         max(top, min(bottom-1, round(y+13*math.sin(phase*1.3)))))
                if not driver.move_cursor(point):
                    raise ValueError('Windows没有接受鼠标移动。')
                play['last_cursor'] = driver.cursor()
                play['verified'] += play['last_cursor'] == point
            else:
                rect = tuple(state['window_rect'])
                original = tuple(play['state']['window_rect'])
                if rect == play['last_rect'] and rect != original:
                    play['verified'] += 1
                elif rect == original and play['last_rect'] != original:
                    # The target may be slow to process an asynchronous move.
                    # Keep only one outstanding move instead of flooding it.
                    return
                elif rect not in (play['last_rect'], original):
                    play['restorable'] = False
                    self.stop('你调整了窗口，已放开操作。')
                    return
                left, top, right, bottom = original
                x, y = left+round(10*math.sin(phase)), top+round(5*math.sin(phase*1.4))
                if not driver.move_window(state['window_id'], (x, y)):
                    raise ValueError('Windows没有接受窗口移动。')
                play['last_rect'] = (x, y, x+right-left, y+bottom-top)
            play['moves'] += 1
        except Exception as error:
            self.stop(str(error)[:160])

    def stop(self, reason='已停止电脑玩闹。', *, completed=False, pause=False):
        if pause:
            # Esc is a session-level veto, not merely a skipped animation frame.
            self.paused = True
        self.timer.stop()
        play, self.active = self.active, None
        if not play:
            return
        restored = False
        if play['action'] == 'window_nudge' and play['restorable']:
            try:
                state = self.driver.snapshot()
                if state.get('available') and state['window_id'] == play['state']['window_id']:
                    rect = tuple(state['window_rect'])
                    if rect in (play['last_rect'], tuple(play['state']['window_rect'])):
                        restored = self.driver.move_window(state['window_id'], play['state']['window_rect'][:2])
            except Exception:
                pass
        result = {'performed': play['verified'] > 0, 'finished': True, 'completed': completed,
                  'interrupted': not completed, 'action': play['action'], 'moves': play['moves'],
                  'verified_moves': play['verified'], 'restore_requested': bool(restored), 'note': reason}
        if not result['performed']:
            result['note'] += '没有实际位移可确认。'
        play['request']['result'] = result
        play['request']['ready'].set()

    def install(self, toolkit, worker):
        from chat_tools import function
        if not self.window.companion.options().get('playful_computer', False):
            return
        peer = getattr(worker, 'qq_peer', '')
        if peer and not self.window.qq_account_service.computer_allowed(peer):
            return
        if not peer and not self.window.agentEnabledCheckBox.isChecked():
            return
        if worker.api_settings.get('interaction_mode', 'normal') == 'work':
            return
        worker.computer_play_requested.connect(self.dispatch, Qt.ConnectionType.QueuedConnection)
        attempted = False
        def execute(args):
            nonlocal attempted
            if attempted:
                return {'error': '本轮已经做过一次电脑玩闹，先接着聊天，不连续重启来延长动作。'}
            attempted = True
            request = {'worker': worker, 'args': args, 'ready': threading.Event(), 'result': {}}
            worker.computer_play_requested.emit(request)
            deadline = time.monotonic()+9
            while not request['ready'].wait(0.05):
                if worker.isInterruptionRequested() or time.monotonic() >= deadline:
                    request['cancelled'] = True
                    return {'cancelled': True, 'note': '本次电脑玩闹已取消。'}
            return request['result']
        toolkit.computer_play = execute
        toolkit.definitions.append(function('play_with_computer',
            '真的短暂移动鼠标或挪动当前窗口，可以在普通聊天或自主活动时按当下情绪主动逗主人，不需要每次等口令。'
            '不是表情动画。cursor_tease在鼠标周围轻微扰动，window_nudge挪动普通窗口后申请放回。'
            '一次动作就收住，不能接连调用延长；Esc、停止指令或点击拖动会放开。只凭实际回执说明做过什么。', {
                'action': {'type': 'string', 'enum': ['cursor_tease', 'window_nudge']},
                'seconds': {'type': 'number', 'minimum': 0.5, 'maximum': 5},
                'reason': {'type': 'string', 'description': '这次想这样逗主人的具体来由'}}, ['action', 'reason']))
