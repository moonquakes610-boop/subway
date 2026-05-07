"""
自检：确认当前终端用的就是 E 盘工程里的代码，且「宠物」查询有结果。

在项目根目录执行：
    py -3 scripts\\verify_carry_on_e_drive.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))


def main() -> int:
    import src.reference_data as ref

    print("当前工作目录:", os.getcwd())
    print("reference_data.py:", Path(ref.__file__).resolve())
    print("禁带 JSON:", ref.REF_DIR / "prohibited_items.json")
    for q in ("宠物", "小猫", "鼠标"):
        r = ref.check_prohibited_carry(q)
        v = r.get("verdict")
        n = len(r.get("matches") or [])
        print(f"  查询「{q}」→ verdict={v}, 命中类别数={n}")
    if "e:\\beijingsubwaysystem" not in str(Path(ref.__file__).resolve()).lower():
        print("\n[提示] reference_data.py 不在 E:\\BeijingSubwaySystem 下，可能启动了别的文件夹里的工程。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
