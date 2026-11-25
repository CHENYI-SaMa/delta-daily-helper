# -*- coding: utf-8 -*-
"""三角洲每日助手 原生桌面查看器（tkinter，单文件 exe）。

特点：
- 原生窗口程序，双击即开，不依赖 Edge / 本地服务器。
- 自带 kkrb.net 抓取：首次打开 / 完全退出后重开 → 联网抓取当日数据（后台线程，不卡界面）。
- 页面缓存：抓取成功后写入 AppData 缓存；无网络时回退到离线缓存。
- 系统托盘：点 × 默认缩到托盘；托盘图标左键唤出、右键菜单「显示/退出」。
- 全局热键：Ctrl+Q 快速唤出 / 隐藏窗口（固定，不支持自定义）。
- 滚轮（或 ‹ › 按钮）在「密码 / 制造 / 兑换」三个项目间整页切换。
- 深 / 浅色主题切换、窗口置顶。
- 无边框圆角窗口，记忆上次关闭时的位置。
- 不含：复制按钮、子弹追踪、更新时间、AZ彩六联动房、刷新按钮。
"""
import json
import os
import sys
import threading
import ctypes
import webbrowser
import tkinter as tk
from tkinter import messagebox
from datetime import datetime

import license as lic

# ============================================================
# 高 DPI 适配
# ============================================================
DPI_SCALE = 1.0
if sys.platform.startswith("win"):
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
    try:
        _dpi = ctypes.windll.user32.GetDpiForSystem()
    except Exception:
        _dpi = 96
    if _dpi and _dpi > 0:
        DPI_SCALE = _dpi / 96.0


def px(n):
    return int(round(n * DPI_SCALE))


# ============================================================
# 路径与缓存
# ============================================================
APP_DIR = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))

CONFIG_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local")), "DeltaForceNative")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
CACHE_PATH = os.path.join(CONFIG_DIR, "cache.json")

# 密码地点映射（含 AZ3 彩六联动房，UI 会按关键词过滤）
PASSWORD_PLACES = {
    "db": "零号大坝",
    "cgxg": "长弓溪谷",
    "bks": "巴克什",
    "htjd": "航天基地",
    "cxjy": "潮汐监狱",
    "az3": "AZ3核电站",
    "az3r6": "AZ3彩六联动房",
}

# 密码地图中需过滤掉的项（非常规密码）
PASSWORD_FILTER = ["彩六"]

WINDOW_WIDTH = 460
WINDOW_HEIGHT = 420
WINDOW_SIZE = "%dx%d" % (px(WINDOW_WIDTH), px(WINDOW_HEIGHT))
CORNER_RADIUS = 20

THEMES = {
    "dark": {
        "bg": "#0e1116", "card": "#1a2029", "card2": "#20262f", "border": "#2a313c",
        "text": "#e6eaf0", "dim": "#9aa4b2", "accent": "#f5b942", "accent2": "#4ade80",
        "danger": "#f87171", "track": "#2a313c",
    },
    "light": {
        "bg": "#f4f6f9", "card": "#ffffff", "card2": "#f7f9fc", "border": "#dde3ec",
        "text": "#1b2230", "dim": "#5b6675", "accent": "#c98a14", "accent2": "#1ba85a",
        "danger": "#d6453f", "track": "#dde3ec",
    },
}

BTN_COLORS = {
    "dark":  {"normal": "#20262f", "hover": "#2a313c", "active": "#333d49", "fg": "#e6eaf0", "outline": "#2a313c"},
    "light": {"normal": "#ffffff", "hover": "#eef1f6", "active": "#e1e7f0", "fg": "#1b2230", "outline": "#dde3ec"},
}

# 热键默认：Ctrl+Q
DEFAULT_HOTKEY = (2, 0x51)
MOD_LABELS = {
    0: "无", 2: "Ctrl", 1: "Alt", 3: "Ctrl+Alt", 8: "Win",
    10: "Ctrl+Win", 9: "Alt+Win", 11: "Ctrl+Alt+Win", 4: "Shift", 6: "Ctrl+Shift",
    5: "Alt+Shift", 12: "Win+Shift", 7: "Ctrl+Alt+Shift",
}

# 「获取激活码」链接（占位，替换为实际页面后再发布）
GET_CODE_URL = "https://example.com/get-code"


# ============================================================
# 配置读写
# ============================================================
def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(**kwargs):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        cfg = load_config()
        cfg.update(kwargs)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False)
    except Exception:
        pass


def load_cache():
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_cache(data):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        pass


# ============================================================
# kkrb.net 抓取（纯标准库）
# ============================================================
import urllib.request
import urllib.parse
import http.cookiejar

BASE_URL = "https://www.kkrb.net"


class KkrbAPI:
    def __init__(self):
        self.cj = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cj)
        )
        self.opener.addheaders = [
            ("User-Agent",
             "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
             "AppleWebKit/537.36 (KHTML, like Gecko) "
             "Chrome/131.0.0.0 Safari/537.36"),
            ("Referer", f"{BASE_URL}/"),
            ("Origin", BASE_URL),
            ("X-Requested-With", "XMLHttpRequest"),
            ("Accept", "application/json, text/javascript, */*; q=0.01"),
            ("Accept-Language", "zh-CN,zh;q=0.9,en;q=0.8"),
        ]
        self._session_ready = False

    def _init_session(self):
        if self._session_ready:
            return
        self.opener.open(f"{BASE_URL}/")
        data = urllib.parse.urlencode({"globalData": "false"}).encode()
        req = urllib.request.Request(f"{BASE_URL}/getMenu", data=data, method="POST")
        self.opener.open(req)
        self._session_ready = True

    def post(self, endpoint, params=None):
        self._init_session()
        if params is None:
            params = {}
        data = urllib.parse.urlencode(params).encode()
        req = urllib.request.Request(f"{BASE_URL}/{endpoint}", data=data, method="POST")
        resp = self.opener.open(req, timeout=30)
        return json.loads(resp.read().decode("utf-8"))

    def get_passwords(self):
        result = self.post("getBonusDoorData")
        if result.get("code") != 1:
            raise Exception(f"密码接口返回错误: {result.get('msg', 'unknown')}")
        return result["data"]

    def get_manufacturing(self):
        result = self.post("getSwatProductData")
        if result.get("code") != 1:
            raise Exception(f"制造接口返回错误: {result.get('msg', 'unknown')}")
        return result.get("data", {}).get("cn", [])

    def get_exchange(self):
        result = self.post("getTradeAmmoData")
        if result.get("code") != 1:
            raise Exception(f"兑换接口返回错误: {result.get('msg', 'unknown')}")
        return result.get("data", {}).get("cn", [])


def fetch_today_data(api):
    """抓取当日密码 / 制造 / 兑换，返回适配 UI 的 dict。"""
    from collections import defaultdict
    data = {"date": datetime.now().strftime("%Y-%m-%d"),
            "fetch_time": datetime.now().strftime("%H:%M:%S")}

    # 密码
    try:
        pwd_raw = api.get_passwords()
        data["passwords"] = {}
        for key, name in PASSWORD_PLACES.items():
            if key in pwd_raw:
                data["passwords"][name] = pwd_raw[key].get("password", "")
    except Exception as e:
        data["passwords"] = None
        data["passwords_error"] = str(e)

    # 制造推荐
    try:
        mfg_raw = api.get_manufacturing()
        by_place = defaultdict(list)
        for item in mfg_raw:
            by_place[item.get("placeName", "")].append(item)
        data["manufacturing"] = []
        for place in ["技术中心", "工作台", "制药台", "防具台"]:
            if place in by_place:
                top = max(by_place[place], key=lambda x: x.get("profit", 0))
                data["manufacturing"].append({
                    "place": place,
                    "item": top.get("itemName", ""),
                    "profit": top.get("profit", 0),
                })
    except Exception as e:
        data["manufacturing"] = None
        data["manufacturing_error"] = str(e)

    # 兑换推荐
    try:
        ex_raw = api.get_exchange()
        sorted_items = sorted(ex_raw, key=lambda x: x.get("profit", 0), reverse=True)
        data["exchange"] = []
        for item in sorted_items[:3]:
            data["exchange"].append({
                "item": item.get("itemName", ""),
                "profit": item.get("profit", 0),
            })
    except Exception as e:
        data["exchange"] = None
        data["exchange_error"] = str(e)

    return data


def hotkey_label(hk):
    mod, vk = hk
    # 生成可读修饰名
    parts = []
    if mod & 0x2: parts.append("Ctrl")
    if mod & 0x1: parts.append("Alt")
    if mod & 0x4: parts.append("Shift")
    if mod & 0x8: parts.append("Win")
    s = "+".join(parts) if parts else "无"
    # vk -> 字符
    if 0x41 <= vk <= 0x5A:
        key = chr(vk)
    elif 0x30 <= vk <= 0x39:
        key = str(vk - 0x30)
    elif 0x70 <= vk <= 0x7B:
        key = "F" + str(vk - 0x70 + 1)
    else:
        key = "?"
    return (s + "+" + key) if s != "无" else key


# ============================================================
# 圆角按钮
# ============================================================
class RoundedButton(tk.Canvas):
    def __init__(self, master, text="", width=80, height=30, radius=12,
                 font=("Microsoft YaHei", 11), command=None, canvas_bg="#0e1116",
                 colors=None):
        super().__init__(master, width=px(width), height=px(height),
                         highlightthickness=0, bd=0, bg=canvas_bg,
                         insertontime=0, insertwidth=0)
        self._bw = px(width)
        self._bh = px(height)
        self._r = px(radius)
        self._text = text
        self._font = font
        self._command = command
        self._colors = colors or BTN_COLORS
        self._theme = "dark"
        self.bind("<Enter>", lambda e: self._redraw("hover"))
        self.bind("<Leave>", lambda e: self._redraw("normal"))
        self.bind("<ButtonPress-1>", lambda e: self._redraw("active"))
        self.bind("<ButtonRelease-1>", lambda e: (self._redraw("hover"), self._fire()))
        self._redraw("normal")

    def _fire(self):
        if self._command:
            self._command()

    def _redraw(self, state):
        self.delete("all")
        c = self._colors[self._theme]
        bg = c.get(state, c["normal"])
        fg = c["fg"]
        ol = c.get("outline", bg)
        self._round_rect(0, 0, self._bw, self._bh, self._r, fill=bg, outline=ol, width=px(1))
        self.create_text(self._bw / 2, self._bh / 2, text=self._text, fill=fg,
                         font=self._font, anchor="center")

    def _round_rect(self, x1, y1, x2, y2, r, **kw):
        pts = [x1, y1 + r, x1 + r, y1, x2 - r, y1, x2, y1 + r,
               x2, y2 - r, x2 - r, y2, x1 + r, y2, x1, y2 - r]
        self.create_polygon(pts, smooth=True, **kw)

    def set_theme(self, theme):
        self._theme = theme
        self._redraw("normal")

    def set_text(self, t):
        self._text = t
        self._redraw("normal")


# ============================================================
# 系统托盘（pystray，可靠）+ 全局热键（隐藏窗口 + 单实例激活）
# ============================================================
if sys.platform.startswith("win"):
    import ctypes.wintypes as wt

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    # 64 位下句柄返回必须显式声明 restype，否则被当成 32 位 int 截断导致 hwnd 错乱
    kernel32.GetModuleHandleW.restype = wt.HANDLE
    kernel32.CreateMutexW.restype = wt.HANDLE
    kernel32.GetLastError.restype = ctypes.c_uint
    user32.CreateWindowExW.restype = wt.HWND
    user32.CreateWindowExW.argtypes = [wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD,
                                       ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                       wt.HWND, wt.HMENU, wt.HANDLE, wt.LPVOID]
    user32.LoadCursorW.restype = wt.HANDLE
    user32.DefWindowProcW.restype = ctypes.c_int64
    user32.RegisterClassW.restype = wt.ATOM
    user32.FindWindowW.restype = wt.HWND
    user32.PostMessageW.restype = wt.BOOL
    user32.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
    user32.GetCursorPos.restype = wt.BOOL
    user32.GetCursorPos.argtypes = [ctypes.POINTER(wt.POINT)]
    user32.RegisterHotKey.restype = wt.BOOL
    user32.UnregisterHotKey.restype = wt.BOOL

    # 系统托盘相关（shell32 + 右键菜单）
    try:
        shell32 = ctypes.windll.shell32
    except Exception:
        shell32 = None
    user32.LoadImageW.restype = wt.HANDLE
    user32.LoadImageW.argtypes = [wt.HANDLE, wt.LPCWSTR, wt.UINT, ctypes.c_int, ctypes.c_int, wt.UINT]
    user32.CreatePopupMenu.restype = wt.HANDLE
    user32.AppendMenuW.restype = wt.BOOL
    user32.AppendMenuW.argtypes = [wt.HANDLE, wt.UINT, ctypes.c_size_t, wt.LPCWSTR]
    user32.TrackPopupMenu.restype = wt.UINT
    user32.TrackPopupMenu.argtypes = [wt.HANDLE, wt.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.HWND, ctypes.c_void_p]
    user32.DestroyMenu.restype = wt.BOOL
    user32.DestroyMenu.argtypes = [wt.HANDLE]
    if shell32 is not None:
        shell32.Shell_NotifyIconW.restype = wt.BOOL
        shell32.Shell_NotifyIconW.argtypes = [wt.DWORD, ctypes.c_void_p]

    WM_HOTKEY = 0x0312
    WM_QUIT = 0x0012
    WM_USER = 0x0400
    WM_SHOW = WM_USER + 200          # 单实例激活：让已运行的实例把窗口唤出
    TRAY_WND_CLASS = "DeltaForceTrayWnd"
    SINGLE_INSTANCE_MUTEX = "Global\\DeltaForceNativeMutex"

    WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_int64, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)

    class WNDCLASS(ctypes.Structure):
        _fields_ = [
            ("style", wt.UINT),
            ("lpfnWndProc", WNDPROC),
            ("cbClsExtra", ctypes.c_int),
            ("cbWndExtra", ctypes.c_int),
            ("hInstance", wt.HINSTANCE),
            ("hIcon", wt.HANDLE),
            ("hCursor", wt.HANDLE),
            ("hbrBackground", wt.HANDLE),
            ("lpszMenuName", wt.LPCWSTR),
            ("lpszClassName", wt.LPCWSTR),
        ]

    class MSG(ctypes.Structure):
        _fields_ = [
            ("hwnd", wt.HWND), ("message", wt.UINT),
            ("wParam", wt.WPARAM), ("lParam", wt.LPARAM),
            ("time", wt.DWORD), ("pt_x", ctypes.c_long), ("pt_y", ctypes.c_long),
        ]

    class NOTIFYICONDATA(ctypes.Structure):
        _fields_ = [
            ("cbSize", wt.DWORD),
            ("hWnd", wt.HWND),
            ("uID", wt.UINT),
            ("uFlags", wt.UINT),
            ("uCallbackMessage", wt.UINT),
            ("hIcon", wt.HANDLE),
            ("szTip", wt.WCHAR * 128),
        ]

    # 托盘消息 / 菜单常量
    WM_TRAY = WM_USER + 100
    WM_LBUTTONUP = 0x0202
    WM_RBUTTONUP = 0x0205
    WM_RBUTTONDOWN = 0x0204
    WM_LBUTTONDBLCLK = 0x0203
    WM_COMMAND = 0x0111
    NIF_MESSAGE = 0x1
    NIF_ICON = 0x2
    NIF_TIP = 0x4
    NIM_ADD = 0x0
    NIM_DELETE = 0x1
    IMAGE_ICON = 1
    LR_LOADFROMFILE = 0x0010
    LR_DEFAULTSIZE = 0x0040
    MF_STRING = 0x0
    TPM_LEFTALIGN = 0x0000
    TPM_RIGHTBUTTON = 0x0002
    TPM_NONOTIFY = 0x0080
    TPM_RETURNCMD = 0x0100
    WM_NULL = 0x0000
    ID_SHOW = 1001
    ID_EXIT = 1002

    _tray_app = None
    _wnd_proc_inst = None
    _tray_nid = None
    _menu_open = False

    def _wnd_proc(hwnd, msg, wparam, lparam):
        if msg == WM_HOTKEY:
            if _tray_app:
                _tray_app.after(0, _tray_app.toggle_show)
            return 0
        if msg == WM_SHOW:
            if _tray_app:
                _tray_app.after(0, _tray_app.show)
            return 0
        if msg == WM_TRAY:
            # 左键 / 双击：直接唤起窗口；右键（按下或抬起都算）：弹菜单
            if lparam in (WM_LBUTTONUP, WM_LBUTTONDBLCLK):
                if _tray_app:
                    _tray_app.after(0, _tray_app.show)
            elif lparam in (WM_RBUTTONUP, WM_RBUTTONDOWN):
                _show_tray_menu(hwnd)
            return 0
        if msg == WM_COMMAND:
            cmd = wparam & 0xFFFF
            if cmd == ID_SHOW and _tray_app:
                _tray_app.after(0, _tray_app.show)
            elif cmd == ID_EXIT and _tray_app:
                _tray_app.after(0, _tray_app.quit_app)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _show_tray_menu(hwnd):
        """右键托盘图标 → 调度到主线程弹菜单。

        用 tkinter 自绘菜单（不走 ctypes 原生 TrackPopupMenu），彻底绕开
        Win11 DWM 合成下原生菜单文字被覆盖/显示为空白的问题。
        """
        if _tray_app:
            _tray_app.after(0, _tray_app._popup_tray_menu)

    def _load_hicon():
        """把内嵌的 PNG 图标转成 HICON 供托盘使用。"""
        try:
            import io as _io
            import base64 as _b64
            import tempfile
            from PIL import Image
            from icon_data import ICON_B64
            img = Image.open(_io.BytesIO(_b64.b64decode(ICON_B64))).convert("RGBA")
            fd, path = tempfile.mkstemp(suffix=".ico")
            os.close(fd)
            img.save(path, format="ICO")
            hicon = user32.LoadImageW(None, path, IMAGE_ICON, 0, 0,
                                      LR_LOADFROMFILE | LR_DEFAULTSIZE)
            try:
                os.remove(path)
            except Exception:
                pass
            return hicon
        except Exception:
            return None

    def _add_tray_icon(hwnd):
        global _tray_nid
        if shell32 is None:
            return
        hicon = _load_hicon()
        nid = NOTIFYICONDATA()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATA)
        nid.hWnd = hwnd
        nid.uID = 1
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        nid.uCallbackMessage = WM_TRAY
        nid.hIcon = hicon if hicon else 0
        nid.szTip = "三角洲每日助手"[:127]
        try:
            shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))
        except Exception:
            pass
        _tray_nid = nid

    def _remove_tray_icon():
        global _tray_nid
        if shell32 is None or _tray_nid is None:
            return
        try:
            shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(_tray_nid))
        except Exception:
            pass
        _tray_nid = None

    def _hotkey_loop():
        global _wnd_proc_inst
        _wnd_proc_inst = WNDPROC(_wnd_proc)
        cls = WNDCLASS()
        cls.lpfnWndProc = _wnd_proc_inst
        cls.hInstance = kernel32.GetModuleHandleW(None)
        cls.lpszClassName = TRAY_WND_CLASS
        cls.hCursor = user32.LoadCursorW(0, 32512)
        try:
            user32.RegisterClassW(ctypes.byref(cls))
        except Exception:
            pass
        hwnd = user32.CreateWindowExW(0, TRAY_WND_CLASS, "tray",
                                      0, 0, 0, 0, 0, 0, 0, cls.hInstance, None)
        if not hwnd:
            return
        _tray_app._tray_hwnd = hwnd
        # 系统托盘图标（左键唤起窗口、右键菜单）
        try:
            _add_tray_icon(hwnd)
        except Exception:
            pass
        # 热键固定为 Ctrl+Q（不再支持自定义）
        try:
            user32.RegisterHotKey(hwnd, 1, DEFAULT_HOTKEY[0], DEFAULT_HOTKEY[1])
        except Exception:
            pass
        msg = MSG()
        while user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def activate_existing_instance():
        """若程序已在运行，唤醒其窗口并退出当前进程。"""
        try:
            hwnd = user32.FindWindowW(TRAY_WND_CLASS, None)
            if hwnd:
                user32.PostMessageW(hwnd, WM_SHOW, 0, 0)
                return True
        except Exception:
            pass
        return False


# ============================================================
# 主程序
# ============================================================
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        global _tray_app
        _tray_app = self

        cfg = load_config()
        self.theme = cfg.get("theme", "dark")
        if self.theme not in THEMES:
            self.theme = "dark"
        self._themed = []
        self.topmost = False
        self.page_idx = 0
        self.pages = []
        self.page_names = []
        self.rb_buttons = []

        # 热键固定为 Ctrl+Q（不再支持自定义）
        self.hotkey = DEFAULT_HOTKEY
        self._tray_hwnd = None

        # 数据 / 抓取状态
        self.data = {}
        self._fetched = False
        self._fetching = False
        self._load_error = None
        self._visible = True

        self.title("三角洲每日助手")
        try:
            self.iconbitmap()
        except Exception:
            pass

        saved_geo = cfg.get("geometry")
        if saved_geo and isinstance(saved_geo, str) and "x" in saved_geo:
            self.geometry(saved_geo)
        else:
            self.geometry(WINDOW_SIZE)

        self.resizable(False, False)
        self.overrideredirect(True)
        self.configure(bg=THEMES[self.theme]["bg"])

        self.bg_canvas = tk.Canvas(self, highlightthickness=0, bd=0, bg=THEMES[self.theme]["bg"])
        self.bg_canvas.place(x=0, y=0, relwidth=1, relheight=1)

        self._build_toolbar()
        self._build_body()
        self._toolbar_themed = list(self._themed)

        # 首次打开：强制抓取（后台）
        self.refresh_data(force=True)

        self.bind_all("<MouseWheel>", self._on_wheel)
        self.bind_all("<Button-4>", lambda e: self.go_page(-1))
        self.bind_all("<Button-5>", lambda e: self.go_page(1))
        self.bind_all("<KeyPress-Down>", lambda e: self.go_page(1))
        self.bind_all("<KeyPress-Up>", lambda e: self.go_page(-1))
        self.bind_all("<KeyPress-Right>", lambda e: self.go_page(1))
        self.bind_all("<KeyPress-Left>", lambda e: self.go_page(-1))

        self.update_idletasks()
        self.deiconify()
        self._apply_round_corners()
        self._make_taskbar_visible()

        # 启动全局热键（隐藏窗口）+ 系统托盘（同一隐藏窗口承载）
        if sys.platform.startswith("win"):
            threading.Thread(target=_hotkey_loop, daemon=True).start()

    # ---------- 主题着色 ----------
    def style(self, w, bg=None, fg=None, border=None):
        c = THEMES[self.theme]
        if bg:
            w.configure(bg=c[bg])
        if fg:
            w.configure(fg=c[fg])
        if border:
            try:
                w.configure(highlightbackground=c[border])
            except Exception:
                pass
        self._themed.append((w, bg, fg, border))

    def apply_theme(self):
        c = THEMES[self.theme]
        for w, bg, fg, border in self._themed:
            if bg:
                w.configure(bg=c[bg])
            if fg:
                w.configure(fg=c[fg])
            if border:
                try:
                    w.configure(highlightbackground=c[border])
                except Exception:
                    pass
        for rb in self.rb_buttons:
            try:
                rb.set_theme(self.theme)
            except Exception:
                pass
        self._draw_window_bg()
        try:
            self._settings_win.configure(bg=c["bg"])
        except Exception:
            pass

    # ---------- 圆角按钮工厂 ----------
    def _new_btn(self, parent, text, width, font, command):
        rb = RoundedButton(parent, text=text, width=width, height=30, radius=12,
                           font=font, command=command, canvas_bg=THEMES[self.theme]["bg"],
                           colors=BTN_COLORS)
        self.style(rb, bg="bg")
        self.rb_buttons.append(rb)
        return rb

    # ---------- 顶部工具栏 ----------
    def _build_toolbar(self):
        bar = tk.Frame(self)
        self.style(bar, bg="bg")
        bar.pack(fill="x", side="top")
        self.lbl_title = tk.Label(bar, text="三角洲每日助手", font=("Microsoft YaHei", 16, "bold"))
        self.style(self.lbl_title, bg="bg", fg="text")
        self.lbl_title.pack(side="left", padx=px(14), pady=px(10))
        self.lbl_title.bind("<ButtonPress-1>", self._start_drag)
        self.lbl_title.bind("<B1-Motion>", self._on_drag)

        right = tk.Frame(bar)
        self.style(right, bg="bg")
        right.pack(side="right", padx=px(10), pady=px(8))

        fnt = ("Microsoft YaHei", 11)
        # 工具栏顺序（从左到右）：置顶 | 设置 | ×
        self.btn_close = self._new_btn(right, "×", 40, fnt, self.on_close)
        self.btn_close.pack(side="right", padx=px(4))
        self.btn_settings = self._new_btn(right, "⚙", 40, fnt, self.open_settings)
        self.btn_settings.pack(side="right", padx=px(4))
        self.btn_top = self._new_btn(right, "置顶", 60, fnt, self.toggle_topmost)
        self.btn_top.pack(side="right", padx=px(4))

    # ---------- 主体 + 底部导航 ----------
    def _build_body(self):
        self.body = tk.Frame(self)
        self.style(self.body, bg="bg")
        self.body.pack(fill="both", expand=True)

        self.container = tk.Frame(self.body)
        self.style(self.container, bg="bg")
        self.container.pack(fill="both", expand=True, padx=px(14), pady=px(10))

        nav = tk.Frame(self.body)
        self.style(nav, bg="bg")
        nav.pack(fill="x", side="bottom")
        fnt = ("Microsoft YaHei", 11)
        self.btn_prev = self._new_btn(nav, "‹ 上一项", 96, fnt, lambda: self.go_page(-1))
        self.btn_prev.pack(side="left", padx=px(14), pady=px(6))
        self.lbl_page = tk.Label(nav, text="", font=("Microsoft YaHei", 11))
        self.style(self.lbl_page, bg="bg", fg="dim")
        self.lbl_page.pack(side="left", padx=px(10))
        self.btn_next = self._new_btn(nav, "下一项 ›", 96, fnt, lambda: self.go_page(1))
        self.btn_next.pack(side="right", padx=px(14), pady=px(6))

    # ---------- 数据抓取 / 缓存 ----------
    def refresh_data(self, force=False):
        if self._fetching:
            return
        if not force and self._fetched and self.data:
            return
        # 授权拦截：未激活且首次试用已用完 → 不联网抓取，界面显示激活提示
        if not lic.is_activated() and lic.is_trial_used():
            self._fetching = False
            self.refresh()
            return
        self._fetching = True
        self.refresh()  # 显示「正在抓取」
        threading.Thread(target=self._fetch_worker, daemon=True).start()

    def _fetch_worker(self):
        try:
            api = KkrbAPI()
            data = fetch_today_data(api)
            ok = bool(data.get("passwords") or data.get("manufacturing") or data.get("exchange"))
            result = (True, data if ok else (False, data.get("passwords_error") or
                                             data.get("manufacturing_error") or
                                             data.get("exchange_error") or "数据为空"))
        except Exception as e:
            result = (False, str(e))
        self.after(0, self._on_data, result)

    def _on_data(self, result):
        self._fetching = False
        ok, payload = result
        if ok:
            self.data = payload
            save_cache(payload)
            self._fetched = True
            self._load_error = None
            if not lic.is_activated():
                lic.mark_trial_used()   # 首次联网获取数据成功 → 试用次数用完
            self.refresh()
        else:
            cached = load_cache()
            if cached and (cached.get("passwords") or cached.get("manufacturing") or cached.get("exchange")):
                self.data = cached
                self._fetched = True
                self._load_error = "抓取失败，已加载离线缓存"
                self.refresh()
            else:
                self._load_error = payload
                self.refresh()

    # ---------- 渲染 ----------
    def refresh(self):
        self._themed = list(self._toolbar_themed)
        for ch in list(self.container.children.values()):
            ch.destroy()
        self.rb_buttons = [rb for rb in self.rb_buttons if rb.winfo_exists()]
        self.pages = []
        self.page_names = []

        # 未激活且试用已用完 → 显示激活提示页（不联网、不更新数据）
        if not lic.is_activated() and lic.is_trial_used():
            self._render_license_blocked()
            self.apply_theme()
            return

        if self._fetching and not (self.data and (self.data.get("passwords") or
                                                   self.data.get("manufacturing") or
                                                   self.data.get("exchange"))):
            self._render_message("正在抓取当日数据…", dim=True)
            self.apply_theme()
            return

        if self._load_error and not (self.data and (self.data.get("passwords") or
                                                     self.data.get("manufacturing") or
                                                     self.data.get("exchange"))):
            self._render_message("抓取失败：" + str(self._load_error), error=True,
                                 action="重试", on_action=lambda: self.refresh_data(force=True))
            self.apply_theme()
            return

        if not self.data:
            self._render_message("未找到数据文件，且抓取失败。", error=True)
            self.apply_theme()
            return

        self.apply_theme()
        if self.data.get("passwords"):
            p = tk.Frame(self.container)
            self.style(p, bg="bg")
            self._card_passwords(p)
            self.pages.append(p)
            self.page_names.append("今日密码")
        if self.data.get("manufacturing"):
            p = tk.Frame(self.container)
            self.style(p, bg="bg")
            self._card_list(p, "制造推荐", self.data["manufacturing"], True)
            self.pages.append(p)
            self.page_names.append("制造推荐")
        if self.data.get("exchange"):
            p = tk.Frame(self.container)
            self.style(p, bg="bg")
            self._card_list(p, "兑换推荐", self.data["exchange"], False)
            self.pages.append(p)
            self.page_names.append("兑换推荐")

        if not self.pages:
            self._render_message("今日数据为空。", error=True)
            return
        self.page_idx = min(self.page_idx, len(self.pages) - 1)
        self._show_page()

    def _render_message(self, msg, dim=False, error=False, action=None, on_action=None):
        col = "dim" if dim else ("danger" if error else "text")
        tip = tk.Label(self.container, text=msg, font=("Microsoft YaHei", 12),
                       justify="left", wraplength=px(400))
        self.style(tip, bg="bg", fg=col)
        tip.pack(padx=px(20), pady=px(20))
        if action and on_action:
            b = self._new_btn(self.container, action, 96, ("Microsoft YaHei", 11), on_action)
            b.pack(padx=px(20), pady=px(6))

    def _render_license_blocked(self):
        """未激活且试用已用完时的激活提示页（不联网、不更新数据）。"""
        tip = tk.Label(self.container,
                       text="需要激活后才能获取最新数据\n\n首次使用已为您提供一次免费查看。\n激活后永久使用，感谢支持！",
                       font=("Microsoft YaHei", 12), justify="left", wraplength=px(400))
        self.style(tip, bg="bg", fg="dim")
        tip.pack(padx=px(20), pady=px(14))
        b1 = self._new_btn(self.container, "获取激活码", 110, ("Microsoft YaHei", 11),
                           lambda: webbrowser.open(GET_CODE_URL))
        b1.pack(padx=px(20), pady=px(5))
        b2 = self._new_btn(self.container, "去设置激活", 110, ("Microsoft YaHei", 11),
                           self.open_settings)
        b2.pack(padx=px(20), pady=px(5))

    def _show_page(self):
        for i, p in enumerate(self.pages):
            if i == self.page_idx:
                p.pack(fill="both", expand=True)
            else:
                p.pack_forget()
        if self.page_names:
            self.lbl_page.configure(text="%d / %d  ·  %s" % (self.page_idx + 1, len(self.pages), self.page_names[self.page_idx]))
        self.apply_theme()

    def go_page(self, d):
        if not self.pages:
            return
        self.page_idx = (self.page_idx + d) % len(self.pages)
        self._show_page()

    def _on_wheel(self, ev):
        if ev.delta > 0:
            self.go_page(-1)
        else:
            self.go_page(1)

    # ---------- 卡片：密码 ----------
    def _card_passwords(self, parent):
        card, body = self._card(parent, "今日密码", "")
        grid = tk.Frame(body)
        self.style(grid, bg="card")
        grid.pack(fill="x")
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)
        pw = self.data["passwords"]
        items = [(mp, code) for mp, code in pw.items() if not any(k in mp for k in PASSWORD_FILTER)]
        for i, (mp, code) in enumerate(items):
            row = tk.Frame(grid, highlightthickness=1)
            self.style(row, bg="card2", border="border")
            row.grid(row=i // 2, column=i % 2, padx=px(6), pady=px(5), sticky="ew")
            name = tk.Label(row, text=mp, font=("Microsoft YaHei", 12))
            self.style(name, bg="card2", fg="dim")
            name.pack(side="left", padx=px(10), pady=px(8), fill="x", expand=True)
            c = tk.Label(row, text=code, font=("Consolas", 16, "bold"))
            self.style(c, bg="card2", fg="accent")
            c.pack(side="right", padx=px(10), pady=px(8))

    # ---------- 卡片：列表 ----------
    def _card_list(self, parent, title, items, with_place):
        card, body = self._card(parent, title, "%d 项" % len(items))
        items = sorted(items, key=lambda x: x.get("profit", 0), reverse=True)
        for it in items:
            row = tk.Frame(body, highlightthickness=1)
            self.style(row, bg="card2", border="border")
            row.pack(fill="x", padx=px(4), pady=px(4))
            name = it.get("item", "")
            sub = ("  [" + it["place"] + "]") if (with_place and it.get("place")) else ""
            main = tk.Label(row, text=name + sub, font=("Microsoft YaHei", 12), anchor="w")
            self.style(main, bg="card2", fg="text")
            main.pack(side="left", padx=px(10), pady=px(7), fill="x", expand=True)
            prof = it.get("profit", 0)
            pcol = "accent2" if prof >= 0 else "danger"
            ptxt = ("¥" if prof >= 0 else "-¥") + format(abs(prof), ",.2f")
            p = tk.Label(row, text=ptxt, font=("Consolas", 12, "bold"))
            self.style(p, bg="card2", fg=pcol)
            p.pack(side="right", padx=px(10), pady=px(7))

    # ---------- 卡片外壳 ----------
    def _card(self, parent, title, tag):
        card = tk.Frame(parent, highlightthickness=1, bd=0)
        self.style(card, bg="card", border="border")
        card.pack(fill="x", pady=px(8))
        head = tk.Frame(card)
        self.style(head, bg="card2")
        head.pack(fill="x")
        t = tk.Label(head, text=title, font=("Microsoft YaHei", 13, "bold"))
        self.style(t, bg="card2", fg="text")
        t.pack(side="left", padx=px(12), pady=px(8))
        if tag:
            tg = tk.Label(head, text=tag, font=("Microsoft YaHei", 10))
            self.style(tg, bg="card2", fg="dim")
            tg.pack(side="left")
        body = tk.Frame(card)
        self.style(body, bg="card")
        body.pack(fill="x", padx=px(12), pady=px(10))
        return card, body

    # ---------- 圆角窗口 ----------
    def _apply_round_corners(self):
        if not sys.platform.startswith("win"):
            return
        try:
            self.update_idletasks()
            hwnd = self.winfo_id()
            w = self.winfo_width()
            h = self.winfo_height()
            r = px(CORNER_RADIUS)
            if w < 10 or h < 10:
                self.after(100, self._apply_round_corners)
                return
            hrgn = ctypes.windll.gdi32.CreateRoundRectRgn(0, 0, w, h, r, r)
            ctypes.windll.user32.SetWindowRgn(hwnd, hrgn, True)
            self._draw_window_bg()
        except Exception:
            pass

    def _draw_window_bg(self):
        if not self.bg_canvas:
            return
        c = THEMES[self.theme]
        self.bg_canvas.configure(bg=c["bg"])
        w = self.winfo_width()
        h = self.winfo_height()
        r = px(CORNER_RADIUS)
        self.bg_canvas.delete("bg")
        self.bg_canvas.create_rectangle(0, 0, w, h, fill=c["bg"], outline="", tags="bg")
        self._round_rect_on_canvas(self.bg_canvas, 0, 0, w, h, r, fill=c["bg"], outline=c["border"], width=px(1), tags="bg")

    def _round_rect_on_canvas(self, canvas, x1, y1, x2, y2, r, **kw):
        pts = [x1, y1 + r, x1 + r, y1, x2 - r, y1, x2, y1 + r,
               x2, y2 - r, x2 - r, y2, x1 + r, y2, x1, y2 - r]
        canvas.create_polygon(pts, smooth=True, **kw)

    # ---------- 拖拽 ----------
    def _start_drag(self, ev):
        self._drag_x = ev.x_root
        self._drag_y = ev.y_root
        geo = self.geometry().split("+")
        self._drag_wx = int(geo[1]) if len(geo) > 1 else 0
        self._drag_wy = int(geo[2]) if len(geo) > 2 else 0

    def _on_drag(self, ev):
        if not hasattr(self, "_drag_x"):
            return
        nx = self._drag_wx + (ev.x_root - self._drag_x)
        ny = self._drag_wy + (ev.y_root - self._drag_y)
        self.geometry("+%d+%d" % (nx, ny))

    # ---------- 显示 / 隐藏 / 退出 ----------
    def show(self):
        # 用 Win32 SW_SHOWNOACTIVATE 直接显示，不走 Tk deiconify（后者会激活窗口、
        # 破坏 Alt 修饰键状态）——这样按住 Ctrl+Alt 连续点按 D 可反复触发全局热键
        if sys.platform.startswith("win"):
            try:
                user32.ShowWindow(self._real_hwnd(), 4)  # SW_SHOWNOACTIVATE
            except Exception:
                try:
                    self.deiconify()
                except Exception:
                    pass
        else:
            try:
                self.deiconify()
            except Exception:
                pass
        self._apply_round_corners()
        self._apply_taskbar_style()
        self._bring_to_front()
        if self.topmost:
            self._apply_topmost()
        self._visible = True

    def _real_hwnd(self):
        """获取真实的外层主窗口句柄（winfo_id 返回的是内部 TkChild）。"""
        hwnd = self.winfo_id()
        if sys.platform.startswith("win"):
            try:
                parent = ctypes.windll.user32.GetParent(hwnd)
                if parent:
                    hwnd = parent
            except Exception:
                pass
        return hwnd

    def _apply_taskbar_style(self):
        """一次性给窗口设置任务栏样式（APPWINDOW 加、TOOLWINDOW 去）。"""
        if not sys.platform.startswith("win"):
            return
        try:
            hwnd = self._real_hwnd()
            GWL_EXSTYLE = -20
            WS_EX_APPWINDOW = 0x00040000
            WS_EX_TOOLWINDOW = 0x00000080
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE,
                                                (style | WS_EX_APPWINDOW) & ~WS_EX_TOOLWINDOW)
        except Exception:
            pass

    def _make_taskbar_visible(self):
        """开启任务栏守护循环：Tk 会反复覆盖窗口样式，需持续重新断言。"""
        self._apply_taskbar_style()
        if getattr(self, "_taskbar_loop", False):
            return
        self._taskbar_loop = True

        def keep():
            self._apply_taskbar_style()
            try:
                self.after(500, keep)
            except Exception:
                pass
        keep()

    def _bring_to_front(self):
        """仅调整 z 序到最前并确保可见，不激活/不抢焦点——避免破坏 Alt 修饰键状态。"""
        if not sys.platform.startswith("win"):
            try:
                self.lift()
            except Exception:
                pass
            return
        try:
            hwnd = self._real_hwnd()
            # 若被最小化则还原（SW_SHOWNOACTIVATE 不抢焦点）
            if user32.IsIconic(hwnd):
                user32.ShowWindow(hwnd, 4)  # SW_SHOWNOACTIVATE
            HWND_TOPMOST, HWND_TOP = -1, 0
            SWP_NOMOVE, SWP_NOSIZE, SWP_NOACTIVATE, SWP_SHOWWINDOW = 0x2, 0x1, 0x10, 0x40
            flag = HWND_TOPMOST if self.topmost else HWND_TOP
            user32.SetWindowPos(hwnd, flag, 0, 0, 0, 0,
                                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW)
        except Exception:
            try:
                self.lift()
            except Exception:
                pass

    def on_close(self):
        # 默认缩到系统托盘，不退出（用 SW_HIDE 直接隐藏，避免激活副作用破坏修饰键状态）
        if sys.platform.startswith("win"):
            try:
                user32.ShowWindow(self._real_hwnd(), 0)  # SW_HIDE
            except Exception:
                try:
                    self.withdraw()
                except Exception:
                    pass
        else:
            try:
                self.withdraw()
            except Exception:
                pass
        self._visible = False

    def toggle_show(self):
        if self._visible:
            self.on_close()
        else:
            self.show()

    def _start_tray(self):
        """（已废弃）托盘由 _hotkey_loop 隐藏窗口统一承载，此处保留占位避免旧引用报错。"""
        pass

    def quit_app(self):
        if sys.platform.startswith("win"):
            try:
                _remove_tray_icon()
            except Exception:
                pass
        if self._tray_hwnd:
            try:
                user32.PostMessageW(self._tray_hwnd, WM_QUIT, 0, 0)
            except Exception:
                pass
        try:
            self.destroy()
        except Exception:
            pass
        os._exit(0)

    def _popup_tray_menu(self):
        """在主线程弹托盘右键菜单（tkinter 自绘，文字可靠可见）。"""
        global _menu_open
        if _menu_open:
            return
        _menu_open = True
        try:
            menu = tk.Menu(self, tearoff=0)
            menu.add_command(label="显示窗口", command=self.show)
            menu.add_command(label="退出", command=self.quit_app)
            pt = wt.POINT()
            try:
                user32.GetCursorPos(ctypes.byref(pt))
            except Exception:
                pt.x = pt.y = 0
            menu.tk_popup(pt.x, pt.y)
        finally:
            _menu_open = False

    # ---------- 主题 / 置顶 ----------
    def toggle_theme(self):
        self.theme = "light" if self.theme == "dark" else "dark"
        save_config(theme=self.theme)
        self.apply_theme()

    def toggle_topmost(self):
        self.topmost = not self.topmost
        self._apply_topmost()
        self.btn_top.set_text("取消置顶" if self.topmost else "置顶")

    def _apply_topmost(self):
        """用 Windows API 强制置顶/取消置顶（tk 的 -topmost 对无边框窗口常失效）。"""
        try:
            self.attributes("-topmost", self.topmost)
        except Exception:
            pass
        if not sys.platform.startswith("win"):
            return
        try:
            hwnd = self._real_hwnd()
            HWND_TOPMOST, HWND_NOTOPMOST = -1, -2
            SWP_NOMOVE, SWP_NOSIZE, SWP_NOACTIVATE = 0x2, 0x1, 0x10
            flag = HWND_TOPMOST if self.topmost else HWND_NOTOPMOST
            ctypes.windll.user32.SetWindowPos(
                hwnd, flag, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
        except Exception:
            pass

    # ---------- 设置页 ----------
    def open_settings(self):
        # 窗口已存在就恢复显示（不再用 withdraw 隐藏导致 lift 无效）
        if getattr(self, "_settings_win", None) and self._settings_win.winfo_exists():
            self._settings_win.deiconify()
            self._settings_win.lift()
            self._settings_win.focus_set()
            return

        w = tk.Toplevel(self)
        w.title("设置")
        w.resizable(False, False)
        w.configure(bg=THEMES[self.theme]["bg"])
        self._settings_win = w

        def close_settings():
            try:
                w.destroy()
            except Exception:
                pass
            self._settings_win = None

        w.protocol("WM_DELETE_WINDOW", close_settings)

        def s(widget, bg=None, fg=None):
            c = THEMES[self.theme]
            if bg:
                widget.configure(bg=c[bg])
            if fg:
                widget.configure(fg=c[fg])

        title = tk.Label(w, text="设置", font=("Microsoft YaHei", 16, "bold"))
        s(title, bg="bg", fg="text")
        title.pack(pady=px(14))

        # 快捷键（固定为 Ctrl+Q，不支持自定义）
        fk = tk.LabelFrame(w, text="全局快捷键（唤出/隐藏窗口）", font=("Microsoft YaHei", 11),
                           bd=1, relief="groove")
        s(fk, bg="bg", fg="dim")
        fk.pack(fill="x", padx=px(16), pady=px(6))
        tk.Label(fk, text="当前：" + hotkey_label(DEFAULT_HOTKEY) + "（固定，不可更改）",
                 font=("Microsoft YaHei", 12),
                 bg=THEMES[self.theme]["bg"], fg=THEMES[self.theme]["text"]
                 ).pack(padx=px(16), pady=(px(12), px(2)))
        tk.Label(fk, text="提示：热键格式须为 Ctrl+其他按键",
                 font=("Microsoft YaHei", 9),
                 bg=THEMES[self.theme]["bg"], fg=THEMES[self.theme]["dim"]
                 ).pack(pady=(0, px(10)))

        # 主题与置顶
        fo = tk.LabelFrame(w, text="外观与窗口", font=("Microsoft YaHei", 11), bd=1, relief="groove")
        s(fo, bg="bg", fg="dim")
        fo.pack(fill="x", padx=px(16), pady=px(6))

        btn_theme2 = self._new_btn(fo, "切换深/浅色", 140, ("Microsoft YaHei", 11), self.toggle_theme)
        btn_theme2.pack(pady=px(6))
        btn_top2 = self._new_btn(fo, "切换置顶", 140, ("Microsoft YaHei", 11), self.toggle_topmost)
        btn_top2.pack(pady=px(6))

        # 激活
        fa = tk.LabelFrame(w, text="激活", font=("Microsoft YaHei", 11), bd=1, relief="groove")
        s(fa, bg="bg", fg="dim")
        fa.pack(fill="x", padx=px(16), pady=px(6))

        c = THEMES[self.theme]
        activated = lic.is_activated()
        self._lic_status = tk.Label(fa, text="状态：已激活（永久）" if activated else "状态：未激活",
                                    font=("Microsoft YaHei", 10), anchor="w")
        s(self._lic_status, bg="bg", fg="accent2" if activated else "danger")
        self._lic_status.pack(fill="x", padx=px(16), pady=px(6))

        if not activated:
            tk.Label(fa, text="首次使用已提供一次免费查看。输入激活码后永久使用，\n"
                              "激活码请通过「获取激活码」按钮获取。",
                     font=("Microsoft YaHei", 10), justify="left", anchor="w",
                     bg=THEMES[self.theme]["bg"], fg=THEMES[self.theme]["dim"]).pack(
                fill="x", padx=px(16))

            entry_row = tk.Frame(fa)
            s(entry_row, bg="bg")
            entry_row.pack(fill="x", padx=px(16), pady=px(8))

            self._lic_entry = tk.Entry(entry_row, font=("Consolas", 13), bd=0,
                                       highlightthickness=1)
            self._lic_entry.configure(bg=c["card2"], fg=c["text"],
                                      highlightbackground=c["border"],
                                      highlightcolor=c["accent"])
            self._lic_entry.pack(side="left", fill="x", expand=True, ipady=px(5))

            btn_lic = self._new_btn(entry_row, "激活", 80, ("Microsoft YaHei", 11),
                                    lambda: self._settings_activate(entry_row))
            btn_lic.pack(side="left", padx=px(8))

            self._lic_err = tk.Label(fa, text="", font=("Microsoft YaHei", 10),
                                     bg=THEMES[self.theme]["bg"], fg=THEMES[self.theme]["danger"])
            self._lic_err.pack(fill="x", padx=px(16), pady=(0, px(6)))

        # 关于
        fabout = tk.LabelFrame(w, text="关于", font=("Microsoft YaHei", 11), bd=1, relief="groove")
        s(fabout, bg="bg", fg="dim")
        fabout.pack(fill="x", padx=px(16), pady=px(6))

        about_info = ("作者：逸飞\n"
                      "邮箱：707477488@qq.com\n"
                      "欢迎提供意见，感谢你的支持")
        lbl_about = tk.Label(fabout, text=about_info, font=("Microsoft YaHei", 10),
                             justify="left", anchor="w")
        s(lbl_about, bg="bg", fg="dim")
        lbl_about.pack(fill="x", padx=px(16), pady=px(10))

        # 退出
        btn_quit = self._new_btn(w, "完全退出程序", 160, ("Microsoft YaHei", 11), self.quit_app)
        btn_quit.pack(pady=px(16))

        # 等所有控件布局完成后，按内容自适应窗口大小，并居中到主窗口
        w.update_idletasks()
        req_w = max(px(320), w.winfo_reqwidth() + px(32))
        req_h = max(px(260), w.winfo_reqheight() + px(24))
        # 居中到主窗口
        self.update_idletasks()
        master_geo = self.geometry()
        parts = master_geo.replace("x", "+").split("+")
        try:
            mw = int(parts[0])
            mh = int(parts[1])
            mx = int(parts[2]) if len(parts) > 2 else 0
            my = int(parts[3]) if len(parts) > 3 else 0
        except Exception:
            mw, mh, mx, my = req_w, req_h, 0, 0
        cx = mx + (mw - req_w) // 2
        cy = my + (mh - req_h) // 2
        w.geometry("%dx%d+%d+%d" % (req_w, req_h, max(0, cx), max(0, cy)))
        w.focus_set()

    def _settings_activate(self, entry_row):
        """设置页内的激活处理：校验、记录机器码、立即恢复数据更新。"""
        key = self._lic_entry.get().strip()
        if not key:
            self._lic_err.configure(text="请输入激活码")
            return
        ok, result = lic.try_activate(key)
        if ok:
            c = THEMES[self.theme]
            self._lic_err.configure(text="", fg=c["danger"])
            self._lic_status.configure(text="状态：已激活（永久）", fg=c["accent2"])
            entry_row.destroy()
            messagebox.showinfo("激活成功", "激活成功，感谢支持！")
            self.refresh_data(force=True)
        else:
            self._lic_err.configure(text=result, fg=THEMES[self.theme]["danger"])

    # ---------- 关闭时保存位置 ----------
    def destroy(self):
        try:
            save_config(geometry=self.geometry())
        except Exception:
            pass
        super().destroy()


def main():
    # 单实例：若已在运行，唤醒其窗口后退出
    if sys.platform.startswith("win"):
        try:
            if activate_existing_instance():
                return
            kernel32.CreateMutexW(None, True, SINGLE_INSTANCE_MUTEX)
        except Exception:
            pass

    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
