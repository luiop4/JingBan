"""Optional Cordis host, kept outside the GUI process and installed on demand."""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import tempfile
import uuid
import time
import zipfile

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal

from dsh_packages import (CORE_PACKAGES, PET_WEB_DEPENDENCIES, PET_WEB_FILES, checked_dir, cancelled, download, download_npm,
                          package_source, bounded_copy, write_json, read_json, safe_name, runtime_dependencies)

NODE_VERSION = 'v24.22.1'

# Generated under data/dsh/runtime. Package code is loaded only after explicit enable.
HOST_SOURCE = r'''import { createRequire, registerHooks } from 'node:module';
import { pathToFileURL } from 'node:url';
import { createInterface } from 'node:readline';
import { inspect } from 'node:util';
import { readFileSync } from 'node:fs';
import { request as httpRequest } from 'node:http';

const output = process.stdout.write.bind(process.stdout);
function send(type, value) {
  output('\u001eJBDSH ' + JSON.stringify({type, value}) + '\n');
}
for (const name of ['log', 'info', 'warn', 'error', 'debug']) {
  console[name] = (...args) => send('log', args.map(x => typeof x === 'string' ? x : inspect(x, {depth: 3})).join(' ').slice(0, 12000));
}
// The original standalone plugin owns the windows and rendering. This bridge only
// posts completed local replies to its authenticated, loopback-only public API.
class PetReplyBridge {
  constructor(interfaceFile, enabled) {
    this.interfaceFile = interfaceFile;
    this.enabled = enabled;
    this.revision = 0;
    this.requests = new Set();
    this.shown = new Map();
    this.queue = Promise.resolve();
    this.timer = null;
    this.closed = false;
  }
  api(path, body) {
    const state = JSON.parse(readFileSync(this.interfaceFile, 'utf8'));
    if (state.pid !== process.pid || !Number.isInteger(state.port) || state.port < 1 || state.port > 65535
        || typeof state.token !== 'string' || !/^[A-Za-z0-9_-]{43}$/.test(state.token)) {
      throw new Error('桌宠本机接口状态已失效，请重新启用插件。');
    }
    return new Promise((resolve, reject) => {
      const data = body === undefined ? undefined : JSON.stringify(body);
      const req = httpRequest({hostname: '127.0.0.1', port: state.port,
        path: '/dsh-pet-7340/' + path, method: data === undefined ? 'GET' : 'POST',
        headers: {'x-dsh-pet-token': state.token, ...(data === undefined ? {} : {
          'content-type': 'application/json', 'content-length': Buffer.byteLength(data)})}}, res => {
        const chunks = [];
        let size = 0;
        res.on('data', chunk => {
          size += chunk.length;
          if (size > 512 * 1024) req.destroy(new Error('桌宠接口响应超过大小限制。'));
          else chunks.push(chunk);
        });
        res.on('error', reject);
        res.on('end', () => {
          try {
            const value = JSON.parse(Buffer.concat(chunks).toString('utf8'));
            if (res.statusCode !== 200 || value?.ok === false) {
              // Never print URLs, headers, API responses, or authentication tokens.
              throw new Error('桌宠接口拒绝操作（' + res.statusCode + ' / ' +
                String(value?.reason || 'request-failed').replace(/[^a-z-]/g, '').slice(0, 60) + '）。');
            }
            resolve(value);
          } catch (error) { reject(error); }
        });
      });
      this.requests.add(req);
      const timeout = setTimeout(() => req.destroy(new Error('桌宠本机接口请求超时。')), 3000);
      req.on('error', reject);
      req.on('close', () => { clearTimeout(timeout); this.requests.delete(req); });
      req.end(data);
    });
  }
  invalidate() {
    ++this.revision;
    clearTimeout(this.timer);
    this.timer = null;
    for (const req of this.requests) req.destroy(new Error('reply-replaced'));
  }
  schedule(task) {
    const revision = this.revision;
    this.queue = this.queue.catch(() => {}).then(async () => {
      if (this.closed || revision !== this.revision || stopping) return;
      try { await task(revision); }
      catch {
        if (!this.closed && revision === this.revision && !stopping) {
          send('log', '鲸伴回复同步失败：请检查原插件日志、桌面显示模式或占用锁；鲸伴聊天不受影响。');
        }
      }
    });
  }
  async clear(revision) {
    if (!this.shown.size) return;
    const state = await this.api('state');
    for (const [pet, text] of [...this.shown]) {
      if (revision !== this.revision || this.closed || stopping) return;
      // The original plugin may have shown its own chat/whisper in the meantime.
      if (state?.pets?.[pet]?.say?.data?.text !== text) {
        this.shown.delete(pet);
        continue;
      }
      try { await this.api('bubble/clear?pet=' + encodeURIComponent(pet) + '&surface=any', {}); }
      catch { /* Removed or hidden pets may no longer accept a clear request. */ }
      this.shown.delete(pet);
    }
  }
  accept(name, value) {
    if (this.closed) return;
    if (name === 'settings') {
      this.enabled = value === true;
      if (this.enabled) return;
    } else if (name === 'data_cleared') {
      // Clear only bubbles this bridge displayed; never erase the plugin's own chat.
    } else if (name === 'message' && this.enabled && value?.source === 'local') {
      if (value.role === 'assistant' && typeof value.content === 'string' && value.content.trim()) {
        this.invalidate();
        const chars = Array.from(value.content.trim());
        const pages = [];
        for (let i = 0; i < chars.length; i += 120) pages.push(chars.slice(i, i + 120).join(''));
        this.schedule(revision => this.page(pages, 0, revision));
        return;
      }
      if (value.role !== 'user') return;
    } else return;
    this.invalidate();
    this.schedule(revision => this.clear(revision));
  }
  async page(pages, index, revision) {
    const config = await this.api('config');
    if (revision !== this.revision || this.closed || stopping) return;
    const pets = [...new Set(Object.values(config).flatMap(entry =>
      Array.isArray(entry?.pets) ? entry.pets : []).filter(pet =>
        pet && typeof pet.id === 'string' && ['desktop', 'web', 'both'].includes(pet.display)).map(pet => pet.id))];
    if (!pets.length) {
      send('log', '鲸伴回复未显示：没有启用显示的桌宠，请打开插件界面或恢复桌面显示。');
      return;
    }
    const text = (pages.length > 1 ? `【${index + 1}/${pages.length}】\n` : '') + pages[index];
    const duration = Math.min(20000, Math.max(8000, Array.from(pages[index]).length * 100));
    for (const pet of pets) {
      if (revision !== this.revision || this.closed || stopping) return;
      this.shown.set(pet, text);
      try { await this.api('broadcast?pet=' + encodeURIComponent(pet) + '&surface=any',
        {text, duration, anim: false}); }
      catch (error) {
        if (revision !== this.revision || this.closed || stopping) return;
        send('log', '一只桌宠未接受鲸伴回复气泡，请检查原插件的桌面显示和占用锁。');
      }
    }
    if (index + 1 < pages.length && revision === this.revision && !this.closed && !stopping) {
      this.timer = setTimeout(() => this.schedule(next => this.page(pages, index + 1, next)), duration);
    }
  }
  dispose() { this.closed = true; this.invalidate(); this.shown.clear(); }
}
let root, fiber, petBridge, webCompat, stopping = false, loaded = false, mode = 'cordis';
async function stop(code = 0) {
  if (stopping) return;
  stopping = true;
  petBridge?.dispose();
  webCompat?.close();
  if (mode === 'standalone') {
    if (process.listenerCount('SIGTERM')) process.emit('SIGTERM');
    setTimeout(() => process.exit(code), 3500);
    return;
  }
  const limit = setTimeout(() => process.exit(code), 1000);
  try { if (fiber) await fiber.dispose(); if (root) await root.fiber.dispose(); }
  catch (error) { send('log', String(error)); }
  await new Promise(resolve => output('', resolve));
  clearTimeout(limit);
  process.exit(code);
}
function fail(error) { send('error', String(error?.stack || error).slice(0, 14000)); void stop(1); }
process.on('uncaughtException', fail);
process.on('unhandledRejection', fail);

async function start(request) {
  if (loaded || root) throw new Error('插件已经启动。');
  const req = createRequire(import.meta.url);
  const dependencyParent = pathToFileURL(request.dependencyRoot + '/package.json').href;
  const shared = ['@deepseek-ai/cordis', '@deepseek-ai/cosmokit', '@standard-schema/spec'];
  const resolved = new Map(shared.map(name => [name, pathToFileURL(req.resolve(name)).href]));
  // Resolve only the three pinned shared packages; plugin-local imports keep Node semantics.
  registerHooks({ resolve(specifier, context, nextResolve) {
    if (resolved.has(specifier)) {
      return nextResolve(resolved.get(specifier), context);
    }
    if (shared.some(x => specifier.startsWith(x + '/'))) {
      return nextResolve(new URL('./node_modules/' + specifier, import.meta.url).href, context);
    }
    try { return nextResolve(specifier, context); }
    catch (error) {
      if (!['ERR_MODULE_NOT_FOUND', 'MODULE_NOT_FOUND'].includes(error.code) || specifier.startsWith('.') || specifier.startsWith('/') || specifier.includes(':')) throw error;
      return nextResolve(specifier, {...context, parentURL: dependencyParent});
    }
  }});
  mode = request.mode || 'cordis';
  if (mode === 'standalone') {
    if (request.petReplyBridge && request.interfaceFile) {
      petBridge = new PetReplyBridge(request.interfaceFile, request.replyBubbles !== false);
    }
    process.argv = [process.execPath, request.entry, ...(request.arguments || [])];
    await import(pathToFileURL(request.entry).href);
    if (request.webInterface) {
      const {createWeb} = await import(pathToFileURL(request.webHost).href);
      webCompat = await createWeb(request, null, send);
    }
    loaded = true;
    if (request.interfaceFile) {
      const timer = setInterval(() => {
        try {
          const state = JSON.parse(readFileSync(request.interfaceFile, 'utf8'));
          if (state.pid === process.pid) {
            clearInterval(timer);
            send('ready', '原版插件服务已启动；桌面运行库的下载及窗口状态见原插件日志。');
            if (petBridge) send('log', '鲸伴新回复气泡同步' + (petBridge.enabled ? '已开启。' : '已关闭，可在启动设置中开启。'));
          }
        } catch {}
      }, 250);
    } else send('ready', '原版插件独立入口已加载。');
    return;
  }
  const { Context, Inject } = await import('@deepseek-ai/cordis');
  root = new Context();
  if (request.webInterface) {
    const {createWeb} = await import(pathToFileURL(request.webHost).href);
    webCompat = await createWeb(request, root, send);
  }
  root.logger.exporter({export(message) {
    send('log', '[' + message.type + '][' + message.name + '] ' + message.args.map(x => inspect(x, {depth: 2})).join(' ').slice(0, 12000));
  }});
  const module = await import(pathToFileURL(request.entry).href);
  const plugin = module.default || module;
  const dependencies = Object.keys(Inject.resolve(plugin.inject));
  const missing = dependencies.filter(name => !root.get(name));
  if (missing.length) throw new Error('尚未适配 DSH 服务：' + missing.join(', '));
  fiber = root.plugin(plugin, request.config || {});
  await Promise.race([fiber.await(), new Promise((_, reject) => setTimeout(() => reject(new Error('插件启动超过 10 秒，可能等待尚未适配的服务。')), 10000))]);
  if (fiber.state !== 2) throw new Error('插件没有进入运行状态，请检查 inject 服务依赖。');
  loaded = true;
  send('ready', 'Cordis 4.0.4 插件已启动');
  setInterval(() => {
    for (const runtime of root.registry.values()) {
      for (const child of runtime.fibers) {
        if (child.state === 3) return fail(new Error('插件或其子插件运行失败，请查看前面的日志。'));
        if (child.state === 0) return fail(new Error('子插件正在等待未适配的服务，已停止该插件。'));
      }
    }
  }, 1000);
}
const input = createInterface({input: process.stdin, crlfDelay: Infinity});
let chain = Promise.resolve();
input.on('line', line => {
  if (line.length > 262144) return fail(new Error('输入事件超过大小限制。'));
  let request;
  try { request = JSON.parse(line); } catch (error) { return fail(error); }
  if (request.type === 'stop') return void stop();
  if (request.type === 'balance-result') return webCompat?.reply(request);
  chain = chain.then(async () => {
    if (request.type === 'start') return start(request);
    if (request.type === 'pet-restore') {
      try { await webCompat?.restore(); } catch { send('log', '恢复桌面显示失败，请查看插件记录或重新启用。'); }
      return;
    }
    if (request.type === 'bridge-settings') return petBridge?.accept('settings', request.enabled);
    if (request.type === 'event' && loaded && petBridge && /^jingban\/(message|data_cleared)$/.test(request.name)) {
      petBridge.accept(request.name.slice('jingban/'.length), request.value);
      return;
    }
    if (request.type === 'event' && loaded && root && /^jingban\/(message|voice_state|chat_state|data_cleared)$/.test(request.name)) {
      root.emit(request.name, request.value);
    }
  }).catch(fail);
});
input.on('close', () => void stop());
'''


class ProcessJob:
    """Assign Node before sending its plugin entrypoint; own all descendants."""
    def __init__(self, pid):
        self.handle = None
        if os.name != 'nt':
            return
        import ctypes
        from ctypes import wintypes as w
        from onebot_process import _ExtendedLimits
        self.api = api = ctypes.WinDLL('kernel32', use_last_error=True)
        api.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
        api.CreateJobObjectW.restype = w.HANDLE
        api.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
        api.SetInformationJobObject.restype = w.BOOL
        api.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
        api.OpenProcess.restype = w.HANDLE
        api.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
        api.AssignProcessToJobObject.restype = w.BOOL
        api.CloseHandle.argtypes = [w.HANDLE]
        api.CloseHandle.restype = w.BOOL
        self.handle = api.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        process = None
        try:
            limits = _ExtendedLimits()
            limits.BasicLimitInformation.LimitFlags = 0x2000
            if not api.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
                raise ctypes.WinError(ctypes.get_last_error())
            process = api.OpenProcess(0x0100 | 0x0001, False, int(pid))
            if not process or not api.AssignProcessToJobObject(self.handle, process):
                raise ctypes.WinError(ctypes.get_last_error())
        except Exception:
            self.close()
            raise
        finally:
            if process:
                api.CloseHandle(process)

    def close(self):
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None


def runtime_directory(root):
    return Path(root) / 'data' / 'dsh' / 'runtime'


def runtime_ready(root):
    directory = runtime_directory(root)
    return (directory / 'node.exe').is_file() and (directory / 'node_modules/npm/bin/npm-cli.js').is_file() and (directory / 'ready.json').is_file() and all(
        (directory / 'node_modules' / name / 'package.json').is_file() for name in CORE_PACKAGES)


def install_runtime(root, progress=lambda _: None, check=lambda: False):
    storage = checked_dir(root, 'data/dsh')
    target = storage / 'runtime'
    if target.resolve() != target:
        raise ValueError('运行环境目录不能是链接。')
    with tempfile.TemporaryDirectory(prefix='.runtime-', dir=storage) as scratch:
        scratch = Path(scratch)
        stage = scratch / 'ready'
        stage.mkdir()
        progress('正在获取 Node.js 官方文件校验信息…')
        sums = scratch / 'SHASUMS256.txt'
        download(f'https://nodejs.org/dist/{NODE_VERSION}/SHASUMS256.txt', sums, progress, check, 1024**2)
        relative = f'node-{NODE_VERSION}-win-x64.zip'
        wanted = next((line.split()[0] for line in sums.read_text().splitlines()
                       if line.split()[-1].lstrip('*') == relative), None)
        if not wanted:
            raise ValueError('官方清单没有 Windows x64 Node.js。')
        progress('正在下载共享 Node.js / npm 运行环境…')
        node_archive = scratch / relative
        download(f'https://nodejs.org/dist/{NODE_VERSION}/{relative}', node_archive, progress, check, 192 * 1024**2)
        if hashlib.sha256(node_archive.read_bytes()).hexdigest() != wanted:
            raise ValueError('Node.js SHA-256 校验失败。')
        with zipfile.ZipFile(node_archive) as archive:
            prefix = f'node-{NODE_VERSION}-win-x64/'
            total = 0
            for member in archive.infolist():
                cancelled(check)
                if member.is_dir() or not member.filename.startswith(prefix):
                    continue
                name = safe_name(member.filename[len(prefix):])
                if name not in ('node.exe', 'LICENSE') and not name.startswith('node_modules/npm/'):
                    continue
                total += member.file_size
                if total > 256 * 1024**2:
                    raise ValueError('Node.js 运行环境超过解压上限。')
                path = stage / name
                path.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, path.open('wb') as destination:
                    shutil.copyfileobj(source, destination)
        for name, (version, integrity) in CORE_PACKAGES.items():
            cancelled(check)
            progress('正在安装共享依赖：' + name)
            archive = scratch / (name.rsplit('/', 1)[-1] + '.tgz')
            download_npm(name, version, integrity, archive, progress, check)
            with package_source(archive, scratch / ('unpack-' + name.rsplit('/', 1)[-1]), check) as source:
                bounded_copy(source, stage / 'node_modules' / name, check)
        (stage / 'host.mjs').write_text(HOST_SOURCE, encoding='utf-8')
        write_json(stage / 'ready.json', {'node': NODE_VERSION, 'cordis': '4.0.4', 'format': 2})
        cancelled(check)
        previous = None
        if target.exists():
            removed = checked_dir(root, 'data/dsh/removed')
            previous = removed / ('runtime-' + uuid.uuid4().hex[:12])
            target.rename(previous)
        try:
            stage.rename(target)
        except Exception:
            if previous:
                previous.rename(target)
            raise
    return {'message': '共享 Node.js / Cordis 运行环境安装完成。'}


def dependency_directory(root, key, metadata):
    deps = runtime_dependencies(metadata)
    content = json.dumps({'dependencies': deps, 'node': NODE_VERSION, 'cordis': '4.0.4'}, sort_keys=True).encode()
    return Path(root) / 'data/dsh/dependencies' / (key + '-' + hashlib.sha256(content).hexdigest()[:16])


def missing_dependency_files(directory, metadata):
    directory = Path(directory)
    deps = runtime_dependencies(metadata)
    required = [name + '/package.json' for name in deps]
    if metadata.get('name') == 'dsh-pet':
        required.extend(PET_WEB_FILES)
    missing = []
    for name in required:
        path = directory / 'node_modules' / name
        try:
            if not path.is_file() or path.stat().st_size == 0:
                missing.append(name)
        except OSError:
            missing.append(name)
    if metadata.get('name') == 'dsh-pet':
        for name, version in PET_WEB_DEPENDENCIES.items():
            try:
                info = read_json(directory / 'node_modules' / name / 'package.json')
                if info.get('name') != name or info.get('version') != version:
                    missing.append(name + '（兼容版本不匹配）')
            except (OSError, ValueError):
                missing.append(name + '/package.json')
    return list(dict.fromkeys(missing))


def dependencies_ready(root, key, metadata):
    directory = dependency_directory(root, key, metadata)
    try:
        marker = read_json(directory / 'ready.json')
        return marker.get('format') in (1, 2) and not missing_dependency_files(directory, metadata)
    except (OSError, ValueError):
        return False


def run_npm(root, directory, progress, check):
    """No shell or lifecycle scripts; suspended launch assigns the entire npm tree."""
    import ctypes
    from ctypes import wintypes as w
    import msvcrt
    from onebot_process import OneBotProcess
    runtime = runtime_directory(root)
    environment = dict(os.environ)
    for key in list(environment):
        if key.upper().startswith('NPM_CONFIG_') or key.upper() in ('NODE_OPTIONS', 'NODE_PATH'):
            environment.pop(key, None)
    environment['PATH'] = str(runtime) + os.pathsep + environment.get('PATH', '')
    environment['NPM_CONFIG_CACHE'] = str(checked_dir(root, 'data/dsh/npm-cache'))
    environment['NPM_CONFIG_USERCONFIG'] = str(Path(directory) / '.npmrc')
    Path(environment['NPM_CONFIG_USERCONFIG']).write_text('registry=https://registry.npmjs.org/\nignore-scripts=true\n', encoding='utf-8')
    command = [str(runtime / 'node.exe'), str(runtime / 'node_modules/npm/bin/npm-cli.js'),
               'install', '--omit=dev', '--ignore-scripts', '--legacy-peer-deps', '--no-audit', '--no-fund',
               '--registry=https://registry.npmjs.org/', '--strict-ssl=true', '--fetch-retries=1', '--fetch-timeout=30000']
    try:
        process = OneBotProcess(command, directory, environment)
    except Exception as error:
        raise ValueError('无法启动插件依赖安装进程：' + str(error).replace('OneBot', '插件')) from error
    api = process.kernel
    api.PeekNamedPipe.argtypes = [w.HANDLE, ctypes.c_void_p, w.DWORD, ctypes.c_void_p, ctypes.POINTER(w.DWORD), ctypes.c_void_p]
    api.PeekNamedPipe.restype = w.BOOL
    api.GetExitCodeProcess.argtypes = [w.HANDLE, ctypes.POINTER(w.DWORD)]
    api.GetExitCodeProcess.restype = w.BOOL
    handle = msvcrt.get_osfhandle(process.output.fileno())
    output = ''
    started = time.monotonic()
    def drain():
        nonlocal output
        available = w.DWORD()
        if api.PeekNamedPipe(handle, None, 0, None, ctypes.byref(available), None) and available.value:
            chunk = os.read(process.output.fileno(), min(available.value, 65536)).decode('utf-8', errors='replace')
            output = (output + chunk)[-16000:]
            progress('npm：' + chunk.strip()[-1200:])
    try:
        while process.active():
            cancelled(check)
            if time.monotonic() - started > 600:
                raise ValueError('依赖安装超过 10 分钟，已停止；可稍后重试。')
            drain()
            time.sleep(.1)
        drain()
        code = w.DWORD()
        if not api.GetExitCodeProcess(process.process, ctypes.byref(code)) or code.value:
            raise ValueError('npm 依赖安装失败：\n' + output[-6000:])
    finally:
        process.close()
        process.output.close()


def prepare_plugin(root, key, progress=lambda _: None, check=lambda: False, force=False):
    if not re.fullmatch('[0-9a-f]{20}', key):
        raise ValueError('插件标识无效。')
    if not runtime_ready(root):
        install_runtime(root, progress, check)
    package = Path(root) / 'data/dsh/packages' / key / 'package'
    metadata = read_json(package / 'package.json')
    target = dependency_directory(root, key, metadata)
    storage = checked_dir(root, 'data/dsh/dependencies')
    if target.resolve() != target:
        raise ValueError('依赖目录不能是链接。')
    if dependencies_ready(root, key, metadata) and not force:
        return {'message': '插件运行依赖已就绪。'}
    with tempfile.TemporaryDirectory(prefix='.prepare-', dir=storage) as scratch:
        stage = Path(scratch) / 'ready'
        stage.mkdir()
        write_json(stage / 'package.json', {'name': 'jingban-plugin-dependencies', 'version': '1.0.0',
                                           'private': True, 'dependencies': runtime_dependencies(metadata)})
        if runtime_dependencies(metadata):
            progress('正在准备插件与兼容层 npm 运行依赖（禁用安装脚本）…')
            run_npm(root, stage, progress, check)
        missing = missing_dependency_files(stage, metadata)
        if missing:
            raise ValueError('依赖安装后仍缺少运行文件，本次未标记就绪：' + '、'.join(missing[:10]))
        write_json(stage / 'ready.json', {'format': 2})
        cancelled(check)
        previous = None
        if target.exists():
            previous = checked_dir(root, 'data/dsh/removed') / ('dependencies-' + uuid.uuid4().hex[:16])
            target.rename(previous)
        try:
            stage.rename(target)
        except Exception:
            if previous:
                previous.rename(target)
            raise
    return {'message': '原版插件运行依赖已就绪。'}


class CordisBackend(QObject):
    log = Signal(str)
    ready = Signal()
    failed = Signal(str)
    stopped = Signal()
    balance_requested = Signal(str)
    web_requested = Signal(str)

    def __init__(self, root, package, report, config, parent=None, *, reply_bubbles=True):
        super().__init__(parent)
        self.root, self.package, self.report, self.config = Path(root), Path(package), report, config
        self.reply_bubbles = bool(reply_bubbles)
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        self.process.readyReadStandardOutput.connect(self._stdout)
        self.process.readyReadStandardError.connect(self._stderr)
        self.process.started.connect(self._started)
        self.process.errorOccurred.connect(self._error)
        self.process.finished.connect(self._finished)
        self.timeout = QTimer(self)
        self.timeout.setSingleShot(True)
        self.timeout.timeout.connect(lambda: self._fail('插件启动超时，已终止后台进程。'))
        self.kill_timer = QTimer(self)
        self.kill_timer.setSingleShot(True)
        self.kill_timer.timeout.connect(self.process.kill)
        self.buffer = b''
        self.job = None
        self.is_ready = self.stopping = self.has_failed = False

    def start(self):
        if not runtime_ready(self.root):
            raise ValueError('插件运行环境尚未准备完成。')
        metadata = read_json(self.package / 'package.json')
        self.dependency_root = dependency_directory(self.root, self.report['id'], metadata)
        if not dependencies_ready(self.root, self.report['id'], metadata):
            raise ValueError('插件 npm 运行依赖尚未准备完成。')
        runtime = runtime_directory(self.root)
        from dsh_web import WEB_HOST
        self.web_host = runtime / ('web-host-' + hashlib.sha256(WEB_HOST.encode()).hexdigest()[:16] + '.mjs')
        if not self.web_host.is_file():
            self.web_host.write_text(WEB_HOST, encoding='utf-8')
        host = runtime / ('host-' + hashlib.sha256(HOST_SOURCE.encode()).hexdigest()[:16] + '.mjs')
        if not host.is_file():
            host.write_text(HOST_SOURCE, encoding='utf-8')
        self.process.setWorkingDirectory(str(self.package))
        environment = QProcessEnvironment.systemEnvironment()
        for key in ('NODE_OPTIONS', 'NODE_PATH', 'ELECTRON_RUN_AS_NODE'):
            environment.remove(key)
        self.arguments = []
        if self.report['adapter'] == 'standalone':
            arguments = self.config.get('arguments', [])
            extra = self.config.get('environment', {})
            if (not isinstance(arguments, list) or len(arguments) > 50
                    or any(not isinstance(value, str) or len(value) > 4000 for value in arguments)
                    or not isinstance(extra, dict) or len(extra) > 50):
                raise ValueError('独立入口配置应为 arguments 字符串数组和 environment 对象。')
            for key, value in extra.items():
                if (not re.fullmatch('[A-Za-z_][A-Za-z0-9_]{0,99}', key) or not isinstance(value, str)
                        or len(value) > 4000 or key.upper() in ('NODE_OPTIONS', 'NODE_PATH', 'ELECTRON_RUN_AS_NODE', 'DSH_HOME')):
                    raise ValueError('无效或保留的环境变量：' + str(key))
                environment.insert(key, value)
            self.arguments = arguments
        self.state_home = checked_dir(self.root, 'data/dsh/state')
        self.web_interface = self.state_home / 'compat' / (self.report['id'] + '.json')
        # Some dependency APIs (including esbuild-wasm) spawn bare "node" even
        # though the host itself was launched by absolute path. Pin our runtime
        # first after applying plugin environment overrides, for this child only.
        environment.insert('PATH', str(runtime.resolve()) + os.pathsep + environment.value('PATH'))
        environment.insert('npm_node_execpath', str((runtime / 'node.exe').resolve()))
        environment.insert('DSH_HOME', str(self.state_home))
        environment.insert('NO_COLOR', '1')
        self.process.setProcessEnvironment(environment)
        self.process.start(str(runtime / 'node.exe'), [str(host)])
        self.timeout.start(30000)

    def _started(self):
        try:
            self.job = ProcessJob(self.process.processId())
        except Exception as error:
            self._fail('无法托管后台插件进程，已取消加载：' + str(error))
            self.process.kill()
            return
        request = {'type': 'start', 'entry': str((self.package / self.report['entry']).resolve()),
                   'mode': self.report['adapter'], 'config': self.config, 'arguments': self.arguments,
                   'dependencyRoot': str(self.dependency_root)}
        if self.report.get('interface_file'):
            relative = safe_name(self.report['interface_file'])
            request['interfaceFile'] = str(self.state_home / relative)
        request['petReplyBridge'] = (self.report.get('adapter') == 'standalone'
                                     and self.report.get('command') == 'dsh-pet-standalone')
        if request['petReplyBridge']:
            request['replyBubbles'] = self.reply_bubbles
        if self.report.get('web_compat'):
            from dsh_web import PET_CLIENT
            request.update(webInterface=str(self.web_interface), webHost=str(self.web_host),
                           petWeb=request['petReplyBridge'], petClient=PET_CLIENT,
                           whaleWidget=self.report.get('web_compat') == 'whale-widget')
        self.send(request)

    def send(self, value):
        if self.process.state() == QProcess.ProcessState.Running:
            raw = (json.dumps(value, ensure_ascii=False) + '\n').encode('utf-8')
            if len(raw) <= 256 * 1024:
                self.process.write(raw)

    def publish_event(self, name, value=None):
        if self.is_ready and not self.stopping:
            self.send({'type': 'event', 'name': 'jingban/' + name, 'value': value})

    def set_reply_bubbles(self, enabled):
        self.reply_bubbles = bool(enabled)
        if not self.stopping:
            self.send({'type': 'bridge-settings', 'enabled': bool(enabled)})

    def _stdout(self):
        self.buffer += bytes(self.process.readAllStandardOutput())
        if len(self.buffer) > 256 * 1024:
            return self._fail('插件输出过长，已停止。')
        while b'\n' in self.buffer:
            line, self.buffer = self.buffer.split(b'\n', 1)
            if line.startswith(b'\x1eJBDSH '):
                try:
                    packet = json.loads(line[7:])
                    kind, value = packet['type'], str(packet.get('value', ''))
                    if kind == 'balance-request' and not self.stopping:
                        self.balance_requested.emit(value)
                    elif kind == 'web-surface' and not self.stopping:
                        self.web_requested.emit(value)
                    elif kind == 'ready' and not self.stopping:
                        self.timeout.stop()
                        self.is_ready = True
                        self.log.emit(value)
                        self.ready.emit()
                    elif kind == 'error':
                        self._fail(value)
                    else:
                        self.log.emit(value[:14000])
                except (ValueError, KeyError, TypeError):
                    self.log.emit(line.decode('utf-8', errors='replace')[:14000])
            elif line:
                self.log.emit(line.decode('utf-8', errors='replace')[:14000])

    def _stderr(self):
        text = bytes(self.process.readAllStandardError()).decode('utf-8', errors='replace')
        if text:
            self.log.emit(text[:14000])

    def _fail(self, text):
        if not self.has_failed and not self.stopping:
            self.has_failed = True
            self.failed.emit(text[:14000])
        self.stop()

    def _error(self, error):
        if not self.stopping:
            self._fail('后台进程错误：' + self.process.errorString())
        if error == QProcess.ProcessError.FailedToStart:
            self.stopped.emit()

    def _finished(self, code, status):
        self.timeout.stop()
        self.kill_timer.stop()
        self._stdout()
        self._stderr()
        if self.job:
            self.job.close()
            self.job = None
        if not self.stopping:
            self.failed.emit(f'插件后台进程意外退出（代码 {code}），请查看运行日志。')
        self.stopped.emit()

    def stop(self):
        self.timeout.stop()
        self.stopping = True
        self.is_ready = False
        self.send({'type': 'stop'})
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.kill_timer.start(4000)

    def shutdown(self):
        self.stop()
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.waitForFinished(4100)
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()
            self.process.waitForFinished(1000)
        if self.job:
            self.job.close()
            self.job = None
