# -*- coding: utf-8 -*-
"""三角洲每日助手 · 激活码生成工具（图形窗口版，双击即可使用）。

用法：双击本文件（.pyw 不会闪黑框）。输入数量 → 点「生成」→
激活码自动显示并导出为 激活码_时间.txt，也可一键复制全部。
"""
import os
import sys
import tkinter as tk
from tkinter import scrolledtext, messagebox
from datetime import datetime

# 保证从任何位置双击/运行时都能找到 license.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import license as lic

BG = "#0e1116"
CARD = "#1a2029"
TEXT = "#e6eaf0"
DIM = "#9aa4b2"
ACCENT = "#f5b942"


def desktop_path():
    """获取当前用户桌面路径（兼容 OneDrive/系统重定向）。"""
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(260)
        # CSIDL_DESKTOPDIRECTORY = 0x10
        if ctypes.windll.shell32.SHGetFolderPathW(None, 0x10, None, 0, buf) == 0:
            return buf.value
    except Exception:
        pass
    return os.path.join(os.path.expanduser("~"), "Desktop")


class GenWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("三角洲每日助手 · 激活码生成")
        self.resizable(False, False)
        self.configure(bg=BG)

        tk.Label(self, text="激活码生成（永久）", font=("Microsoft YaHei", 14, "bold"),
                 bg=BG, fg=TEXT).pack(pady=(14, 8))

        row = tk.Frame(self, bg=BG)
        row.pack(fill="x", padx=16)
        tk.Label(row, text="生成数量：", font=("Microsoft YaHei", 11),
                 bg=BG, fg=DIM).pack(side="left")
        self.var_count = tk.StringVar(value="1")
        sp = tk.Spinbox(row, from_=1, to=9999, textvariable=self.var_count, width=6,
                        font=("Microsoft YaHei", 11), bd=0, highlightthickness=1,
                        bg=CARD, fg=TEXT, buttonbackground="#20262f", insertbackground=TEXT)
        sp.pack(side="left", padx=(6, 12), ipady=2)

        self.btn_gen = tk.Button(row, text="生 成", font=("Microsoft YaHei", 11),
                                 command=self.generate, bg=ACCENT, fg="#1b2230",
                                 activebackground="#d9a02c", activeforeground="#1b2230",
                                 relief="flat", padx=20, pady=2, cursor="hand2")
        self.btn_gen.pack(side="left")

        self.txt = scrolledtext.ScrolledText(self, width=46, height=13,
                                             font=("Consolas", 12), bg=CARD, fg=TEXT,
                                             relief="flat", state="disabled", wrap="none")
        self.txt.pack(fill="both", expand=True, padx=16, pady=10)

        self.lbl_path = tk.Label(self, text="", font=("Microsoft YaHei", 9),
                                 bg=BG, fg=DIM, anchor="w")
        self.lbl_path.pack(fill="x", padx=16)

        btn_row = tk.Frame(self, bg=BG)
        btn_row.pack(pady=(8, 14))
        self.btn_copy = self._mk_btn(btn_row, "复制全部", self.copy_all)
        self.btn_copy.pack(side="left", padx=6)
        self.btn_save = self._mk_btn(btn_row, "导出 txt", self.save_file)
        self.btn_save.pack(side="left", padx=6)

        self._keys = []
        self._out_file = None

    def _mk_btn(self, parent, text, command):
        return tk.Button(parent, text=text, font=("Microsoft YaHei", 11),
                         command=command, bg=CARD, fg=TEXT,
                         activebackground="#2a313c", activeforeground=TEXT,
                         relief="flat", padx=18, pady=3, cursor="hand2")

    def generate(self):
        try:
            n = int(self.var_count.get())
        except ValueError:
            messagebox.showerror("错误", "数量必须是整数")
            return
        if n < 1 or n > 9999:
            messagebox.showerror("错误", "数量需在 1 ~ 9999 之间")
            return
        self._keys = [lic.create_key() for _ in range(n)]
        self.txt.configure(state="normal")
        self.txt.delete("1.0", "end")
        self.txt.insert("end", "\n".join(self._keys) + ("\n" if self._keys else ""))
        self.txt.configure(state="disabled")
        self._save()
        self.lbl_path.configure(text="已导出：%s" % self._out_file)

    def _save(self):
        if not self._keys:
            return
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = os.path.join(desktop_path(), "激活码_%s.txt" % ts)
        with open(out, "w", encoding="utf-8") as f:
            f.write("\n".join(self._keys) + "\n")
        self._out_file = out

    def save_file(self):
        if not self._keys:
            messagebox.showinfo("提示", "请先生成激活码")
            return
        self._save()
        self.lbl_path.configure(text="已导出：%s" % self._out_file)
        messagebox.showinfo("完成", "已导出：\n%s" % self._out_file)

    def copy_all(self):
        if not self._keys:
            messagebox.showinfo("提示", "请先生成激活码")
            return
        self.clipboard_clear()
        self.clipboard_append("\n".join(self._keys))
        messagebox.showinfo("完成", "已复制 %d 个激活码到剪贴板" % len(self._keys))


if __name__ == "__main__":
    GenWindow().mainloop()