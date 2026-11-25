# -*- coding: utf-8 -*-
"""三角洲每日助手 · 激活码生成工具（管理员用）。

用法：
    python gen_license.py [数量] [输出文件]

示例：
    python gen_license.py        生成 1 个永久激活码
    python gen_license.py 5      生成 5 个永久激活码
    python gen_license.py 3 激活码.txt   生成 3 个并导出到指定文件

导出的 txt 文件格式：每行一个激活码。
激活码为一次性：在一台电脑上激活后即与该电脑绑定；卸载重装同机不可再激活。
"""
import os
import sys
from datetime import datetime

import license as lic


def desktop_path():
    """获取当前用户桌面路径（兼容 OneDrive/系统重定向）。"""
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(260)
        if ctypes.windll.shell32.SHGetFolderPathW(None, 0x10, None, 0, buf) == 0:
            return buf.value
    except Exception:
        pass
    return os.path.join(os.path.expanduser("~"), "Desktop")


def main():
    args = [a for a in sys.argv[1:]]

    count = 1
    if len(args) >= 1:
        try:
            count = int(args[0])
        except ValueError:
            print("错误：数量必须是整数")
            return 1
    if count < 1:
        print("错误：数量至少为 1")
        return 1

    out_file = None
    if len(args) >= 2:
        out_file = args[1]
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_file = os.path.join(desktop_path(), "激活码_%s.txt" % ts)

    print("类型  : 永久")
    print("数量  : %d" % count)
    print("-" * 40)

    lines = []
    for i in range(1, count + 1):
        key = lic.create_key()
        lines.append(key)
        print("%2d. %s" % (i, key))

    try:
        with open(out_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print("-" * 40)
        print("已导出: %s" % out_file)
    except OSError as e:
        print("导出失败: %s" % e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())