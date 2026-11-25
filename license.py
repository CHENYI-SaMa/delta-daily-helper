# -*- coding: utf-8 -*-
"""三角洲每日助手 · 离线授权模块（一次性永久激活码 + 首次试用，纯标准库）。

规则：
- 只提供永久激活码；激活码为一次性，任意电脑第一次激活都成功。
- 激活时自动记录「当前机器码」；之后卸载重装再输同一条码：
    机器码相同（同机重装）→ 禁用，提示已使用；
    机器码不同（换了硬件/系统）→ 允许重新激活并绑定新机器码。
- 首次试用：未激活且尚未用过试用时，允许联网获取一次数据；
  获取成功后记录「试用已用」（注册表，卸载重装不重置）。
- 授权状态保存在 %LOCALAPPDATA%\\DeltaForceNative\\license.json；
  「已使用激活码→机器码」与「试用标记」保存在注册表 HKCU\\Software\\DeltaForceDaily。
"""
import hmac
import json
import os
import uuid
from datetime import datetime

# ============================================================
# 常量与配置
# ============================================================
CONFIG_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local")),
                          "DeltaForceNative")
LICENSE_PATH = os.path.join(CONFIG_DIR, "license.json")

REG_ROOT = r"Software\DeltaForceDaily"     # HKCU 下的授权记录键
REG_USED = "UsedCodes"                     # {激活码: 机器码}
REG_TRIAL = "TrialUsed"                    # "1" = 首次试用已用完

TYPE_PERM = "P"    # 永久激活码

BASE32_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
VERSION_BYTE = 0x0A
GROUP = 5          # 激活码分组位数

# 密钥：运行时拼装，避免源码中直接出现明文（可进一步混淆，但任何离线方案都无法根治提取）
_SECRET_PARTS = [0x44, 0x46, 0x44, 0x2d, 0x44, 0x41, 0x49, 0x4c,
                 0x59, 0x21, 0x4c, 0x49, 0x43, 0x45, 0x4e, 0x53, 0x45, 0x33,
                 0x8C, 0x9B, 0xAA, 0xBB, 0xCD, 0xDE, 0xEF, 0xF0]


def _secret():
    return bytes(b ^ 0xA5 for b in _SECRET_PARTS)


# ============================================================
# Base32（自实现，兼容 Python 3.8+）
# ============================================================
_B32_REV = {c: i for i, c in enumerate(BASE32_ALPHABET)}


def b32e(data):
    out = []
    acc = 0
    bits = 0
    for b in data:
        acc = (acc << 8) | b
        bits += 8
        while bits >= 5:
            bits -= 5
            out.append(BASE32_ALPHABET[(acc >> bits) & 0x1F])
    if bits > 0:
        out.append(BASE32_ALPHABET[(acc << (5 - bits)) & 0x1F])
    return "".join(out)


def b32d(text):
    out = bytearray()
    acc = 0
    bits = 0
    for ch in text.rstrip("="):
        if ch not in _B32_REV:
            raise ValueError("invalid base32 char: %r" % ch)
        acc = (acc << 5) | _B32_REV[ch]
        bits += 5
        if bits >= 8:
            bits -= 8
            out.append((acc >> bits) & 0xFF)
    return bytes(out)


def normalize_key(key):
    """清洗用户输入的激活码：转大写、去掉分隔符和空白。"""
    return "".join(key.upper().split()).replace("-", "").replace(" ", "")


def format_key(compact):
    """把 20 位紧凑码格式化为 5-5-5-5 分组样式。"""
    return "-".join(compact[i:i + GROUP] for i in range(0, len(compact), GROUP))


# ============================================================
# 机器码
# ============================================================
def get_machine_code():
    """生成并返回本机机器码（16 位大写字母数字）。"""
    parts = []
    # 1) 系统 MachineGuid（重装系统才变，足够稳定）
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SOFTWARE\Microsoft\Cryptography") as k:
            parts.append(winreg.QueryValueEx(k, "MachineGuid")[0] or "")
    except Exception:
        pass
    # 2) 系统分区卷序列号
    try:
        import ctypes
        drive = os.environ.get("SystemDrive", "C:") + "\\"
        serial = ctypes.c_uint32(0)
        ctypes.windll.kernel32.GetVolumeInformationW(
            drive, None, 0, ctypes.byref(serial), None, None, None, 0)
        if serial.value:
            parts.append(str(serial.value))
    except Exception:
        pass
    # 3) 兜底：本机网卡字节
    if not any(parts):
        try:
            parts.append(str(uuid.getnode()))
        except Exception:
            parts.append("unknown")
    import hashlib
    raw = "|".join(parts).encode("utf-8", "replace")
    return b32e(hashlib.sha256(raw).digest())[:16]


# ============================================================
# 激活码生成 / 校验（生成与校验共用同一套逻辑）
# ============================================================
def create_key():
    """生成永久激活码（返回 5-5-5-5 分组样式），不绑定任何机器。"""
    body = bytes([VERSION_BYTE, ord(TYPE_PERM)]) + os.urandom(7)   # 9 字节
    sig = hmac.new(_secret(), body, "sha256").digest()[:3]
    data = body + sig                                              # 12 字节
    compact = b32e(data)                                           # 20 位 Base32
    return format_key(compact)


def verify_key(key):
    """校验激活码真伪。成功返回 (True, None)；失败返回 (False, 错误信息)。"""
    compact = normalize_key(key)
    if len(compact) != 20:
        return False, "激活码长度不正确"
    try:
        data = b32d(compact)
    except Exception:
        return False, "激活码格式不正确"
    if len(data) != 12:
        return False, "激活码格式不正确"
    if data[0] != VERSION_BYTE:
        return False, "激活码版本不支持"

    body, sig = data[:9], data[9:]
    expect = hmac.new(_secret(), body, "sha256").digest()[:3]
    if not hmac.compare_digest(sig, expect):
        return False, "激活码无效"

    key_type = chr(body[1])
    if key_type != TYPE_PERM:
        return False, "激活码类型无效"
    return True, None


# ============================================================
# 已使用激活码 → 机器码 记录（注册表持久化，卸载重装仍在）
# ============================================================
def _read_used():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_ROOT) as k:
            value, _ = winreg.QueryValueEx(k, REG_USED)
        used = json.loads(value or "{}")
        return used if isinstance(used, dict) else {}
    except Exception:
        return {}


def _write_used(used):
    try:
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_ROOT) as k:
            winreg.SetValueEx(k, REG_USED, 0, winreg.REG_SZ,
                              json.dumps(used, ensure_ascii=False))
    except Exception:
        pass


def is_code_used(key):
    return normalize_key(key) in _read_used()


# ============================================================
# 首次试用标记（注册表，卸载重装不重置）
# ============================================================
def is_trial_used():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_ROOT) as k:
            value, _ = winreg.QueryValueEx(k, REG_TRIAL)
        return str(value) == "1"
    except FileNotFoundError:
        return False
    except Exception:
        return False


def mark_trial_used():
    try:
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_ROOT) as k:
            winreg.SetValueEx(k, REG_TRIAL, 0, winreg.REG_SZ, "1")
    except Exception:
        pass


# ============================================================
# 激活状态存取
# ============================================================
def load_state():
    try:
        with open(LICENSE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(LICENSE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False)
    except Exception:
        pass


# ============================================================
# 激活 / 校验对外接口
# ============================================================
def try_activate(key):
    """永久码一次性激活：激活时记录机器码；同机重装禁用，机器码变了允许重新激活。"""
    ok, err = verify_key(key)
    if not ok:
        return False, err
    compact = normalize_key(key)
    used = _read_used()
    machine = get_machine_code()

    if compact in used:
        if used[compact] == machine:
            return False, "该激活码已在此电脑使用过，卸载重装后无法再次激活"
        # 机器码已变化（换硬件/重装系统）→ 允许重新激活并更新绑定
        used[compact] = machine
    else:
        used[compact] = machine

    save_state({
        "code": compact,
        "type": TYPE_PERM,
        "machine": machine,
        "activated_at": datetime.now().isoformat(timespec="seconds"),
    })
    _write_used(used)
    return True, TYPE_PERM


def is_activated():
    """当前是否已激活（永久授权）。"""
    st = load_state()
    return bool(st and st.get("type") == TYPE_PERM)


if __name__ == "__main__":
    # 自检：生成 → 激活 → 同码再激活（同机禁用 / 换机码允许）→ 篡改检测
    import tempfile
    lic_path = os.path.join(tempfile.gettempdir(), "test_license.json")
    old_path, LICENSE_PATH = LICENSE_PATH, lic_path
    try:
        if os.path.exists(lic_path):
            os.remove(lic_path)
        assert is_activated() is False, "未激活应返回 False"
        k = create_key()
        print("永久激活码:", k)
        assert verify_key(k) == (True, None)
        assert verify_key(k + "A")[0] is False, "篡改应校验失败"

        ok, t = try_activate(k)
        assert ok and t == TYPE_PERM, (ok, t)
        assert is_activated() is True, "激活后应有效"

        # 模拟卸载重装（删 license.json），同机再输入同码 → 禁用
        os.remove(lic_path)
        ok2, err2 = try_activate(k)
        assert not ok2 and "已在此电脑使用过" in err2, (ok2, err2)

        # 模拟机器码变化：改写注册表记录为另一台机器 → 允许重新激活
        k2 = create_key()
        _write_used({k2: "DIFFERENTMACHINE0000"})
        ok3, err3 = try_activate(k2)
        assert ok3, (ok3, err3)
        print("生成->激活->同机重装禁用->换机码重激活 全部通过")
    finally:
        LICENSE_PATH = old_path
        if os.path.exists(lic_path):
            os.remove(lic_path)
        _write_used({})                       # 清理注册表使用记录
        try:
            import winreg
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_ROOT) as kk:
                winreg.SetValueEx(kk, REG_TRIAL, 0, winreg.REG_SZ, "0")
        except Exception:
            pass