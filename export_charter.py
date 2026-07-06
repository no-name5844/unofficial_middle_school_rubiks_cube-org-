#!/usr/bin/env python3
"""从数据库导出章程/细则为 Markdown，保留多行格式。

用法：
  python3 export_charter.py                  # 导出「章程」，文件名自动带时间戳
  python3 export_charter.py 细则              # 导出「细则」
  python3 export_charter.py 章程 out.md       # 指定输出文件名
  python3 export_charter.py 章程 out.md --force   # 强制覆盖已存在的文件
  python3 export_charter.py 细则 -            # 输出到标准输出（不写文件）

时间戳检验：
  - 默认导出到「导出_章程_20260706_230000.md」这类带时间戳的文件，永不覆盖
  - 若指定了已存在的文件名，会比较文件修改时间与当前时间，非 --force 拒绝覆盖
"""

import sqlite3, sys, os
from datetime import datetime

DB_PATH = 'charter.db'

def build_markdown(source: str) -> str:
    db = sqlite3.connect(DB_PATH)
    chs = db.execute(
        "SELECT DISTINCT chapter FROM articles WHERE source=? ORDER BY id",
        (source,)
    ).fetchall()
    lines = [f'# {source}\n']
    for (ch,) in chs:
        arts = db.execute(
            "SELECT article_cn, content FROM articles WHERE source=? AND chapter=? ORDER BY article_num",
            (source, ch)
        ).fetchall()
        lines.append(f'\n## {ch}\n')
        for cn, txt in arts:
            lines.append(f'**{cn}** {txt}\n')
        lines.append('\n---')
    db.close()
    return '\n'.join(lines)

def export(source: str, outfile=None, force: bool = False):
    result = build_markdown(source)

    # 标准输出模式
    if outfile == '-':
        print(result)
        return None

    # 默认：带时间戳的文件名，避免任何覆盖
    if outfile is None:
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        outfile = f'导出_{source}_{ts}.md'

    # 时间戳检验：已存在则比对修改时间
    if os.path.exists(outfile):
        mtime = datetime.fromtimestamp(os.path.getmtime(outfile))
        age = datetime.now() - mtime
        if not force:
            print(f'⚠️  目标文件已存在：{outfile}')
            print(f'     最后修改：{mtime.strftime("%Y-%m-%d %H:%M:%S")}（{age}前）')
            print(f'     如需覆盖，请加 --force 参数')
            return None
        else:
            print(f'🔁 已强制覆盖：{outfile}（原文件 {mtime.strftime("%Y-%m-%d %H:%M:%S")}）')

    with open(outfile, 'w', encoding='utf-8') as f:
        f.write(result)
    return outfile

if __name__ == '__main__':
    positional = [a for a in sys.argv[1:] if not a.startswith('--')]
    flags = [a for a in sys.argv[1:] if a.startswith('--')]
    force = '--force' in flags

    src = positional[0] if len(positional) >= 1 else '章程'
    out = positional[1] if len(positional) >= 2 else None

    r = export(src, out, force)
    if r:
        print(f'✅ 已导出：{r}')
    elif out != '-':
        print('❌ 导出已取消')
