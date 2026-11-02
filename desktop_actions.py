"""Small Win32 input adapter. Called on the GUI thread after live permission checks."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import math
import time


class MouseInput(ctypes.Structure):
    _fields_ = [('dx', wintypes.LONG), ('dy', wintypes.LONG), ('mouseData', wintypes.DWORD),
               ('dwFlags', wintypes.DWORD), ('time', wintypes.DWORD), ('dwExtraInfo', ctypes.c_size_t)]


class KeyboardInput(ctypes.Structure):
    _fields_ = [('wVk', wintypes.WORD), ('wScan', wintypes.WORD), ('dwFlags', wintypes.DWORD),
               ('time', wintypes.DWORD), ('dwExtraInfo', ctypes.c_size_t)]


class InputUnion(ctypes.Union):
    _fields_ = [('mi', MouseInput), ('ki', KeyboardInput)]


class Input(ctypes.Structure):
    _anonymous_ = ('value',)
    _fields_ = [('type', wintypes.DWORD), ('value', InputUnion)]


KEYS = {'CTRL': 0x11, 'ALT': 0x12, 'SHIFT': 0x10, 'WIN': 0x5B,
        'ENTER': 0x0D, 'TAB': 9, 'ESC': 0x1B, 'SPACE': 0x20, 'BACKSPACE': 8,
        'DELETE': 0x2E, 'HOME': 0x24, 'END': 0x23, 'PAGEUP': 0x21, 'PAGEDOWN': 0x22,
        'LEFT': 0x25, 'UP': 0x26, 'RIGHT': 0x27, 'DOWN': 0x28}
KEYS.update({chr(code): code for code in range(0x30, 0x5B) if chr(code).isalnum()})
KEYS.update({'F'+str(i): 0x6F+i for i in range(1, 13)})


def _keyboard(key, flags=0, scan=0):
    return Input(type=1, ki=KeyboardInput(wVk=key, wScan=scan, dwFlags=flags))


def perform(args, snapshot):
    from companionship import foreground_state
    state = foreground_state(True)
    if not state.get('available'):
        return {'error': '当前桌面不可操作，可能已锁屏。'}
    if not snapshot or time.monotonic()-snapshot.get('captured_at', 0) > 30:
        return {'error': '请先 observe_desktop 获取新的真实截图，再按图中像素坐标操作。'}
    if (state.get('window_id') != snapshot.get('window_id') or
            state.get('window_rect') != snapshot.get('window_rect') or
            state.get('monitor_rect') != snapshot.get('monitor_rect')):
        return {'error': '前台窗口或显示器已改变，请重新观察，未执行输入。'}
    action = args.get('action')
    events = []
    point = None
    if action in {'click', 'double_click', 'right_click', 'move', 'scroll'}:
        x, y = float(args.get('x', -1)), float(args.get('y', -1))
        width, height = snapshot['image_size']
        if not math.isfinite(x+y) or not (0 <= x < width and 0 <= y < height):
            return {'error': '坐标必须位于最近截图的像素范围内。'}
        left, top, right, bottom = snapshot['monitor_rect']
        point = (round(left+x*(right-left)/width), round(top+y*(bottom-top)/height))
        flags = {'click': (2, 4), 'double_click': (2, 4, 2, 4), 'right_click': (8, 16)}.get(action, ())
        events.extend(Input(type=0, mi=MouseInput(dwFlags=flag)) for flag in flags)
        if action == 'scroll':
            steps = max(-8, min(8, int(args.get('scroll_steps', -3))))
            events.append(Input(type=0, mi=MouseInput(mouseData=(steps*120) & 0xFFFFFFFF, dwFlags=0x0800)))
    elif action == 'type_text':
        text = str(args.get('text', ''))
        if not text or len(text) > 2000:
            return {'error': '输入文本须为 1–2000 字符。'}
        encoded = text.encode('utf-16-le')
        for offset in range(0, len(encoded), 2):
            unit = int.from_bytes(encoded[offset:offset+2], 'little')
            events.extend((_keyboard(0, 4, unit), _keyboard(0, 6, unit)))
    elif action == 'hotkey':
        keys = args.get('keys', [])
        if not isinstance(keys, list) or not 1 <= len(keys) <= 4 or any(str(key).upper() not in KEYS for key in keys):
            return {'error': '按键使用 CTRL/ALT/SHIFT/WIN、A–Z、0–9、F1–F12、ENTER/TAB/ESC/方向键等，最多4键。'}
        codes = [KEYS[str(key).upper()] for key in keys]
        events.extend(_keyboard(key) for key in codes)
        events.extend(_keyboard(key, 2) for key in reversed(codes))
    else:
        return {'error': '未知桌面动作。'}
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
    user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(Input), ctypes.c_int]
    user32.SendInput.restype = wintypes.UINT
    if point and not user32.SetCursorPos(*point):
        return {'error': '鼠标移动失败，未继续点击。'}
    if events:
        inputs = (Input*len(events))(*events)
        sent = user32.SendInput(len(events), inputs, ctypes.sizeof(Input))
        if sent != len(events):
            # Release key/button downs if a system restriction accepted only part
            # of the sequence. Never resend text/clicks blindly.
            releases = [event for event in events if event.type == 1 and event.ki.dwFlags & 2
                        or event.type == 0 and event.mi.dwFlags in (4, 16)]
            if releases:
                user32.SendInput(len(releases), (Input*len(releases))(*releases), ctypes.sizeof(Input))
            return {'error': '系统仅接收了部分输入，可能被目标程序权限阻止；请重新观察，勿直接重试。',
                    'partial_input': True, 'accepted_events': sent}
    return {'performed': True, 'action': action, 'window_before': state.get('title', ''),
            'note': '输入已提交 Windows，不代表目标应用已完成任务；请依据后续截图核实。'}
