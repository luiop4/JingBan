"""Transparent native surfaces for the original DSH whale widget, without an HTML window."""
from __future__ import annotations

import json
import math
import os

from PySide6.QtCore import QObject, QEvent, QFile, QIODevice, QPoint, QRect, QTimer, QUrl, Qt, Signal, Slot
from PySide6.QtGui import QColor, QDesktopServices, QGuiApplication, QPainter, QRegion
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout


_rendering_configured = False


def configure_rendering():
    """Select the supported CPU path before the first WebEngine/Quick surface.

    Windows translucent GPU surfaces can retain corrupt texture tiles on a cold
    start. Isolating HWNDs does not fix that driver/compositor failure. Configure
    both halves: Chromium's page renderer and Qt Quick's final scene renderer.
    This is process-local, not a Windows or external-browser setting.
    """
    global _rendering_configured
    if _rendering_configured:
        return
    os.environ['QT_QUICK_BACKEND'] = 'software'
    flags = os.environ.get('QTWEBENGINE_CHROMIUM_FLAGS', '')
    for flag in ('--disable-gpu', '--disable-gpu-compositing'):
        if flag not in flags.split():
            flags = (flags+' '+flag).strip()
    os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = flags
    try:
        from PySide6.QtQuick import QQuickWindow
    except ImportError:
        # Missing optional web/Quick components must not prevent the chat UI
        # from opening; plugin activation will report its missing dependency.
        _rendering_configured = True
        return
    QQuickWindow.setSceneGraphBackend('software')
    _rendering_configured = True


SURFACE_SCRIPT = r'''(()=>{
 if(window.__jingbanWhaleSurface)return;
 const css=document.createElement('style');
 css.textContent='html,body{background:transparent!important;background-image:none!important;margin:0!important;padding:0!important;overflow:hidden!important}' +
   '#root>[data-composer-seat],#sections{display:none!important}';
 document.head.appendChild(css);
 let bridge=null,queued=false,drag=false,last='';
 const root=()=>document.querySelector('.dshwv-root');
 const visible=e=>{
   for(let p=e;p&&p!==document.documentElement;p=p.parentElement){
     const s=getComputedStyle(p);if(s.display==='none'||s.visibility==='hidden'||Number(s.opacity)===0)return false;
   }return true;
 };
 function report(){
   queued=false;if(!bridge)return;
   const r=root(),image=r?.querySelector('img'),mounted=!!(r&&image?.naturalWidth),rects=[];
   const add=e=>{if(!visible(e))return;const b=e.getBoundingClientRect();
     if(b.width>0&&b.height>0)rects.push([b.left,b.top,b.width,b.height]);};
   for(const e of document.body.children){
     if([...e.classList].some(c=>c.startsWith('dshwv-')))add(e);
   }
   // Speech bubbles can extend beyond the character's own bounding rectangle.
   if(r)for(const e of r.querySelectorAll('.dshwv-pop,.dshwv-minipop'))add(e);
   const b=r?.getBoundingClientRect();
   const payload={mounted,rects:rects.slice(0,64),viewport:[innerWidth,innerHeight],
     drag:drag||!!r?.classList.contains('dshwv-dragging'),
     position:b?[b.left/Math.max(1,innerWidth),b.top/Math.max(1,innerHeight)]:null};
   const value=JSON.stringify(payload);if(value!==last){last=value;bridge.regions(value);}
 }
 const queue=()=>{if(!queued){queued=true;setTimeout(report,24);}};
 const settle=()=>{queue();setTimeout(queue,70);setTimeout(queue,200);setTimeout(queue,400);};
 new MutationObserver(queue).observe(document.body,{childList:true,subtree:true,attributes:true,
   attributeFilter:['class','style','src','hidden']});
 document.addEventListener('pointerdown',e=>{if(e.target.closest?.('.dshwv-root')){drag=true;queue();}},true);
 const release=()=>{if(drag){drag=false;settle();}};
 document.addEventListener('pointerup',release,true);document.addEventListener('pointercancel',release,true);
 window.addEventListener('blur',release);window.addEventListener('resize',settle);
 document.addEventListener('transitionend',queue,true);document.addEventListener('load',queue,true);
 document.addEventListener('scroll',queue,true);
 window.__jingbanWhaleSurface={refresh(){last='';settle();}};
 new QWebChannel(qt.webChannelTransport,channel=>{bridge=channel.objects.jingbanWhaleSurface;settle();});
 // Recover from delayed plugin mounting; unchanged geometry does not cross into Qt.
 setInterval(queue,2000);
})()'''


class _SurfaceWindow(QWidget):
    dismissed = Signal()

    def paintEvent(self, event):
        # Transparent pixels must replace the previous frame, not blend over it.
        painter = QPainter(self)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.fillRect(event.rect(), Qt.GlobalColor.transparent)
        painter.end()

    def closeEvent(self, event):
        self.hide()
        self.dismissed.emit()
        event.accept()


class WhaleWidgetSurface(QObject):
    closed = Signal()
    mode_changed = Signal(str)
    position_changed = Signal(str, object)
    problem = Signal(str)

    def __init__(self, window, url, mode='window', positions=None, parent=None):
        super().__init__(parent or window)
        configure_rendering()
        from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineScript
        from PySide6.QtWebEngineWidgets import QWebEngineView
        from PySide6.QtWebChannel import QWebChannel

        self.window, self.mode = window, ''
        self.positions = dict(positions) if isinstance(positions, dict) else {}
        self.host = self.view = None
        self._closed = self._mounted = self._dragging = False
        self._position = None
        self._region = QRegion()
        self._screen = None
        self._restoring = False
        self._preload_script = None
        port = QUrl(url).port()

        # Create the hidden native host before constructing its child view.
        self._make_host(mode if mode in ('window', 'desktop', 'hidden') else 'window')
        self.view = QWebEngineView(self.host)
        self.view.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.view.setStyleSheet('background:transparent;border:0;')
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.host.layout().addWidget(self.view)

        class LocalPage(QWebEnginePage):
            def acceptNavigationRequest(page, target, kind, main):
                if main and (target.host() != '127.0.0.1' or target.port() != port or target.scheme() != 'http'):
                    if target.scheme() in ('http', 'https'):
                        QDesktopServices.openUrl(target)
                    return False
                return True

        self.page = LocalPage(self.view)
        self.page.setBackgroundColor(QColor(0, 0, 0, 0))
        self.view.setPage(self.page)
        self.channel = QWebChannel(self.page)
        self.channel.registerObject('jingbanWhaleSurface', self)
        self.page.setWebChannel(self.channel)
        library = QFile(':/qtwebchannel/qwebchannel.js')
        if not library.open(QIODevice.OpenModeFlag.ReadOnly):
            self.close()
            raise RuntimeError('挂件界面连接组件不可用，请修复应用运行环境。')
        channel_source = bytes(library.readAll()).decode('utf-8')
        library.close()
        script = QWebEngineScript()
        script.setName('jingban-transparent-whale-surface')
        script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentReady)
        script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        script.setRunsOnSubFrames(False)
        script.setSourceCode(channel_source+'\n'+SURFACE_SCRIPT)
        self.page.scripts().insert(script)
        self._install_position_script()
        self.view.loadFinished.connect(self._loaded)
        self.position_timer = QTimer(self)
        self.position_timer.setSingleShot(True)
        self.position_timer.timeout.connect(self._save_position)
        self.drag_timer = QTimer(self)
        self.drag_timer.setInterval(250)
        self.drag_timer.timeout.connect(self._check_drag)
        self.owner_timer = QTimer(self)
        self.owner_timer.setSingleShot(True)
        self.owner_timer.timeout.connect(self._sync_owner)
        window.installEventFilter(self)
        central = window.centralWidget() if hasattr(window, 'centralWidget') else window
        self.embed_parent = central or window
        if self.embed_parent is not window:
            self.embed_parent.installEventFilter(self)
        QGuiApplication.instance().primaryScreenChanged.connect(self._primary_screen_changed)
        self._primary_screen_changed(QGuiApplication.primaryScreen())
        self.view.setUrl(QUrl(url))
        self._prime()

    def _prime(self):
        # Let the CPU renderer initialize the whole transparent framebuffer.
        # A 1-pixel bootstrap mask leaves most cold-start tiles uninitialized;
        # expanding that mask later can expose old page or character fragments.
        if not self._closed and self.mode != 'hidden' and self._owner_visible():
            self.host.clearMask()
            self.view.show()
            self.host.show()
            self._sync_transient_owner()

    def _make_host(self, mode):
        # Keep WebEngine in its own native surface even when following the app.
        # A late GPU widget inside the main widget tree promotes/recreates the
        # main backing store during startup and can retain stale texture tiles.
        parent = None
        flags = Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint
        if mode == 'desktop':
            parent = None
            flags |= Qt.WindowType.WindowStaysOnTopHint
        host = _SurfaceWindow(parent, flags)
        host.setObjectName('jingbanWhaleSurface')
        host.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        host.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        host.setStyleSheet('QWidget#jingbanWhaleSurface{background:transparent;border:0;}')
        host.setWindowTitle('鲸伴 · 桌面挂件')
        layout = QVBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        host.dismissed.connect(lambda: self.set_mode('hidden'))
        self.host, self.mode = host, mode
        self._sync_geometry()

    def _desktop_geometry(self):
        screen = QGuiApplication.primaryScreen()
        return screen.availableGeometry() if screen else QRect(0, 0, 1280, 720)

    def _sync_geometry(self):
        if self._closed or self.host is None:
            return
        if self.mode == 'desktop':
            geometry = self._desktop_geometry()
        else:
            central = self.window.centralWidget() if hasattr(self.window, 'centralWidget') else self.window
            central = central or self.window
            geometry = QRect(central.mapToGlobal(QPoint(0, 0)), central.size())
        self.host.setGeometry(geometry)
        if self.view is not None:
            self.view.setGeometry(self.host.rect())

    def _sync_transient_owner(self):
        handle = self.host.windowHandle()
        owner = self.window.windowHandle() if self.mode == 'window' else None
        if handle is not None and handle.transientParent() is not owner:
            handle.setTransientParent(owner)

    def _owner_visible(self):
        return self.mode == 'desktop' or (self.window.isVisible() and not self.window.isMinimized())

    def _sync_owner(self):
        if not self._closed:
            self._sync_geometry()
            self._apply_region()

    def _primary_screen_changed(self, screen):
        if self._screen is not None:
            try:
                self._screen.availableGeometryChanged.disconnect(self._sync_geometry)
            except (RuntimeError, TypeError):
                pass
        self._screen = screen
        if screen is not None:
            screen.availableGeometryChanged.connect(self._sync_geometry)
        self._sync_geometry()

    def eventFilter(self, watched, event):
        if not self._closed and event.type() in (QEvent.Type.Move, QEvent.Type.Resize, QEvent.Type.Show,
                                                QEvent.Type.Hide, QEvent.Type.WindowActivate, QEvent.Type.WindowStateChange):
            # Let the owning window finish its native Show/resize first.
            if event.type() == QEvent.Type.Hide and self.mode != 'desktop':
                self.host.hide()
            self.owner_timer.start(0)
        return False

    def _loaded(self, ok):
        if self._closed:
            return
        if not ok:
            self.problem.emit('挂件未加载成功，可在插件页点“重新加载挂件”。')
        self._restore_position()

    def _restore_position(self):
        if self._closed:
            return
        self._restoring = True
        self.page.runJavaScript('window.__jingbanWhaleSurface?.refresh()')
        QTimer.singleShot(600, lambda: setattr(self, '_restoring', False) if not self._closed else None)

    def _install_position_script(self):
        from PySide6.QtWebEngineCore import QWebEngineScript
        position = self.positions.get(self.mode)
        if (not isinstance(position, (list, tuple)) or len(position) != 2
                or not all(type(v) in (int, float) and math.isfinite(v) for v in position)):
            position = [0.72, 0.42] if self.mode == 'window' else [0.78, 0.60]
        position = [max(0., min(1., v)) for v in position]
        script = QWebEngineScript()
        script.setName('jingban-whale-surface-position')
        script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        script.setRunsOnSubFrames(False)
        # Use the original plugin's own anchoring state at initialization. Merely
        # moving its DOM would be overwritten by its resize and render handlers.
        script.setSourceCode('(()=>{try{const p='+json.dumps(position)+';'
            "localStorage.setItem('dshw-pos',JSON.stringify({v:2,hAnchor:'left',hDist:Math.round(p[0]*(innerWidth||1000)),"
            "vAnchor:'top',vDist:Math.round(p[1]*(innerHeight||720))}));}catch{}})()")
        if self._preload_script is not None:
            self.page.scripts().remove(self._preload_script)
        self.page.scripts().insert(script)
        self._preload_script = script

    @Slot(str)
    def regions(self, encoded):
        if self._closed or len(encoded) > 20000:
            return
        try:
            data = json.loads(encoded)
            width, height = data['viewport']
            if not all(type(v) in (int, float) and math.isfinite(v) and v > 0 for v in (width, height)):
                return
            sx, sy = self.view.width()/width, self.view.height()/height
            region = QRegion()
            for row in data.get('rects', [])[:64]:
                if (not isinstance(row, list) or len(row) != 4
                        or not all(type(v) in (int, float) and math.isfinite(v) and abs(v) < 100000 for v in row)):
                    continue
                x, y, w, h = row
                if w > 0 and h > 0:
                    region |= QRegion(QRect(math.floor(x*sx)-3, math.floor(y*sy)-3,
                                           math.ceil(w*sx)+6, math.ceil(h*sy)+6))
            self._region = region.intersected(QRegion(self.host.rect()))
            self._mounted = data.get('mounted') is True
            dragging = data.get('drag') is True
            released = self._dragging and not dragging
            self._dragging = dragging
            self.drag_timer.start() if dragging else self.drag_timer.stop()
            position = data.get('position')
            if (isinstance(position, list) and len(position) == 2
                    and all(type(v) in (int, float) and math.isfinite(v) for v in position)):
                self._position = [max(0., min(1., float(v))) for v in position]
            if released and not self._restoring:
                self.position_timer.start(450)
            self._apply_region()
        except (ValueError, TypeError, KeyError, OverflowError):
            return

    def _apply_region(self):
        if self._closed:
            return
        if self.mode == 'hidden' or not self._owner_visible():
            self.host.hide()
            return
        if not self._mounted or self._region.isEmpty():
            self._prime()
            return
        mask = QRegion(self.host.rect()) if self._dragging else self._region
        if self.host.mask() != mask:
            self.host.setMask(mask)
            self.host.update()
            self.view.update()
        self.host.show()
        self._sync_transient_owner()
        if self.mode == 'desktop' or self.window.isActiveWindow() or self.host.isActiveWindow():
            self.host.raise_()

    def _check_drag(self):
        if not QApplication.mouseButtons():
            self._dragging = False
            self.drag_timer.stop()
            self.position_timer.start(450)
            self._apply_region()

    def _save_position(self):
        if self._closed or self.mode == 'hidden' or self._restoring or self._position is None:
            return
        self.positions[self.mode] = list(self._position)
        self.position_changed.emit(self.mode, list(self._position))

    def set_mode(self, mode):
        if self._closed or mode not in ('window', 'desktop', 'hidden'):
            return
        if mode == self.mode:
            self.show()
            return
        self._save_position()
        self.position_timer.stop()
        self._dragging = False
        self.drag_timer.stop()
        old = self.host
        old.hide()
        self._make_host(mode)
        # Reparent directly into an already prepared hidden host, never show the
        # view as a temporary independent window while switching surfaces.
        self.view.setParent(self.host)
        self.host.layout().addWidget(self.view)
        self.view.show()
        old.deleteLater()
        self._region = QRegion()
        self._mounted = False
        self._prime()
        self._install_position_script()
        self.view.reload()
        self.mode_changed.emit(mode)

    def show(self):
        if not self._closed:
            self._sync_geometry()
            self._apply_region()
            self.page.runJavaScript('window.__jingbanWhaleSurface?.refresh()')

    def reload(self):
        if not self._closed:
            self._mounted = False
            self._prime()
            self.view.reload()

    def close(self):
        if self._closed:
            return
        self._closed = True
        if hasattr(self, 'position_timer'):
            self.position_timer.stop()
            self.drag_timer.stop()
            self.owner_timer.stop()
        if self.host is not None:
            self.host.hide()
            self.host.deleteLater()
        self.closed.emit()
        self.deleteLater()
