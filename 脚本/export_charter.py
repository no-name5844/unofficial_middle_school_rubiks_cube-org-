#!/usr/bin/env python3
"""从数据库导出章程/细则为 Markdown，保留多行格式。

用法：
  python3 export_charter.py                          # 导出「章程」
  python3 export_charter.py 细则                       # 导出全部细则（多文件合并）
  python3 export_charter.py 运营委员会临时细则           # 按文件名导出单个细则
  python3 export_charter.py 章程 out.md                # 指定输出文件名
  python3 export_charter.py 章程 out.md --force         # 强制覆盖已存在的文件
  python3 export_charter.py 细则 -                     # 输出到标准输出
  python3 export_charter.py --list                     # 列出数据库中所有可导出的文件

时间戳检验：
  - 默认导出到「导出_章程_20260731_210000.md」这类带时间戳的文件，永不覆盖
  - 若指定了已存在的文件名，会比较文件修改时间与当前时间，非 --force 拒绝覆盖
"""

import sqlite3, sys, os
from datetime import datetime

# 自动定位 charter.db：先查当前目录，再查脚本所在目录的上一级（仓库根）
DB_PATH = next(
    (p for p in ['charter.db', os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'charter.db')]
     if os.path.exists(p)),
    'charter.db',
)

def build_markdown_by_file(db: sqlite3.Connection, file_name: str, source: str) -> str:
    """按单个文件名导出"""
    chs = db.execute(
        "SELECT DISTINCT chapter FROM articles WHERE source=? AND file_name=? ORDER BY id",
        (source, file_name)
    ).fetchall()
    if not chs:
        return None
    lines = [f'# {file_name}\n']
    for (ch,) in chs:
        arts = db.execute(
            "SELECT article_cn, content, hash FROM articles WHERE source=? AND file_name=? AND chapter=? ORDER BY article_num",
            (source, file_name, ch)
        ).fetchall()
        lines.append(f'\n## {ch}\n')
        for cn, txt, hv in arts:
            # 有哈希则输出 **第X条#hash**，否则回退旧式 **第X条**
            title = f'**{cn}#{hv}**' if hv else f'**{cn}**'
            lines.append(f'{title} {txt}\n')
        lines.append('\n---')
    return '\n'.join(lines)

def build_markdown_merged(db: sqlite3.Connection, source: str) -> str:
    """按 source 导出（多文件合并，按 file_name 分组）"""
    files = db.execute(
        "SELECT DISTINCT file_name FROM articles WHERE source=? ORDER BY file_name",
        (source,)
    ).fetchall()
    if not files:
        return None
    lines = [f'# {source}\n']
    for (fname,) in files:
        result = build_markdown_by_file(db, fname, source)
        if result:
            # 去掉首行标题，追加内容
            lines.append(result.split('\n', 1)[1] if '\n' in result else result)
    return '\n'.join(lines)

def export(source: str, outfile=None, force: bool = False):
    db = sqlite3.connect(DB_PATH)

    # 判断是文件名还是 source 类别
    is_file = db.execute(
        "SELECT COUNT(*) FROM articles WHERE file_name=?",
        (source,)
    ).fetchone()[0] > 0

    if is_file:
        # 由文件名判定来源：含「细则」即为细则，否则为章程（不可仅按 .md 后缀判断）
        src = '细则' if '细则' in source else '章程'
        result = build_markdown_by_file(db, source, src)
    else:
        result = build_markdown_merged(db, source)

    db.close()

    if result is None:
        print(f'❌ 未找到可导出的内容：{source}')
        return None

    # 标准输出模式
    if outfile == '-':
        print(result)
        return None

    # 默认：带时间戳的文件名
    if outfile is None:
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        label = source.replace('.md', '').replace(' ', '_')
        outfile = f'导出_{label}_{ts}.md'

    # 时间戳检验
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

def list_files():
    db = sqlite3.connect(DB_PATH)
    for row in db.execute('''
        SELECT file_name, source, COUNT(*) as cnt
        FROM articles WHERE file_name != ''
        GROUP BY file_name, source ORDER BY source, file_name
    ''').fetchall():
        print(f'  {row[1]:4}  {row[2]:>3}条  {row[0]}')
    db.close()

if __name__ == '__main__':
    positional = [a for a in sys.argv[1:] if not a.startswith('--')]
    flags = [a for a in sys.argv[1:] if a.startswith('--')]
    force = '--force' in flags

    if '--list' in flags:
        list_files()
        sys.exit(0)

    src = positional[0] if len(positional) >= 1 else '章程'
    out = positional[1] if len(positional) >= 2 else None

    r = export(src, out, force)
    if r:
        print(f'✅ 已导出：{r}')
    elif out != '-':
        print('❌ 导出已取消')
