# -*- coding: utf-8 -*-
import os
import sys
import subprocess
import ctypes
import winreg
import shutil
import tkinter as tk
from tkinter import messagebox

APP_NAME = "三角洲每日助手"
APP_EXE = "三角洲每日助手.exe"
REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\DeltaForceDaily"
APPDATA_SUB = "DeltaForceNative"


def kill_proc():
    # taskkill 中文镜像名偶发失效，加 PowerShell 兜底双保险
    for cmd in (
        ["taskkill", "/IM", APP_EXE, "/F", "/T"],
        ["powershell", "-NoProfile", "-Command",
         "Get-Process -Name '三角洲每日助手' -ErrorAction SilentlyContinue | Stop-Process -Force"],
    ):
        try:
            subprocess.run(cmd, capture_output=True,
                           creationflags=0x08000000, timeout=30)
        except Exception:
            pass


def remove_file(p):
    try:
        if os.path.isfile(p):
            os.remove(p)
    except Exception:
        pass


def remove_dir(p):
    try:
        if os.path.isdir(p):
            shutil.rmtree(p, ignore_errors=True)
    except Exception:
        pass


def get_install_dir():
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            with winreg.OpenKey(hive, REG_PATH) as k:
                u = winreg.QueryValueEx(k, "UninstallString")[0]
                d = os.path.dirname(u.strip().strip('"'))
                if d and os.path.isdir(d):
                    return d
        except Exception:
            continue
    for cand in (r"C:\Program Files\DeltaForceDaily",
                 r"C:\Program Files (x86)\DeltaForceDaily"):
        if os.path.isdir(cand):
            return cand
    return None


def uninstall():
    install_dir = get_install_dir()
    kill_proc()
    if install_dir:
        remove_file(os.path.join(install_dir, APP_EXE))
        remove_file(os.path.join(install_dir, "Uninstall.exe"))
        remove_dir(install_dir)

    sm = os.path.join(
        os.environ.get("APPDATA", ""),
        "Microsoft", "Windows", "Start Menu", "Programs", "DeltaForceDaily")
    remove_file(os.path.join(sm, "三角洲每日助手.lnk"))
    remove_file(os.path.join(sm, "卸载三角洲每日助手.lnk"))
    remove_dir(sm)

    desk = os.path.join(os.path.expanduser("~"), "Desktop")
    remove_file(os.path.join(desk, "三角洲每日助手.lnk"))

    la = os.environ.get("LOCALAPPDATA") or os.path.join(
        os.path.expanduser("~"), "AppData", "Local")
    remove_dir(os.path.join(la, APPDATA_SUB))

    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            winreg.DeleteKey(hive, REG_PATH)
        except Exception:
            pass


def main():
    root = tk.Tk()
    root.withdraw()
    try:
        if not messagebox.askyesno(
                APP_NAME,
                "确定要卸载「%s」吗？\n\n将删除程序文件、快捷方式及本地缓存数据。" % APP_NAME):
            sys.exit(0)
        uninstall()
        messagebox.showinfo(APP_NAME, "卸载完成。\n\n已删除程序文件、快捷方式与本地缓存。")
    except Exception as e:
        messagebox.showerror(APP_NAME, "卸载时出现错误：\n%s" % e)
    finally:
        sys.exit(0)


if __name__ == "__main__":
    main()
