"""
项目根目录启动脚本（毕业设计答辩时双击或命令行运行均可）。

用法示例：
    python main.py --from 西单 --to 圆明园
    python main.py --from 西单 --to 圆明园 --out output/guide.txt --export-json output/guide.json
    python main.py --from 西单 --to 圆明园 --no-regulations
"""

import sys

from src.cli import main

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n[信息] 已中断。", file=sys.stderr)
        raise SystemExit(130)
