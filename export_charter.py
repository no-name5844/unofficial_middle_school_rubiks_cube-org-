#!/usr/bin/env python3
"""从数据库导出章程/细则为 Markdown"""
import sqlite3, sys

def export(source, outfile=None):
    db = sqlite3.connect('charter.db')
    chs = db.execute('SELECT DISTINCT chapter FROM articles WHERE source=? ORDER BY id', (source,)).fetchall()
    lines = [f'# {source}\n']
    for (ch,) in chs:
        arts = db.execute('SELECT article_cn, content FROM articles WHERE source=? AND chapter=? ORDER BY article_num', (source, ch)).fetchall()
        lines.append(f'\n## {ch}\n')
        for cn, txt in arts:
            lines.append(f'**{cn}** {txt}\n')
    db.close()
    result = ''.join(lines)
    if outfile:
        with open(outfile, 'w') as f: f.write(result)
    return result

if __name__ == '__main__':
    src = sys.argv[1] if len(sys.argv) > 1 else '章程'
    out = sys.argv[2] if len(sys.argv) > 2 else None
    export(src, out)
    print(f'✅ {src} exported' if out else export(src)[:200])
