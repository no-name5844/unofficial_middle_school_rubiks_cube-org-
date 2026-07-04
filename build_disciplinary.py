#!/usr/bin/env python3
"""违规处罚细则管理工具：建表、增/改、删、查。

用法：
  python3 build_disciplinary.py              # 同步全部初始规则（首次建表 + upsert）
  python3 build_disciplinary.py --list       # 列出全部规则
  python3 build_disciplinary.py --delete 3   # 删除 id=3 的规则
  python3 build_disciplinary.py --add '{"category":"...","behavior":"...",...}'
  python3 build_disciplinary.py --update 5 '{"severity":"重度",...}'
"""

import sqlite3, json, sys

DB_PATH = 'charter.db'

# ═══════════════════════════════════════════════
#  建表（仅首次执行，不丢数据）
# ═══════════════════════════════════════════════

def ensure_table(db):
    db.execute('''
    CREATE TABLE IF NOT EXISTS disciplinary_rules (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        category        TEXT    NOT NULL,
        behavior        TEXT    NOT NULL UNIQUE,   -- 以行为描述作为自然唯一键
        severity        TEXT    NOT NULL,
        penalty_type    TEXT    NOT NULL,
        penalty_detail  TEXT,
        penalty_duration TEXT,
        deciding_body   TEXT    NOT NULL,
        procedure       TEXT,
        appeal_body     TEXT,
        appeal_deadline TEXT,
        charter_basis   TEXT,
        notes           TEXT
    )
    ''')

# ═══════════════════════════════════════════════
#  CRUD
# ═══════════════════════════════════════════════

COLUMNS = [
    'category', 'behavior', 'severity', 'penalty_type', 'penalty_detail',
    'penalty_duration', 'deciding_body', 'procedure', 'appeal_body',
    'appeal_deadline', 'charter_basis', 'notes'
]

def upsert_rule(db, rule: dict):
    """按 behavior 去重：存在则更新，不存在则插入"""
    cols = [c for c in COLUMNS if c in rule]
    placeholders = ', '.join('?' for _ in cols)
    set_clause = ', '.join(f'{c}=excluded.{c}' for c in cols if c != 'behavior')
    sql = f'''
        INSERT INTO disciplinary_rules ({', '.join(cols)})
        VALUES ({placeholders})
        ON CONFLICT(behavior) DO UPDATE SET {set_clause}
    '''
    db.execute(sql, [rule[c] for c in cols])

def delete_rule(db, rule_id: int):
    db.execute('DELETE FROM disciplinary_rules WHERE id=?', (rule_id,))
    return db.total_changes

def list_rules(db):
    rows = db.execute('''
        SELECT id, category, behavior, severity, penalty_type, penalty_duration
        FROM disciplinary_rules ORDER BY category, severity DESC, id
    ''').fetchall()
    return rows

def show_rule(db, rule_id: int):
    return db.execute('SELECT * FROM disciplinary_rules WHERE id=?', (rule_id,)).fetchone()

# ═══════════════════════════════════════════════
#  初始数据集
# ═══════════════════════════════════════════════

INITIAL_RULES = [
    # ── 滥用组织名义 ──
    dict(category='滥用组织名义',
         behavior='未经授权以本组织名义对外联络、发表言论或做出承诺',
         severity='中度', penalty_type='限制权利',
         penalty_detail='暂停投票权与选举权', penalty_duration='一学期',
         deciding_body='常任委员会',
         procedure='收到举报或自行发现→3日内初步核实→通知当事人→5日内听取申辩→常任委员会表决（过半数）',
         appeal_body='监察委员会', appeal_deadline='收到处分决定后7日内',
         charter_basis='第十六条第四项、第八十九条',
         notes='造成外部不良影响的，可加重至更长限制期限；屡教不改的可处除名'),

    dict(category='滥用组织名义',
         behavior='利用组织名义从事违法违规活动',
         severity='重度', penalty_type='除名',
         penalty_detail='立即除名，内部编号注销', penalty_duration='永久',
         deciding_body='常任委员会',
         procedure='收到举报→立即启动调查→3日内形成调查报告→常任委员会表决（三分之二以上）',
         appeal_body='全体成员会议', appeal_deadline='收到处分决定后14日内',
         charter_basis='第十六条第四项、第三条',
         notes='涉嫌违法的，同时向学校或公安机关报告'),

    dict(category='滥用组织名义',
         behavior='非官方群以本组织名义对外联络',
         severity='中度', penalty_type='警告',
         penalty_detail='书面警告，要求立即停止并消除影响', penalty_duration='—',
         deciding_body='常任委员会',
         procedure='发现后口头警告→24小时内未纠正→正式书面警告→常任委员会表决确认',
         appeal_body='监察委员会', appeal_deadline='收到处分决定后7日内',
         charter_basis='第八十八条',
         notes='反复违规可升级为限制权利'),

    # ── 泄露成员隐私 ──
    dict(category='泄露成员隐私',
         behavior='泄露其他成员的隐私信息（真实姓名、联系方式、照片等）',
         severity='中度', penalty_type='限制权利',
         penalty_detail='暂停投票权、选举权与被选举权', penalty_duration='一学期',
         deciding_body='常任委员会',
         procedure='收到举报→3日内核实→通知当事人→5日内听取申辩→常任委员会表决（过半数）',
         appeal_body='监察委员会', appeal_deadline='收到处分决定后7日内',
         charter_basis='第十六条第六项',
         notes='造成严重后果的可加重'),

    dict(category='泄露成员隐私',
         behavior='将线下活动中获知的成员真实身份信息记录到线上系统或档案中',
         severity='重度', penalty_type='限制权利',
         penalty_detail='暂停投票权、选举权与被选举权；拒不删除或后果严重的，可处除名',
         penalty_duration='至少一学期',
         deciding_body='常任委员会',
         procedure='发现后立即要求删除→5日内调查→常任委员会表决（三分之二以上）；除名须经全会表决',
         appeal_body='全体成员会议', appeal_deadline='收到处分决定后14日内',
         charter_basis='第九十二条、第十六条第六项',
         notes='这是章程级红线；拒不纠正的可升级至除名'),

    dict(category='泄露成员隐私',
         behavior='泄露代号与真实姓名的对应关系档案',
         severity='重度', penalty_type='除名',
         penalty_detail='立即除名', penalty_duration='永久',
         deciding_body='常任委员会',
         procedure='发现后立即调查→常任委员会紧急会议表决（三分之二以上）',
         appeal_body='全体成员会议', appeal_deadline='收到处分决定后14日内',
         charter_basis='第八十三条第三项',
         notes='该对应关系为本组织最高机密'),

    # ── 妨碍组织运作 ──
    dict(category='妨碍组织运作',
         behavior='无正当理由拒绝配合组织的正当调查',
         severity='轻度', penalty_type='警告',
         penalty_detail='口头或书面警告', penalty_duration='—',
         deciding_body='常任委员会',
         procedure='调查机构报告→常任委员会核实→通知当事人→申辩→表决',
         appeal_body='常任委员会', appeal_deadline='收到处分决定后7日内',
         charter_basis='第十六条第五项',
         notes='反复拒绝可升级'),

    dict(category='妨碍组织运作',
         behavior='恶意干扰全体成员会议或常任委员会会议的进行',
         severity='中度', penalty_type='限制权利',
         penalty_detail='暂停当次会议表决权，情节严重者暂停一学期投票权',
         penalty_duration='当次会议至一学期',
         deciding_body='会议主持人当场裁量（事后经常任委员会确认）',
         procedure='主持人当场制止→记录在案→会后常任委员会确认→下达书面处分',
         appeal_body='监察委员会', appeal_deadline='收到处分决定后7日内',
         charter_basis='第十六条第二项',
         notes='具体标准由细则进一步明确'),

    dict(category='妨碍组织运作',
         behavior='退出组织时拒不完成必要的工作交接',
         severity='轻度', penalty_type='警告',
         penalty_detail='书面警告，档案中记录', penalty_duration='—',
         deciding_body='常任委员会',
         procedure='所属机构报告→常任委员会核实→通知→申辩→决定',
         appeal_body='监察委员会', appeal_deadline='收到处分决定后7日内',
         charter_basis='第十六条第七项',
         notes='导致组织损失的，可索赔（依第七十三条）'),

    # ── 破坏组织财物 ──
    dict(category='破坏组织财物',
         behavior='故意损坏或侵占组织的集体财物',
         severity='中度', penalty_type='限制权利',
         penalty_detail='暂停投票权与选举权，并照价赔偿',
         penalty_duration='一学期',
         deciding_body='常任委员会',
         procedure='经费管理委员会或相关机构报告→常任委员会调查→听取申辩→表决（过半数）',
         appeal_body='监察委员会', appeal_deadline='收到处分决定后7日内',
         charter_basis='第九条、第十六条第四项',
         notes='第九条：组织的一切集体部分归全体成员共同所有'),

    dict(category='破坏组织财物',
         behavior='私自挪用或侵占组织经费',
         severity='重度', penalty_type='限制权利',
         penalty_detail='暂停投票权、选举权与被选举权，追回款项；数额较大或拒不归还的，可处除名',
         penalty_duration='至少一学期',
         deciding_body='常任委员会',
         procedure='经费管理委员会发现→立即报告常任委员会→5日内调查→常任委员会表决（三分之二以上）；除名须经全会表决',
         appeal_body='全体成员会议', appeal_deadline='收到处分决定后14日内',
         charter_basis='第六十八条第一项、第八条',
         notes='第六十八条第一项：一切经费必须经由经费管理委员会'),

    # ── 权力滥用 ──
    dict(category='权力滥用',
         behavior='常任委员会委员利用职务便利谋取个人利益或不正当行使权力',
         severity='重度', penalty_type='限制权利',
         penalty_detail='暂停委员职务（限制其作为委员的一切权利行使）；情节严重者由全体成员会议依第四十二条罢免',
         penalty_duration='至当届任期结束',
         deciding_body='全体成员会议',
         procedure='监察委员会调查→形成报告→提交全体成员会议→表决（过半数暂停职务，三分之二以上罢免）',
         appeal_body='全体成员会议', appeal_deadline='收到处分决定后14日内',
         charter_basis='第四十一条、第四十二条',
         notes='第四十二条：任免权统一归属于全体成员会议'),

    dict(category='权力滥用',
         behavior='监察委员会委员滥用异议权频繁阻止日常决议，造成组织瘫痪',
         severity='重度', penalty_type='限制权利',
         penalty_detail='暂停委员职务（限制其作为委员的一切权利行使），由全会决定是否罢免',
         penalty_duration='至当届任期结束',
         deciding_body='全体成员会议',
         procedure='常任委员会报告→全会审议→表决（过半数暂停职务，三分之二以上罢免）',
         appeal_body='全体成员会议', appeal_deadline='收到处分决定后14日内',
         charter_basis='第五十九条',
         notes='第五十九条即为本条的上位依据'),

    dict(category='权力滥用',
         behavior='经费管理委员会委员侵占、挪用或隐瞒组织经费',
         severity='重度', penalty_type='除名',
         penalty_detail='立即除名，追回款项', penalty_duration='永久',
         deciding_body='全体成员会议',
         procedure='发现→监察委员会协同经费管理委员会调查→报告全会→表决（三分之二以上）',
         appeal_body='全体成员会议', appeal_deadline='收到处分决定后14日内',
         charter_basis='第六十七条、第六十八条',
         notes='经费管理人员负有最高诚信义务'),

    dict(category='权力滥用',
         behavior='组织代表滥用临时决策权，且监察委员会已认定其行使不合理',
         severity='重度', penalty_type='限制权利',
         penalty_detail='暂停代表职务（限制其作为代表的一切权利行使）；经全体成员会议表决可罢免',
         penalty_duration='至当届任期结束',
         deciding_body='全体成员会议',
         procedure='监察委员会认定不合理→提交全会→表决（过半数暂停职务，三分之二以上罢免）',
         appeal_body='全体成员会议', appeal_deadline='收到处分决定后14日内',
         charter_basis='第五十条、第五十二条',
         notes='第五十条：全会对临时决策拥有最终审议权'),

    # ── 破坏组织声誉 ──
    dict(category='破坏组织声誉',
         behavior='在公开场合发表严重损害本组织声誉的言论',
         severity='中度', penalty_type='限制权利',
         penalty_detail='暂停投票权与选举权', penalty_duration='一学期',
         deciding_body='常任委员会',
         procedure='收到举报→核实→通知当事人→5日内听取申辩→常任委员会表决（过半数）',
         appeal_body='监察委员会', appeal_deadline='收到处分决定后7日内',
         charter_basis='第十六条第二项',
         notes='正常批评与建议（第十三条第四项）不属于违规'),

    # ── 违反投票规则 ──
    dict(category='违反投票规则',
         behavior='伪造或操纵投票结果',
         severity='重度', penalty_type='限制权利',
         penalty_detail='暂停投票权、选举权与被选举权，相关投票结果作废；情节特别严重的可处除名',
         penalty_duration='至少一学期',
         deciding_body='监察委员会联合常任委员会',
         procedure='监察委员会发现异常→第五十五条第六项赋予撤销并重算权力→常任委员会对责任人处分',
         appeal_body='全体成员会议', appeal_deadline='收到处分决定后14日内',
         charter_basis='第五十五条第六项',
         notes='监察委员会可先撤销异常投票，再追责'),

    dict(category='违反投票规则',
         behavior='在需回避时未回避表决',
         severity='轻度', penalty_type='警告',
         penalty_detail='相关表决结果无效，书面警告', penalty_duration='—',
         deciding_body='监察委员会',
         procedure='发现→监察委员会认定违规→宣布表决无效→通知常任委员会记录',
         appeal_body='常任委员会', appeal_deadline='收到处分决定后7日内',
         charter_basis='第四十一条、第五十九条',
         notes='非恶意的可以免于处分'),

    # ── 违反保密义务 ──
    dict(category='违反保密义务',
         behavior='联络员泄露投票人的身份代号或其投票选择',
         severity='重度', penalty_type='限制权利',
         penalty_detail='撤销联络员身份；暂停投票权、选举权与被选举权',
         penalty_duration='至少一学期',
         deciding_body='常任委员会',
         procedure='收到举报→立即核实→撤销联络员身份→5日内调查→常任委员会表决（三分之二以上）',
         appeal_body='全体成员会议', appeal_deadline='收到处分决定后14日内',
         charter_basis='第七十一条',
         notes='第七十一条明确：联络员对投票人的身份代号承担保密义务'),

    # ── 兜底 ──
    dict(category='其他严重违规',
         behavior='其他虽未在细则中列明，但经常任委员会认定严重违反本章程的行为',
         severity='中度', penalty_type='限制权利',
         penalty_detail='根据行为性质和后果裁量', penalty_duration='不超过一学期',
         deciding_body='常任委员会',
         procedure='常任委员会以三分之二以上认定违规→听取申辩→表决处罚→报监察委员会合规审查',
         appeal_body='监察委员会', appeal_deadline='收到处分决定后7日内',
         charter_basis='第十八条',
         notes='兜底条款，不得滥用'),
]

# ═══════════════════════════════════════════════
#  入口
# ═══════════════════════════════════════════════

def print_summary(db):
    total = db.execute('SELECT COUNT(*) FROM disciplinary_rules').fetchone()[0]
    print(f'共 {total} 条规则\n')
    rows = list_rules(db)
    for r in rows:
        print(f'  [{r[0]:>2}] {r[1]}｜{r[4]}｜{r[3]}｜{r[5]}  — {r[2]}')

if __name__ == '__main__':
    db = sqlite3.connect(DB_PATH)
    ensure_table(db)

    if len(sys.argv) == 1:
        # 默认模式：同步全部初始规则
        for rule in INITIAL_RULES:
            upsert_rule(db, rule)
        db.commit()
        print('✅ 已同步初始规则')
        print_summary(db)

    elif sys.argv[1] == '--list':
        for r in list_rules(db):
            rid, cat, behavior, sev, ptype, pdur = r[0], r[1] or '', r[2] or '', r[3] or '', r[4] or '', r[5] or ''
            print(f'[{rid:>2}] {cat:<16} {ptype:<6} {sev:<4} {pdur:<14} — {behavior}')

    elif sys.argv[1] == '--delete' and len(sys.argv) >= 3:
        rid = int(sys.argv[2])
        n = delete_rule(db, rid)
        db.commit()
        print(f'{"✅ 已删除" if n else "❌ 未找到"} id={rid}')

    elif sys.argv[1] == '--add' and len(sys.argv) >= 3:
        rule = json.loads(sys.argv[2])
        upsert_rule(db, rule)
        db.commit()
        print(f'✅ 已添加/更新：{rule.get("behavior", "")}')

    elif sys.argv[1] == '--update' and len(sys.argv) >= 4:
        rid = int(sys.argv[2])
        patch = json.loads(sys.argv[3])
        set_clause = ', '.join(f'{k}=?' for k in patch)
        db.execute(f'UPDATE disciplinary_rules SET {set_clause} WHERE id=?',
                   list(patch.values()) + [rid])
        db.commit()
        print(f'✅ 已更新 id={rid}')

    elif sys.argv[1] == '--show' and len(sys.argv) >= 3:
        r = show_rule(db, int(sys.argv[2]))
        if r:
            for i, col in enumerate(['id'] + COLUMNS):
                print(f'  {col}: {r[i]}')
        else:
            print(f'❌ 未找到')

    else:
        print(__doc__)

    db.close()
