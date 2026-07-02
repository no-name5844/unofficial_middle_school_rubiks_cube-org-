#!/usr/bin/env python3
"""重建 charter.db 从所有 MD 文件，捕获完整多行条款内容"""
import sqlite3, re

db = sqlite3.connect('charter.db')
db.execute('DROP TABLE IF EXISTS articles')
db.execute('''CREATE TABLE articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT, chapter TEXT, article_num INTEGER, article_cn TEXT, content TEXT
)''')

cn_map = {'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10,'百':100,'零':0}
def cn2n(s):
    n=cur=0
    for c in s:
        if c in cn_map:
            v=cn_map[c]
            if v>=10:
                if cur==0:cur=1
                n+=cur*v;cur=0
            else:cur=v
    return n+cur

files = [
    ('xssz魔方非官方组织临时章程.md', '章程'),
    ('全体成员会议工作临时细则.md', '细则'),
    ('特殊身份临时细则.md', '细则'),
    ('监察委员会调查程序临时细则.md', '细则'),
    ('常任委员会运作临时细则.md', '细则'),
    ('历史管理委员会临时细则.md', '细则'),
    ('经费管理委员会临时细则.md', '细则'),
]

ARTICLE_RE = re.compile(r'\*\*第([一二三四五六七八九十百零]+)条\*\*\s*(.*)')

for fname, src in files:
    with open(fname, 'r', encoding='utf-8') as f:
        text = f.read()

    ch = "前言"
    # Split by article headers to capture multi-line content
    parts = re.split(r'(\*\*第[一二三四五六七八九十百零]+条\*\*)', text)

    current_cn = None
    i = 0
    while i < len(parts):
        part = parts[i]
        m = re.match(r'\*\*第([一二三四五六七八九十百零]+)条\*\*', part)
        if m:
            current_cn = m.group(1)
            # The next part is the content
            if i + 1 < len(parts):
                content = parts[i + 1]
                # Stop at the next '## ' or '---' or next article
                content = re.split(r'\n(?=## |---|\*\*第)', content)[0].strip()
                db.execute('INSERT INTO articles VALUES (NULL,?,?,?,?,?)',
                          (src, ch, cn2n(current_cn), f'第{current_cn}条', content))
            i += 2
        else:
            # Check for chapter header
            for line in part.split('\n'):
                if line.startswith('## '):
                    ch = line.strip()[3:]
            i += 1

db.commit()
for src in ['章程','细则']:
    n = db.execute('SELECT COUNT(*) FROM articles WHERE source=?',(src,)).fetchone()[0]
    print(f'{src}: {n}条')
db.close()
print('✅ charter.db rebuilt')
