"""Own one isolated Edge/Chrome tab and read its real player via local CDP."""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import threading
import time
import uuid
from urllib.parse import urlparse, urlencode

import requests


def video_url(value):
    parsed = urlparse(str(value))
    if parsed.scheme != 'https' or parsed.hostname not in {'www.bilibili.com', 'bilibili.com'}:
        return ''
    match = re.fullmatch(r'/video/(BV[a-zA-Z0-9]{10})/?', parsed.path)
    return f'https://www.bilibili.com/video/{match[1]}/' if match else ''


def browser_executable():
    candidates = [shutil.which('msedge'), shutil.which('chrome')]
    for base in (os.environ.get('PROGRAMFILES(X86)'), os.environ.get('PROGRAMFILES'), os.environ.get('LOCALAPPDATA')):
        if base:
            candidates.extend(str(Path(base)/name) for name in (
                'Microsoft/Edge/Application/msedge.exe', 'Google/Chrome/Application/chrome.exe'))
    return next((path for path in candidates if path and Path(path).is_file()), '')


PLAYER_SCRIPT = r'''(() => {
  const v = document.querySelector('video');
  const text = (document.body?.innerText || '').slice(0, 12000);
  const blocked = /请完成安全验证|验证后继续访问|访问权限受限|完成验证后继续/.test(text);
  const login = /登录后观看完整视频|登录后继续观看|该视频需要登录后观看/.test(text);
  let rect = null;
  if (v) {
    const r = v.getBoundingClientRect();
    rect = {x:Math.max(0,r.x),y:Math.max(0,r.y),
      width:Math.max(0,Math.min(r.right,innerWidth)-Math.max(0,r.x)),
      height:Math.max(0,Math.min(r.bottom,innerHeight)-Math.max(0,r.y))};
  }
  return JSON.stringify({url:location.href,title:document.querySelector('h1')?.innerText || document.title,
    blocked,login,has_video:!!v,current_time:v?.currentTime||0,duration:Number.isFinite(v?.duration)?v.duration:0,
    ended:v?.ended||false,paused:v?.paused??true,seeking:v?.seeking||false,ready:v?.readyState||0,error:v?.error?.code||0,
    rect,scroll_x:scrollX,scroll_y:scrollY});
})()'''


class BilibiliBrowser:
    def __init__(self, root, mode='isolated', link=None, *, background=False, profile_name='bilibili-browser'):
        self.root = Path(root)
        self.mode = 'extension' if mode == 'extension' else 'isolated'
        self.background = background
        if profile_name not in ('bilibili-browser', 'web-browser'):
            raise ValueError('不支持的浏览器资料目录。')
        self.profile_name = profile_name
        from browser_link import BrowserLink
        self.link = link or BrowserLink(root)
        self.endpoint = ''
        self.target_id = ''
        self.process = None
        self.lock = threading.RLock()
        self.http = requests.Session()
        self.http.trust_env = False

    def _json(self, path, method='get'):
        response = self.http.request(method, self.endpoint+path, timeout=(2, 3))
        response.raise_for_status()
        return response.json()

    def ensure(self, cancelled):
        if self.mode == 'extension':
            result = self.link.request('Link.ensure', cancelled=cancelled)
            self.target_id = str(result['id'])
            return
        if self.endpoint and self.target_id:
            try:
                if any(row.get('id') == self.target_id for row in self._json('/json/list')):
                    return
            except (requests.RequestException, ValueError):
                pass
        if cancelled():
            raise ValueError('漫游已停止。')
        executable = browser_executable()
        if not executable:
            raise ValueError('未找到 Edge 或 Chrome，请安装其中一个浏览器。')
        # A dedicated persistent profile keeps the user's normal browser untouched.
        profile = self.root / 'data' / self.profile_name
        profile.mkdir(parents=True, exist_ok=True)
        if profile.is_symlink() or profile.resolve() != profile.absolute():
            raise ValueError('漫游浏览器目录异常。')
        # A previous app run can have left its dedicated browser window open.
        # Reuse only this profile's endpoint, and create a new owned tab.
        active_port = profile / 'DevToolsActivePort'
        try:
            saved = active_port.read_text(encoding='utf-8').splitlines()
            old_port = int(saved[0])
            if 1024 <= old_port <= 65535:
                self.endpoint = f'http://127.0.0.1:{old_port}'
                version = self._json('/json/version')
                if 'Browser' in version:
                    target = self._json('/json/new?about:blank', 'put')
                    self.target_id = target['id']
                    return
        except (OSError, ValueError, KeyError, IndexError, requests.RequestException):
            pass
        arguments = [executable, '--user-data-dir='+str(profile.resolve()),
            '--remote-debugging-port=0', '--remote-debugging-address=127.0.0.1',
            '--no-first-run', '--no-default-browser-check', '--disable-background-mode', '--mute-audio',
            '--disk-cache-size=67108864', '--media-cache-size=134217728',
            *(['--headless=new', '--disable-gpu'] if self.background else ['--new-window']), 'about:blank']
        self.process = subprocess.Popen(arguments, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        deadline = time.monotonic()+20
        while time.monotonic() < deadline:
            if cancelled():
                raise ValueError('漫游已停止。')
            try:
                # Chromium writes the actual random endpoint into its profile.
                active = active_port.read_text(encoding='utf-8').splitlines()
                actual_port = int(active[0])
                if not 1024 <= actual_port <= 65535:
                    raise ValueError('无效的浏览器端口。')
                self.endpoint = f'http://127.0.0.1:{actual_port}'
                tabs = [row for row in self._json('/json/list') if row.get('type') == 'page']
                if tabs:
                    self.target_id = next((row['id'] for row in tabs if row.get('url') == 'about:blank'), tabs[0]['id'])
                    return
            except (OSError, requests.RequestException, ValueError, KeyError, IndexError):
                pass
            time.sleep(0.2)
        raise ValueError('漫游浏览器未能建立控制连接；请关闭旧漫游窗口后重试。')

    def command(self, method, params=None, cancelled=lambda: False):
        if self.mode == 'extension':
            with self.lock:
                return self.link.request(method, params, self.target_id, cancelled)
        from websockets.sync.client import connect
        with self.lock:
            if cancelled():
                raise ValueError('漫游已停止。')
            tabs = self._json('/json/list')
            tab = next((row for row in tabs if row.get('id') == self.target_id), None)
            if not tab:
                raise ValueError('漫游窗口已关闭，已停止自动播放。')
            endpoint = str(tab.get('webSocketDebuggerUrl', ''))
            parsed = urlparse(endpoint)
            expected = urlparse(self.endpoint)
            if parsed.scheme != 'ws' or parsed.hostname != '127.0.0.1' or parsed.port != expected.port:
                raise ValueError('浏览器控制地址异常。')
            with connect(endpoint, open_timeout=4, close_timeout=1, max_size=12*1024*1024) as websocket:
                websocket.send(json.dumps({'id': 1, 'method': method, 'params': params or {}}))
                deadline = time.monotonic()+(35 if (params or {}).get('awaitPromise') else 6)
                while time.monotonic() < deadline:
                    if cancelled():
                        raise ValueError('漫游已停止。')
                    try:
                        response = json.loads(websocket.recv(timeout=0.2))
                    except TimeoutError:
                        continue
                    if response.get('id') == 1:
                        if response.get('error'):
                            raise ValueError('浏览器未能完成本次操作。')
                        return response.get('result', {})
            raise ValueError('浏览器操作超时。')

    def evaluate(self, script, cancelled=lambda: False, await_promise=False):
        result = self.command('Runtime.evaluate', {'expression': script, 'returnByValue': True,
                                                   'awaitPromise': await_promise}, cancelled)
        if result.get('exceptionDetails'):
            raise ValueError('播放器读取脚本未完成。')
        return result.get('result', {}).get('value')

    def navigate(self, url, cancelled):
        url = video_url(url)
        if not url:
            raise ValueError('仅允许打开实际 B站视频地址。')
        self.ensure(cancelled)
        self.command('Page.navigate', {'url': url}, cancelled)

    def search(self, query, cancelled):
        self.ensure(cancelled)
        url = 'https://search.bilibili.com/all?' + urlencode({'keyword': str(query)[:160]})
        self.command('Page.navigate', {'url': url}, cancelled)
        deadline = time.monotonic()+22
        while time.monotonic() < deadline:
            if cancelled():
                raise ValueError('漫游已停止。')
            try:
                status = json.loads(self.evaluate("JSON.stringify({host:location.hostname,keyword:new URLSearchParams(location.search).get('keyword'),ready:document.readyState,blocked:/请完成安全验证|验证后继续访问|访问权限受限/.test(document.body?.innerText||'')})", cancelled) or '{}')
            except ValueError:
                if cancelled():
                    raise
                time.sleep(0.3)
                continue
            if (status.get('host') == 'search.bilibili.com' and status.get('keyword') == str(query)[:160]
                    and status.get('ready') in {'interactive', 'complete'}):
                if status.get('blocked'):
                    raise ValueError('B站搜索需要安全验证，已停止漫游，请在漫游窗口手动处理。')
                rows = self.recommendations(cancelled)
                if rows:
                    return rows
            time.sleep(0.3)
        return []

    def feed(self, cancelled):
        self.ensure(cancelled)
        self.command('Page.navigate', {'url': 'https://www.bilibili.com/'}, cancelled)
        deadline = time.monotonic()+20
        while time.monotonic() < deadline:
            if cancelled():
                raise ValueError('漫游已停止。')
            try:
                status = json.loads(self.evaluate("JSON.stringify({host:location.hostname,path:location.pathname,ready:document.readyState,blocked:/请完成安全验证|验证后继续访问|访问权限受限/.test(document.body?.innerText||'')})", cancelled) or '{}')
                if (status.get('host') == 'www.bilibili.com' and status.get('path') == '/'
                        and status.get('ready') in {'interactive', 'complete'}):
                    if status.get('blocked'):
                        raise ValueError('B站推荐页需要安全验证，请在漫游窗口手动处理。')
                    rows = self.recommendations(cancelled)
                    if rows:
                        return rows
            except ValueError as error:
                if cancelled() or '验证' in str(error):
                    raise
            time.sleep(0.3)
        return []

    def favorites(self, cancelled):
        self.ensure(cancelled)
        self.command('Page.navigate', {'url': 'https://www.bilibili.com/'}, cancelled)
        deadline = time.monotonic()+20
        while time.monotonic() < deadline:
            if cancelled():
                raise ValueError('漫游已停止。')
            try:
                host = self.evaluate('location.hostname', cancelled)
                if host == 'www.bilibili.com':
                    break
            except ValueError:
                pass
            time.sleep(0.3)
        # Ask Bilibili's own authenticated page for the account identity; never
        # export cookies, copy another browser profile, or guess a user ID.
        nav = self.evaluate("""(async()=>{const c=new AbortController();const t=setTimeout(()=>c.abort(),4000);
          try {const r=await fetch('https://api.bilibili.com/x/web-interface/nav',
            {credentials:'include',signal:c.signal});const p=await r.json();
            return JSON.stringify({logged:p.data?.isLogin===true,mid:p.data?.mid||0});}
          catch(e){return JSON.stringify({logged:false,mid:0});}finally{clearTimeout(t);}})()""", cancelled, await_promise=True)
        account = json.loads(nav or '{}')
        mid = str(account.get('mid') or '')
        if not account.get('logged') or not mid.isdigit() or int(mid) <= 0:
            raise ValueError('收藏夹需要登录：请在独立漫游窗口登录B站，再发“去刷我的B站收藏”。本次没有读取收藏。')
        self.command('Page.navigate', {'url': f'https://space.bilibili.com/{mid}/favlist'}, cancelled)
        deadline = time.monotonic()+25
        while time.monotonic() < deadline:
            if cancelled():
                raise ValueError('漫游已停止。')
            try:
                location = self.evaluate('location.href', cancelled)
                if str(location).startswith(f'https://space.bilibili.com/{mid}/favlist'):
                    rows = self.recommendations(cancelled)
                    if rows:
                        return rows
            except ValueError:
                pass
            time.sleep(0.3)
        raise ValueError('收藏夹暂时未显示可播放视频，请在漫游窗口选择有内容的收藏夹后重试。')

    def player(self, cancelled):
        state = json.loads(self.evaluate(PLAYER_SCRIPT, cancelled) or '{}')
        if state.get('blocked') or state.get('login'):
            raise ValueError('视频需要登录或安全验证，已停止漫游；可在漫游窗口手动处理。')
        return state

    def play(self, cancelled):
        # Await play(), and use a real CDP click only on the player's play button
        # if autoplay is rejected. Never steal the operating system mouse.
        result = json.loads(self.evaluate("""(async () => {const v=document.querySelector('video');
          if(!v)return JSON.stringify({playing:false});v.muted=true;
          if(!v.paused)return JSON.stringify({playing:true});
          try {await v.play();return JSON.stringify({playing:!v.paused});}catch(e){
            const b=document.querySelector('.bpx-player-ctrl-play,.bilibili-player-video-btn-start');
            const r=b?.getBoundingClientRect();return JSON.stringify({playing:false,
              button:r&&r.width>0&&r.height>0?{x:r.x+r.width/2,y:r.y+r.height/2}:null});}})()""",
              cancelled, await_promise=True) or '{}')
        if result.get('button'):
            point = result['button']
            for kind in ('mousePressed', 'mouseReleased'):
                self.command('Input.dispatchMouseEvent', {'type': kind, 'button': 'left', 'clickCount': 1,
                    'x': point['x'], 'y': point['y']}, cancelled)
        return result

    def seek(self, seconds, cancelled):
        import math
        seconds = float(seconds)
        if not math.isfinite(seconds) or seconds < 0:
            raise ValueError('跳转时间无效。')
        result = self.evaluate("""(() => {const v=document.querySelector('video');
          if(!v||!Number.isFinite(v.duration)||v.duration<=1)return JSON.stringify({ok:false});
          const target=Math.max(0,Math.min(v.duration-1,SECONDS));
          v.currentTime=target;v.muted=true;v.play().catch(()=>{});
          return JSON.stringify({ok:true,target,duration:v.duration});})()""".replace('SECONDS', json.dumps(seconds)), cancelled)
        state = json.loads(result or '{}')
        if not state.get('ok'):
            raise ValueError('播放器暂时不能跳转。')
        return state

    def frame(self, state, cancelled):
        rect = state.get('rect') or {}
        if rect.get('width', 0) < 100 or rect.get('height', 0) < 70:
            raise ValueError('播放器画面未显示。')
        result = self.command('Page.captureScreenshot', {'format': 'jpeg', 'quality': 75,
            'captureBeyondViewport': False, 'clip': {'x': rect['x']+state.get('scroll_x', 0),
            'y': rect['y']+state.get('scroll_y', 0), 'width': rect['width'], 'height': rect['height'], 'scale': 1}}, cancelled)
        raw = base64.b64decode(result.get('data', ''), validate=True)
        if not raw or len(raw) > 4*1024*1024:
            raise ValueError('播放器截图无效或过大。')
        from PySide6.QtCore import QBuffer, QIODevice, Qt
        from PySide6.QtGui import QImageReader
        buffer = QBuffer()
        buffer.setData(raw)
        buffer.open(QIODevice.OpenModeFlag.ReadOnly)
        reader = QImageReader(buffer)
        size = reader.size()
        if size.width() <= 0 or size.height() <= 0 or size.width()*size.height() > 16_000_000:
            raise ValueError('截图尺寸无效。')
        image = reader.read()
        if image.isNull():
            raise ValueError('播放器截图解码失败。')
        if max(image.width(), image.height()) > 1024:
            image = image.scaled(1024, 1024, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        folder = self.root / 'data/attachments/video_cache/browser_frames'
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / (uuid.uuid4().hex+'.jpg')
        if not image.save(str(path), 'JPEG', 78):
            raise ValueError('播放器截图保存失败。')
        relative = path.relative_to(self.root).as_posix()
        return {'path': relative, 'time_seconds': round(float(state.get('current_time', 0)), 2)}

    def recommendations(self, cancelled):
        data = self.evaluate("""JSON.stringify([...document.querySelectorAll('a[href*="/video/BV"]')]
          .map(a=>{const c=a.closest('.bili-video-card,.video-page-card-small,.video-item,.small-item,.video-card,.recommend-video-card')||a.parentElement;
            const title=c?.querySelector('h3,.bili-video-card__info--tit,.title')||c?.querySelector('a[href*="/video/BV"][title]');
            const author=c?.querySelector('.bili-video-card__info--author,.upname,.up-name,.name');
            const duration=c?.querySelector('.bili-video-card__stats__duration,.duration');
            return {url:a.href,title:(a.title||title?.title||title?.innerText||a.innerText||a.querySelector('img')?.alt||'').trim().slice(0,200),
              author:(author?.innerText||'').trim().slice(0,80),duration:(duration?.innerText||'').trim().slice(0,30),
              description:(c?.innerText||'').trim().slice(0,350),source:'浏览器实际视频卡片'};})
          .filter(x=>x.title).slice(0,100))""", cancelled)
        rows, seen = [], set()
        for row in json.loads(data or '[]'):
            url = video_url(row.get('url', ''))
            if url and url not in seen:
                seen.add(url)
                rows.append({**row, 'url': url})
        return rows[:20]

    def pause(self):
        if self.target_id and (self.endpoint or self.mode == 'extension'):
            try:
                self.evaluate("(() => {document.querySelectorAll('video').forEach(v=>v.pause());return true;})()")
            except Exception:
                pass

    def close(self):
        if self.mode == 'extension':
            try:
                if self.target_id and self.link.connection:
                    self.link.request('Link.close', target=self.target_id)
            except Exception:
                pass
            self.target_id = ''
            return
        if self.endpoint and self.target_id:
            try:
                self.command('Target.closeTarget', {'targetId': self.target_id})
            except Exception:
                pass
        elif self.process is not None and self.process.poll() is None:
            # Startup was cancelled before an owned target could be identified.
            # This handle belongs only to the browser process we just launched.
            try:
                self.process.terminate()
            except OSError:
                pass
        self.target_id = ''

    def stop_owned_process(self):
        """Only close a headless process created by this particular object."""
        if self.background and self.process is not None and self.process.poll() is None:
            try:
                self.process.terminate()
                self.process.wait(timeout=4)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2)
            self.endpoint = self.target_id = ''
