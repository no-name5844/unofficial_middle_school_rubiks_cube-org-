#!/usr/bin/env python3
"""从 Markdown 章程/细则文件 UPSERT（非破坏性推送）到 charter.db。

设计原则（区别于已删除的 rebuild_db.py）：
  - 绝不 DROP / 删除任何表或行
  - 使用 ON CONFLICT(source, article_num, file_name) DO UPDATE 做幂等更新
  - 仅更新在文件中出现过的条文；未出现在文件中的旧条文原样保留

用法：
  python3 import_charter.py xssz魔方非官方组织临时章程.md
  python3 import_charter.py 运营委员会临时细则.md --source 细则
  python3 import_charter.py 运营委员会临时细则.md --version 通俗
  python3 import_charter.py xssz魔方非官方组织临时章程.md --dry-run
  python3 import_charter.py xssz魔方非官方组织临时章程.md --prune   # 清理该版本孤儿行
  说明：source 默认按文件名自动判定（含“细则”即细则，否则章程）；version 默认“严谨”。
"""

import sqlite3
import sys
import os
import re

# 自动定位 charter.db：先查当前目录，再查脚本所在目录的上一级（仓库根）
DB_PATH = next(
    (p for p in ['charter.db', os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'charter.db')]
     if os.path.exists(p)),
    'charter.db',
)

# 中文数字 -> int
_CN = {'零': 0, '一': 1, '二': 2, '两': 2, '三': 3, '四': 4, '五': 5,
       '六': 6, '七': 7, '八': 8, '九': 9}

def cn_to_int(s: str) -> int:
    """支持 一~九十九、一百零二、一百零五 等常见写法。"""
    if s.isdigit():
        return int(s)
    if s in _CN:
        return _CN[s]
    total = 0
    section = 0
    for ch in s:
        if ch == '百':
            section = (section or 1) * 100
            total += section
            section = 0
        elif ch == '十':
            section = (section or 1) * 10
            total += section
            section = 0
        elif ch == '零':
            pass
        elif ch in _CN:
            section = _CN[ch]
        else:
            raise ValueError(f'无法解析的数字：{ch}（来自 {s}）')
    return total + section

ART_RE = re.compile(r'^\*\*(第[一二三四五六七八九十百零\d]+条)\*\*')
CHAP_RE = re.compile(r'^##\s+(.+?)\s*$')


def parse_file(path: str):
    """返回 [(chapter, article_num, article_cn, content), ...]"""
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.read().split('\n')

    chapter = ''
    results = []
    buf = None  # 当前正在累积的 (cn, num, content_lines)

    def flush():
        nonlocal buf
        if buf is not None:
            cn, num, clines = buf
            # 去掉末尾的空行与章节分隔符（---），它们不是条文内容
            while clines and clines[-1].strip() in ('', '---'):
                clines.pop()
            # 去掉开头的空行
            while clines and clines[0].strip() == '':
                clines.pop(0)
            content = '\n'.join(clines)
            results.append((chapter, num, cn, content))
            buf = None

    for line in lines:
        m_art = ART_RE.match(line)
        m_chap = CHAP_RE.match(line)
        if m_chap and not m_art:
            flush()
            chapter = m_chap.group(1).strip()
            continue
        if m_art:
            flush()
            cn = m_art.group(1)            # 第四十七条
            num = cn_to_int(re.search(r'第(.+)条', cn).group(1))
            rest = line[m_art.end():].strip()
            buf = (cn, num, [rest] if rest else [])
            continue
        if buf is not None:
            buf[2].append(line)
    flush()
    return results


def upsert(db: sqlite3.Connection, rows, source: str, file_name: str, version: str, dry_run: bool):
    cur = db.cursor()
    stats = {'insert': 0, 'update': 0, 'unchanged': 0}
    for chapter, num, cn, content in rows:
        existing = cur.execute(
            "SELECT id, chapter, content FROM articles WHERE source=? AND article_num=? AND file_name=? AND version=?",
            (source, num, file_name, version)
        ).fetchone()
        if existing is None:
            if not dry_run:
                cur.execute(
                    "INSERT INTO articles (source, chapter, article_num, article_cn, content, file_name, version) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (source, chapter, num, cn, content, file_name, version)
                )
            stats['insert'] += 1
            print(f"  [{'DRY' if dry_run else '新增'}] {cn} (chapter={chapter}) [version={version}]")
        else:
            eid, echap, econtent = existing
            if econtent == content and echap == chapter:
                stats['unchanged'] += 1
            else:
                if not dry_run:
                    cur.execute(
                        "UPDATE articles SET chapter=?, content=? WHERE id=?",
                        (chapter, content, eid)
                    )
                stats['update'] += 1
                changed = []
                if echap != chapter:
                    changed.append(f'chapter: {echap!r} -> {chapter!r}')
                if econtent != content:
                    changed.append('content: 已更新')
                print(f"  [{'DRY' if dry_run else '更新'}] {cn} ({'; '.join(changed)}) [version={version}]")
    if not dry_run:
        db.commit()
    return stats


def prune_db(db: sqlite3.Connection, rows, source: str, file_name: str, version: str, dry_run: bool) -> int:
    """删除该 (source, file_name, version) 下、文件中已不再出现的旧编号行。

    重排编号（如 101→100）后，旧编号行会变成孤儿行（与重排后的新行撞 UNIQUE 键），
    必须在 UPSERT 之前清掉。非破坏性导入的「保留未出现旧条文」原则，在显式 --prune
    时让位于「与源文件严格一致」原则。version 限定只清理当前导入的那个版本。
    """
    keep = {num for _, num, _, _ in rows}
    cur = db.cursor()
    orphan = cur.execute(
        "SELECT id, article_num, article_cn FROM articles WHERE source=? AND file_name=? AND version=?",
        (source, file_name, version)
    ).fetchall()
    removed = 0
    for eid, num, cn in orphan:
        if num not in keep:
            removed += 1
            print(f"  [{'DRY' if dry_run else '删除'}] {cn} (article_num={num}) [version={version}] — 源文件已无此编号")
            if not dry_run:
                cur.execute("DELETE FROM articles WHERE id=?", (eid,))
    if removed and not dry_run:
        db.commit()
    return removed


def main():
    args = sys.argv[1:]
    dry_run = '--dry-run' in args
    prune = '--prune' in args
    version = '严谨'
    if '--version' in args:
        i = args.index('--version')
        version = args[i + 1]
        args = args[:i] + args[i + 2:]
    args = [a for a in args if a not in ('--dry-run', '--prune', '--version')]
    source = None  # 默认按文件名自动判定
    if '--source' in args:
        i = args.index('--source')
        source = args[i + 1]
        args = args[:i] + args[i + 2:]
    if not args:
        print('用法: python3 import_charter.py <markdown文件> [--source 章程|细则] [--version 严谨|通俗] [--dry-run] [--prune]')
        sys.exit(1)
    path = args[0]
    if not os.path.exists(path):
        print(f'❌ 文件不存在：{path}')
        sys.exit(1)
    file_name = os.path.basename(path)
    if source is None:
        source = '细则' if '细则' in file_name else '章程'

    rows = parse_file(path)
    print(f'📄 解析 {file_name}（source={source}, version={version}）：共 {len(rows)} 条')

    db = sqlite3.connect(DB_PATH)
    if prune:
        n = prune_db(db, rows, source, file_name, version, dry_run)
        print(f'🧹 prune：移除 {n} 条孤儿行')
    stats = upsert(db, rows, source, file_name, version, dry_run)
    db.close()
    print(f'✅ 完成：新增 {stats["insert"]} / 更新 {stats["update"]} / 未变 {stats["unchanged"]}')


if __name__ == '__main__':
    main()
