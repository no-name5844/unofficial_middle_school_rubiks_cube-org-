#!/usr/bin/env python3
"""将 Markdown 中「**第X条**」条文标题（及正文内的「第X条」引用）按文档顺序重排为连续编号 1..N。

用途：
  - 修正章节内编号各自从「一」重头数导致的撞号
  - 填补缺失编号（如缺第一百条）
  - 同步修正正文内对同一编号的引用，保持交叉引用不断链

特点：
  - 仅按「出现顺序」分配新号，保证连续、唯一、无缺号
  - 不改动章节标题（如「第七章 组织代表」）
  - 非破坏式：只改写编号，条文内容原样保留

用法：
  python3 renumber_articles.py 文档/规范性文件/xssz魔方非官方组织临时章程.md
  python3 renumber_articles.py 某细则.md --dry-run
"""

import re
import sys
import os

_CN = {'零': 0, '一': 1, '二': 2, '两': 2, '三': 3, '四': 4, '五': 5,
       '六': 6, '七': 7, '八': 8, '九': 9}


def cn_to_int(s: str) -> int:
    if s.isdigit():
        return int(s)
    total = 0
    sec = 0
    for ch in s:
        if ch == '百':
            sec = (sec or 1) * 100
            total += sec
            sec = 0
        elif ch == '十':
            sec = (sec or 1) * 10
            total += sec
            sec = 0
        elif ch == '零':
            pass
        elif ch in _CN:
            sec = _CN[ch]
        else:
            raise ValueError(f'无法解析的数字：{ch}（来自 {s}）')
    return total + sec


def int_to_cn(n: int) -> str:
    if n == 0:
        return '零'
    d = '零一二三四五六七八九'
    units = ['', '十', '百', '千']
    s = ''
    strn = str(n)
    for i, ch in enumerate(strn):
        digit = int(ch)
        unit = units[len(strn) - 1 - i]
        if digit == 0:
            if s and s[-1] != '零':
                s += '零'
        else:
            s += d[digit] + unit
    s = s.rstrip('零')
    if s.startswith('一十'):  # 十、十一… 而非 一十、一十一
        s = s[1:]
    return s


HEADER_RE = re.compile(r'\*\*第(.+?)条\*\*')
# 同时匹配标题内的「第X条」与正文引用「第X条」
ANY_RE = re.compile(r'第([零一二三四五六七八九十百千]+)条')


def renumber(text: str):
    """返回 (新文本, 变更映射 old_int->new_int)。"""
    headers = HEADER_RE.findall(text)
    old_nums = [cn_to_int(s) for s in headers]
    new_nums = list(range(1, len(old_nums) + 1))
    mapping = {o: n for o, n in zip(old_nums, new_nums) if o != n}

    def repl(m):
        cn = m.group(1)
        try:
            old = cn_to_int(cn)
        except ValueError:
            return m.group(0)
        if old in mapping:
            return '第' + int_to_cn(mapping[old]) + '条'
        return m.group(0)

    new_text = ANY_RE.sub(repl, text)
    return new_text, mapping


def main():
    if len(sys.argv) < 2:
        print('用法: python3 renumber_articles.py <markdown> [--dry-run]')
        sys.exit(1)
    path = sys.argv[1]
    dry = '--dry-run' in sys.argv[1:]
    if not os.path.exists(path):
        print(f'❌ 文件不存在：{path}')
        sys.exit(1)

    text = open(path, encoding='utf-8').read()
    new_text, mapping = renumber(text)

    if not mapping:
        print(f'✅ {path} 编号已连续，无需重排。')
        return

    if dry:
        print(f'📋 {path} 拟变更 {len(mapping)} 处编号：')
        for o, n in sorted(mapping.items()):
            print(f'   {int_to_cn(o)}条({o}) -> {int_to_cn(n)}条({n})')
        return

    with open(path, 'w', encoding='utf-8') as f:
        f.write(new_text)
    print(f'✅ 已重排 {path}：{len(mapping)} 处编号更新为连续 1..{len(HEADER_RE.findall(text))}。')


if __name__ == '__main__':
    main()
