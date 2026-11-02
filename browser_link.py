"""Opt-in extension transport for a tab in the user's already logged-in browser."""
from __future__ import annotations

import json
from pathlib import Path
import re
import secrets
import threading
import time
import uuid
from urllib.parse import urlparse, parse_qs
from bilibili_api import REQUEST_SCRIPT


_COOKIE_STATEMENT = "const csrf=document.cookie.split(';').map(p=>p.trim()).find(p=>p.startsWith('bili_jct='))?.slice(9);"
_EXTENSION_API = REQUEST_SCRIPT.replace('const request=__REQUEST__;', 'const request=params;').replace(
    _COOKIE_STATEMENT, "const csrf=(await chrome.cookies.get({url:'https://www.bilibili.com/',name:'bili_jct'}))?.value;")


EXTENSION_WORKER = r'''
importScripts('config.js');
let socket, ping, retry, attached = new Set();
const allowed = u => {try {const p=new URL(u);return p.protocol==='https:' &&
  ['www.bilibili.com','bilibili.com','search.bilibili.com','space.bilibili.com'].includes(p.hostname);}catch{return false;}};
let owned = new Set();
const restored = chrome.storage.session.get('owned').then(v=>{owned=new Set(v.owned||[]);});
const save = () => chrome.storage.session.set({owned:[...owned]});
async function tabFor(id) {
  await restored;
  const n=Number(String(id).replace('tab:',''));
  if(!owned.has(n)) throw new Error('不是鲸伴创建的标签页');
  const tab=await chrome.tabs.get(n);
  if(!allowed(tab.pendingUrl||tab.url||'')) throw new Error('标签页已离开B站，连接已让位');
  return n;
}
async function command(message) {
  const {method,params={}}=message;
  if(method==='Bilibili.api') {
    if(!['identity','video','comments','comment','like','unlike'].includes(params.step))throw Error('未知的B站接口');
    if(params.step==='video'&&!/^BV[0-9a-zA-Z]{10}$/.test(params.bvid||''))throw Error('视频编号无效');
    if(['comments','comment','like','unlike'].includes(params.step)&&!/^\d{1,20}$/.test(params.aid||''))throw Error('视频编号无效');
    if(params.step==='comment'&&(typeof params.text!=='string'||!params.text.trim()||params.text.length>1000))throw Error('评论正文无效');
    return JSON.parse(await __BILIBILI_API__);
  }
  if(method==='Link.ensure') {
    await restored;
    for(const n of owned) {
      try {const t=await chrome.tabs.get(n);if(allowed(t.pendingUrl||t.url||''))return {id:'tab:'+n};}catch{}
    }
    const tab=await chrome.tabs.create({url:'https://www.bilibili.com/',active:false});
    owned.add(tab.id);await save();return {id:'tab:'+tab.id};
  }
  const n=await tabFor(message.target);
  if(method==='Link.close'||method==='Target.closeTarget') {
    owned.delete(n);await save();await chrome.tabs.remove(n);attached.delete(n);return {success:true};
  }
  if(method==='Page.bringToFront') {
    const t=await chrome.tabs.update(n,{active:true});await chrome.windows.update(t.windowId,{focused:true});return {};
  }
  if(method==='Page.navigate'&&!allowed(params.url))throw new Error('仅能打开B站页面');
  if(!['Runtime.evaluate','Page.navigate','Page.captureScreenshot','Input.dispatchMouseEvent'].includes(method))
    throw new Error('未允许的浏览器命令');
  if(!attached.has(n)) {await chrome.debugger.attach({tabId:n},'1.3');attached.add(n);}
  return await chrome.debugger.sendCommand({tabId:n},method,params);
}
function connect() {
  clearTimeout(retry);
  if(socket && [WebSocket.CONNECTING,WebSocket.OPEN].includes(socket.readyState))return;
  socket=new WebSocket(JINGBAN_LINK);
  socket.onopen=()=>{socket.send(JSON.stringify({hello:true,background_bilibili:true,browser:navigator.userAgent.includes('Edg/')?'Edge':'Chrome'}));
    clearInterval(ping);ping=setInterval(()=>{if(socket?.readyState===WebSocket.OPEN)socket.send('{"ping":true}');},20000);};
  socket.onmessage=async e=>{
    let m;try{m=JSON.parse(e.data);}catch{return;}
    if(!m.id)return;
    let reply;
    try{reply={id:m.id,result:await command(m)};}catch(error){reply={id:m.id,error:String(error.message||error).slice(0,200)};}
    if(socket?.readyState===WebSocket.OPEN)socket.send(JSON.stringify(reply));
  };
  socket.onclose=()=>{clearInterval(ping);for(const n of attached)chrome.debugger.detach({tabId:n}).catch(()=>{});
    attached.clear();retry=setTimeout(connect,4000);};
  socket.onerror=()=>socket.close();
}
chrome.debugger.onDetach.addListener(source=>attached.delete(source.tabId));
chrome.tabs.onRemoved.addListener(n=>{owned.delete(n);attached.delete(n);save();});
chrome.runtime.onStartup.addListener(connect);
chrome.runtime.onInstalled.addListener(connect);
chrome.action.onClicked.addListener(connect);
chrome.alarms.create('reconnect',{periodInMinutes:0.5});
chrome.alarms.onAlarm.addListener(a=>{if(a.name==='reconnect')connect();});
connect();
'''.replace('__BILIBILI_API__', _EXTENSION_API)


class BrowserLink:
    def __init__(self, root):
        self.root = Path(root)
        self.server = self.connection = None
        self.pending = {}
        self.guard, self.write_lock = threading.RLock(), threading.Lock()
        self.browser = ''
        self.background_bilibili = False
        self.error = ''

    def start(self):
        with self.guard:
            self._start()

    def _start(self):
        if self.server:
            return
        from websockets.sync.server import serve
        folder = self.root/'data/browser-link'
        folder.mkdir(parents=True, exist_ok=True)
        path = folder/'connection.json'
        if folder.is_symlink() or folder.resolve() != folder.absolute() or path.is_symlink():
            raise ValueError('浏览器连接配置目录异常。')
        try:
            config = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            config = {}
        token, port = str(config.get('token') or ''), config.get('port', 0)
        if not re.fullmatch(r'[a-zA-Z0-9_-]{40,100}', token):
            token = secrets.token_urlsafe(36)
        if type(port) is not int or not (1024 <= port <= 65535):
            port = 0
        self.token = token
        try:
            self.server = serve(self.handle, '127.0.0.1', port, max_size=12*1024*1024,
                                open_timeout=3, close_timeout=1, process_request=self.authorize)
        except OSError:
            raise ValueError('日常浏览器连接端口被占用，请关闭同目录的其他鲸伴实例后重试。') from None
        self.port = self.server.socket.getsockname()[1]
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps({'port': self.port, 'token': token}), encoding='utf-8')
        temporary.replace(path)
        threading.Thread(target=self.server.serve_forever, daemon=True, name='jingban-browser-link').start()

    def authorize(self, connection, request):
        origin = request.headers.get('Origin', '')
        token = parse_qs(urlparse(request.path).query).get('token', [''])[0]
        if not re.fullmatch(r'chrome-extension://[a-p]{32}', origin) or not secrets.compare_digest(token, self.token):
            return connection.respond(403, 'Not paired\n')

    def export(self):
        self.start()
        folder = self.root/'data/browser-extension'
        folder.mkdir(parents=True, exist_ok=True)
        if folder.is_symlink() or folder.resolve() != folder.absolute():
            raise ValueError('浏览器扩展目录异常。')
        manifest = {'manifest_version': 3, 'name': '鲸伴 · 浏览器会话连接', 'version': '1.1.0',
            'minimum_chrome_version': '116', 'description': '沿用本浏览器已有的B站登录；后台评论不打开视频标签页。',
            'permissions': ['debugger', 'storage', 'alarms', 'cookies'],
            'host_permissions': ['https://*.bilibili.com/*'],
            'background': {'service_worker': 'worker.js'}, 'action': {'default_title': '连接鲸伴'}}
        files = {'manifest.json': json.dumps(manifest, ensure_ascii=False, indent=2),
                 'worker.js': EXTENSION_WORKER,
                 'config.js': 'const JINGBAN_LINK='+json.dumps(f'ws://127.0.0.1:{self.port}/?token={self.token}')+';',
                 '安装说明.txt': '在已经登录B站的同一个浏览器及个人资料中安装：\n'
                    '1. Edge打开 edge://extensions；Chrome打开 chrome://extensions。\n'
                    '2. 开启开发者模式，点“加载解压缩的扩展”，选择本文件夹。\n'
                    '3. 保持原来登录B站的同一个浏览器资料打开，鲸伴会自动连接。无需再次登录B站。\n'
                    '4. “鲸鱼心跳→浏览与活动”显示已连接后即可后台评论，无需打开视频页面。\n'
                    'B站请求在扩展内使用当前会话，登录Cookie和校验值不返回鲸伴；播放器控制仍仅操作鲸伴创建的标签页。\n'
                    '首次授权安装后，下一次启动会重新连接；若未连上可点扩展图标。\n'
                    '扩展与本机目录配对，请勿把本文件夹发给别人。安装后更新扩展需在扩展管理页点重新加载。\n'}
        for name, content in files.items():
            path = folder/name
            if path.is_symlink():
                raise ValueError('扩展文件位置异常。')
            path.write_text(content, encoding='utf-8')
        return folder

    def handle(self, connection):
        token = parse_qs(urlparse(connection.request.path).query).get('token', [''])[0]
        if not secrets.compare_digest(token, self.token):
            connection.close(1008, 'Not paired')
            return
        with self.guard:
            if self.connection:
                connection.close(1008, 'Another browser is connected')
                return
            self.connection = connection
        try:
            for raw in connection:
                value = json.loads(raw)
                if not isinstance(value, dict):
                    continue
                if value.get('hello'):
                    self.browser = 'Edge' if value.get('browser') == 'Edge' else 'Chrome'
                    self.background_bilibili = value.get('background_bilibili') is True
                with self.guard:
                    request = self.pending.get(value.get('id'))
                    if request:
                        request['reply'] = value
                        request['ready'].set()
        except Exception:
            pass
        finally:
            with self.guard:
                if self.connection is connection:
                    self.connection, self.browser = None, ''
                    self.background_bilibili = False
                    for request in self.pending.values():
                        request['reply'] = {'error': '浏览器扩展连接已断开；未确认的提交不要重复发送。'}
                        request['ready'].set()

    def request(self, method, params=None, target='', cancelled=lambda: False, *, expected_connection=None):
        self.start()
        identity = uuid.uuid4().hex
        request = {'ready': threading.Event()}
        with self.guard:
            connection = self.connection
            if not connection:
                raise ValueError('日常浏览器尚未连接：请安装连接扩展并保持该浏览器打开；不会另开未登录窗口。')
            if expected_connection is not None and connection is not expected_connection:
                raise ValueError('已连接的浏览器发生变化，这次没有继续操作。')
            self.pending[identity] = request
        try:
            with self.write_lock:
                if cancelled():
                    raise ValueError('浏览器操作已取消。')
                connection.send(json.dumps({'id': identity, 'method': method, 'params': params or {}, 'target': target}))
            deadline = time.monotonic()+(35 if (params or {}).get('awaitPromise') else 10)
            while not request['ready'].wait(0.1):
                if cancelled():
                    raise ValueError('浏览器操作已取消；已提交的写入请先核对。')
                if time.monotonic() >= deadline:
                    raise ValueError('浏览器操作未返回；已提交的写入请先核对，不自动重试。')
            reply = request.get('reply') or {}
            if reply.get('error'):
                raise ValueError(str(reply['error'])[:200])
            return reply.get('result') or {}
        finally:
            with self.guard:
                self.pending.pop(identity, None)

    def stop(self):
        if self.connection:
            self.connection.close(1001, 'App closed')
        if self.server:
            self.server.shutdown()
            self.server = None
