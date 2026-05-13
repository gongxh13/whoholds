"""v2 原型：四视图 + 搜索 + URL 路由。
python 06-app-v2.py → http://127.0.0.1:8766/
"""
import os
import sqlite3
import json
import time
import collections
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
import uvicorn
import requests

DB = os.path.join(os.path.dirname(__file__), 'timeline.db')
WD_CACHE_DB = os.path.join(os.path.dirname(__file__), 'wikidata_cache.db')

# --- Wikidata 缓存 ---
def _ensure_wd_cache():
    conn = sqlite3.connect(WD_CACHE_DB)
    conn.execute('''CREATE TABLE IF NOT EXISTS wd_cache (
        name TEXT PRIMARY KEY,
        qid TEXT, label TEXT, description TEXT,
        birth TEXT, occupations TEXT, employer TEXT, zh_wiki TEXT,
        fetched_at INTEGER
    )''')
    conn.commit()
    conn.close()


def wikidata_lookup(name: str):
    _ensure_wd_cache()
    conn = sqlite3.connect(WD_CACHE_DB)
    row = conn.execute('SELECT * FROM wd_cache WHERE name = ?', (name,)).fetchone()
    if row:
        cols = [d[0] for d in conn.execute('SELECT * FROM wd_cache WHERE 0').description]
        conn.close()
        return dict(zip(cols, row))
    # 实时查询
    try:
        r = requests.get(
            'https://www.wikidata.org/w/api.php',
            params={'action': 'wbsearchentities', 'search': name,
                    'language': 'zh', 'format': 'json', 'limit': 1},
            headers={'User-Agent': 'whoholds-spike/0.1'},
            timeout=8,
        )
        results = r.json().get('search', [])
        if not results:
            conn.execute('INSERT INTO wd_cache(name, fetched_at) VALUES (?, ?)',
                         (name, int(time.time())))
            conn.commit()
            conn.close()
            return {'name': name, 'qid': None}
        first = results[0]
        qid = first['id']
        label = first.get('label')
        desc = first.get('description', '')
        # SPARQL 拉详情
        query = f'''
        SELECT ?occLabel ?bd ?empLabel ?wiki WHERE {{
          OPTIONAL {{ wd:{qid} wdt:P106 ?occ. }}
          OPTIONAL {{ wd:{qid} wdt:P569 ?bd. }}
          OPTIONAL {{ wd:{qid} wdt:P108 ?emp. }}
          OPTIONAL {{ ?wiki schema:about wd:{qid}; schema:isPartOf <https://zh.wikipedia.org/>. }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "zh,en". }}
        }} LIMIT 20
        '''
        s = requests.get('https://query.wikidata.org/sparql',
                         params={'query': query, 'format': 'json'},
                         headers={'User-Agent': 'whoholds-spike/0.1'},
                         timeout=12)
        binds = s.json().get('results', {}).get('bindings', [])
        occupations = sorted({b['occLabel']['value'] for b in binds if 'occLabel' in b})
        births = sorted({b['bd']['value'][:10] for b in binds if 'bd' in b})
        employers = sorted({b['empLabel']['value'] for b in binds if 'empLabel' in b})
        wikis = sorted({b['wiki']['value'] for b in binds if 'wiki' in b})
        data = {
            'name': name, 'qid': qid, 'label': label, 'description': desc,
            'birth': births[0] if births else '',
            'occupations': '/'.join(occupations),
            'employer': '/'.join(employers),
            'zh_wiki': wikis[0] if wikis else '',
            'fetched_at': int(time.time()),
        }
        conn.execute('''INSERT INTO wd_cache(name, qid, label, description, birth,
                        occupations, employer, zh_wiki, fetched_at)
                        VALUES (?,?,?,?,?,?,?,?,?)''',
                     (data['name'], data['qid'], data['label'], data['description'],
                      data['birth'], data['occupations'], data['employer'],
                      data['zh_wiki'], data['fetched_at']))
        conn.commit()
        conn.close()
        return data
    except Exception as e:
        conn.close()
        return {'name': name, 'qid': None, 'error': str(e)}


# --- 数据库 ---
def query(sql, params=()):
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- 个人股东启发式（流通表 nature 为准，否则用关键词判定）---
INST_KEYWORDS = [
    '公司', '集团', '银行', '基金', '委员会', '中心', '合伙', '有限', '股份',
    '控股', '投资', '资本', '资管', '管理', '信托', '保险', '证券', '财险',
    '财产', '人寿', '财务', 'LIMITED', 'NOMINEES', '工会', '协会', 'HKSCC'
]

def is_person_heuristic(name: str, nature: str | None) -> bool:
    if nature == '个人':
        return True
    if nature and nature != '个人':
        return False
    up = name.upper()
    if any(k in name or k in up for k in INST_KEYWORDS):
        return False
    return True


# --- FastAPI ---
app = FastAPI()


@app.get('/api/search')
def search(q: str):
    """搜索人名 + 公司名。优先匹配 holder_companies（全市场覆盖），
    回退到 top10_holders（只有详细持仓的 2 家公司里也能搜）"""
    q = q.strip()
    if not q:
        return {'people': [], 'companies': []}
    # 公司：合并两个源
    companies = query("""
        SELECT stock_code, stock_name FROM (
            SELECT DISTINCT stock_code, stock_name FROM top10_holders
             WHERE stock_name LIKE ? OR stock_code LIKE ?
            UNION
            SELECT DISTINCT stock_code, stock_name FROM holder_companies
             WHERE stock_name LIKE ? OR stock_code LIKE ?
        ) LIMIT 10
    """, (f'%{q}%', f'%{q}%', f'%{q}%', f'%{q}%'))
    # 人物：优先 holder_companies（已知是个人）
    rows = query("""
        SELECT holder_name, COUNT(DISTINCT stock_code) AS n
        FROM holder_companies WHERE holder_type='个人' AND holder_name LIKE ?
        GROUP BY holder_name
        ORDER BY n DESC LIMIT 15
    """, (f'%{q}%',))
    people = [{'name': r['holder_name'], 'n_companies': r['n']} for r in rows]
    return {'people': people, 'companies': companies}


@app.get('/api/person/{name}')
def person_detail(name: str, bucket: int | None = None):
    # 如果给了 bucket，先算消歧并取该桶的公司集合
    bucket_codes = None
    bucket_meta = None
    if bucket is not None:
        buckets, _, _ = _compute_buckets(name)
        if buckets is None:
            raise HTTPException(404, 'name not found')
        target = next((b for b in buckets if b['bucket_idx'] == bucket), None)
        if target is None:
            raise HTTPException(404, f'bucket {bucket} not found for {name}')
        bucket_codes = {c['code'] for c in target['companies']}
        bucket_meta = {
            'bucket_idx': bucket, 'size': target['size'],
            'level': target['level'], 'label': target['label'],
            'evidence': target['evidence'],
        }
    # 持仓 + 当期股价（不复权，反映"当时市值"）
    rows = query("""
        SELECT t.report_date, t.stock_code, t.stock_name,
               t.holdings, t.pct_total, t.rank, fh.holder_nature,
               (SELECT p.close FROM stock_daily_price p
                 WHERE p.stock_code = t.stock_code AND p.adjust = ''
                   AND p.date <= t.report_date
                 ORDER BY p.date DESC LIMIT 1) AS close_unadj
        FROM top10_holders t
        LEFT JOIN top10_free_holders fh ON t.stock_code = fh.stock_code
            AND t.report_date = fh.report_date AND t.holder_name = fh.holder_name
        WHERE t.holder_name = ?
        ORDER BY t.report_date, t.stock_code
    """, (name,))
    if bucket_codes is not None:
        rows = [r for r in rows if r['stock_code'] in bucket_codes]
    # 如果 top10_holders 没数据，回退到 holder_companies（只有快照、没时间线/市值）
    if not rows:
        snap = query("""
            SELECT stock_code, stock_name, report_date
            FROM holder_companies WHERE holder_name = ?
        """, (name,))
        if not snap:
            raise HTTPException(404, 'person not found')
        if bucket_codes is not None:
            snap = [s for s in snap if s['stock_code'] in bucket_codes]
        wd = wikidata_lookup(name)
        # 协同股东：bucket 选中时用桶内特征 peers，否则全局 top
        if bucket is not None:
            buckets, _, _ = _compute_buckets(name)
            target = next((b for b in buckets if b['bucket_idx'] == bucket), None)
            peers = [{'name': p['name'], 'co_count': p['freq']} for p in (target['top_peers'] if target else [])]
        else:
            coholders = query("""
                SELECT holder_a, holder_a_type, holder_b, holder_b_type, co_count
                FROM coholder_pairs
                WHERE (holder_a = ? OR holder_b = ?) AND co_count >= 2
                  AND holder_a_type = '个人' AND holder_b_type = '个人'
                ORDER BY co_count DESC LIMIT 30
            """, (name, name))
            seen = set()
            peers = []
            for r in coholders:
                peer = r['holder_b'] if r['holder_a'] == name else r['holder_a']
                if peer in seen: continue
                seen.add(peer)
                peers.append({'name': peer, 'co_count': r['co_count']})
        return {
            'name': name,
            'wikidata': wd,
            'companies': [{
                'stock_code': s['stock_code'], 'stock_name': s['stock_name'],
                'series': [{'date': s['report_date'], 'pct': None,
                            'holdings': None, 'rank': None,
                            'close': None, 'market_value': None}],
                'latest_pct': None, 'latest_holdings': None, 'latest_rank': None,
                'latest_mv': None,
                'first_quarter': s['report_date'], 'last_quarter': s['report_date'],
            } for s in snap],
            'total_value_series': [],
            'coholders': peers,
            'data_source': 'teamwork',
            'bucket_meta': bucket_meta,
        }
    by_company = {}
    for r in rows:
        mv = r['holdings'] * r['close_unadj'] if r['close_unadj'] else None
        by_company.setdefault(r['stock_code'], {
            'stock_code': r['stock_code'],
            'stock_name': r['stock_name'],
            'series': [],
            'latest_pct': None, 'latest_holdings': None, 'latest_rank': None,
            'latest_mv': None,
            'first_quarter': None, 'last_quarter': None,
        })
        c = by_company[r['stock_code']]
        c['series'].append({
            'date': r['report_date'],
            'pct': r['pct_total'],
            'holdings': r['holdings'],
            'rank': r['rank'],
            'close': r['close_unadj'],
            'market_value': mv,
        })
        c['latest_pct'] = r['pct_total']
        c['latest_holdings'] = r['holdings']
        c['latest_rank'] = r['rank']
        c['latest_mv'] = mv
        c['last_quarter'] = r['report_date']
        if c['first_quarter'] is None:
            c['first_quarter'] = r['report_date']
    wd = wikidata_lookup(name)
    # 总市值时间线（按报告期加总）
    total_by_date = {}
    for c in by_company.values():
        for s in c['series']:
            if s['market_value'] is not None:
                total_by_date.setdefault(s['date'], 0)
                total_by_date[s['date']] += s['market_value']
    total_series = [{'date': d, 'market_value': v} for d, v in sorted(total_by_date.items())]
    # 协同股东（如果数据库里有 coholder_pairs）
    try:
        coholder_rows = query("""
            SELECT holder_a, holder_b, co_count FROM coholder_pairs
            WHERE (holder_a = ? OR holder_b = ?) AND co_count >= 2
            ORDER BY co_count DESC LIMIT 30
        """, (name, name))
        peers = [{'name': r['holder_b'] if r['holder_a']==name else r['holder_a'],
                  'co_count': r['co_count']} for r in coholder_rows]
    except Exception:
        peers = []
    return {
        'name': name,
        'wikidata': wd,
        'companies': list(by_company.values()),
        'total_value_series': total_series,
        'coholders': peers,
        'data_source': 'timeline',
        'bucket_meta': bucket_meta,
    }


@app.get('/api/company/{code}')
def company_detail(code: str, date: str | None = None):
    rows = query("""
        SELECT DISTINCT stock_code, stock_name FROM top10_holders WHERE stock_code = ?
    """, (code,))
    if not rows:
        raise HTTPException(404, 'company not found')
    base = rows[0]
    dates = [r['report_date'] for r in query(
        "SELECT DISTINCT report_date FROM top10_holders WHERE stock_code = ? ORDER BY report_date",
        (code,)
    )]
    date = date or dates[-1]
    top10 = query("""
        SELECT t.rank, t.holder_name, t.share_type, t.holdings, t.pct_total,
               t.change_value, t.change_pct, fh.holder_nature,
               (SELECT p.close FROM stock_daily_price p
                 WHERE p.stock_code = t.stock_code AND p.adjust = ''
                   AND p.date <= t.report_date
                 ORDER BY p.date DESC LIMIT 1) AS close_unadj
        FROM top10_holders t
        LEFT JOIN top10_free_holders fh ON t.stock_code = fh.stock_code
            AND t.report_date = fh.report_date AND t.holder_name = fh.holder_name
        WHERE t.stock_code = ? AND t.report_date = ?
        ORDER BY t.rank
    """, (code, date))
    for r in top10:
        r['is_person'] = is_person_heuristic(r['holder_name'], r.get('holder_nature'))
        r['market_value'] = (r['holdings'] * r['close_unadj']) if r.get('close_unadj') else None
    # 时间线全量（按 holder × date 计算堆叠区面图所需 pct）
    series = query("""
        SELECT report_date, holder_name, pct_total
        FROM top10_holders WHERE stock_code = ? ORDER BY report_date, rank
    """, (code,))
    return {
        'stock_code': code,
        'stock_name': base['stock_name'],
        'available_dates': dates,
        'current_date': date,
        'top10': top10,
        'stack_series': series,
    }


@app.get('/api/network')
def network(focus: str, hops: int = 1, min_pct: float = 0.0):
    """Ego-network: 从一个人名出发，1 跳=他持仓的所有公司 + 这些公司其他股东；
    2 跳=进一步扩展那些其他股东的其他公司"""
    seen_people = set()
    seen_companies = set()
    edges = []
    nodes = {}

    def add_company(code, name):
        if code in seen_companies:
            return
        seen_companies.add(code)
        nodes[f'c:{code}'] = {
            'id': f'c:{code}', 'name': name, 'kind': 'company',
            'symbol': 'rect', 'symbolSize': 45,
            'itemStyle': {'color': '#f0883e'},
        }

    def add_person(name, nature):
        if name in seen_people:
            return
        seen_people.add(name)
        is_p = is_person_heuristic(name, nature)
        nodes[f'p:{name}'] = {
            'id': f'p:{name}', 'name': name,
            'kind': 'person' if is_p else 'inst',
            'symbol': 'circle', 'symbolSize': 22 if name == focus else 16,
            'itemStyle': {'color': '#4493f8' if is_p else '#6e7681'},
        }

    add_person(focus, '个人')
    nodes[f'p:{focus}']['itemStyle']['color'] = '#f78166'  # 焦点高亮

    # 1 跳：focus 持仓的公司，以及公司里的其他股东
    rows = query("""
        SELECT DISTINCT t.stock_code, t.stock_name
        FROM top10_holders t WHERE t.holder_name = ?
    """, (focus,))
    for r in rows:
        add_company(r['stock_code'], r['stock_name'])
        # focus → company 边
        edges.append({'source': f'p:{focus}', 'target': f"c:{r['stock_code']}", 'lineStyle': {'width': 2, 'color': '#f78166'}})
        # 找该公司最近一期的其他股东
        latest = query("""
            SELECT t.holder_name, t.pct_total, fh.holder_nature
            FROM top10_holders t
            LEFT JOIN top10_free_holders fh ON t.stock_code = fh.stock_code
                AND t.report_date = fh.report_date AND t.holder_name = fh.holder_name
            WHERE t.stock_code = ? AND t.report_date = (
                SELECT MAX(report_date) FROM top10_holders WHERE stock_code = ?
            ) AND t.holder_name != ?
        """, (r['stock_code'], r['stock_code'], focus))
        for h in latest:
            if (h['pct_total'] or 0) < min_pct:
                continue
            add_person(h['holder_name'], h.get('holder_nature'))
            edges.append({'source': f"p:{h['holder_name']}", 'target': f"c:{r['stock_code']}"})

    if hops >= 2:
        # 2 跳：1 跳里新出现的"人"再往外扩
        extra_people = [n.replace('p:', '') for n in nodes if n.startswith('p:') and n.replace('p:', '') != focus]
        for p in extra_people[:20]:  # 防爆
            companies = query("""
                SELECT DISTINCT stock_code, stock_name FROM top10_holders
                WHERE holder_name = ? AND stock_code NOT IN (
                    SELECT DISTINCT stock_code FROM top10_holders WHERE holder_name = ?
                )
            """, (p, focus))
            for c in companies:
                add_company(c['stock_code'], c['stock_name'])
                edges.append({'source': f'p:{p}', 'target': f"c:{c['stock_code']}",
                              'lineStyle': {'width': 1, 'color': '#7d8590', 'type': 'dashed'}})

    return {
        'nodes': list(nodes.values()),
        'edges': edges,
        'focus': focus,
        'stats': {
            'people': sum(1 for n in nodes.values() if n['kind'] == 'person'),
            'institutions': sum(1 for n in nodes.values() if n['kind'] == 'inst'),
            'companies': len(seen_companies),
        }
    }


@app.get('/api/discover/top-cross-holders')
def top_cross_holders(limit: int = 20):
    """高频跨公司个人股东榜：从协同分析 holder_companies 拉，覆盖全市场。
    teamwork 数据没有持股/市值字段，但 timeline.db 里如果有该公司该股东的数据可以回填总身价。
    """
    rows = query("""
        SELECT hc.holder_name,
               COUNT(DISTINCT hc.stock_code) AS n_companies,
               GROUP_CONCAT(DISTINCT hc.stock_name) AS companies,
               (SELECT SUM(t.holdings * (
                   SELECT p.close FROM stock_daily_price p
                    WHERE p.stock_code = t.stock_code AND p.adjust = ''
                      AND p.date <= t.report_date
                    ORDER BY p.date DESC LIMIT 1
               ))
                FROM top10_holders t
                WHERE t.holder_name = hc.holder_name
                  AND t.report_date = (SELECT MAX(report_date) FROM top10_holders
                                       WHERE holder_name = hc.holder_name AND stock_code = t.stock_code)
               ) AS total_value
        FROM holder_companies hc
        WHERE hc.holder_type = '个人'
        GROUP BY hc.holder_name
        ORDER BY n_companies DESC
        LIMIT ?
    """, (limit,))
    return rows


def _compute_buckets(name: str):
    """同名消歧 Layer 2 核心算法。供 endpoint 和 person_detail 共用。
    返回 (sorted_buckets, code_to_bucket_idx, code_to_name)。
    bucket idx 从 1 开始（仅多公司桶按 size 编号，单飞桶 idx=None 不暴露给用户）。
    """
    companies = [r['stock_code'] for r in query(
        "SELECT DISTINCT stock_code FROM holder_companies WHERE holder_name = ?", (name,)
    )]
    if not companies:
        return None, None, None
    code_to_name = {r['stock_code']: r['stock_name'] for r in query(
        f"SELECT stock_code, stock_name FROM holder_companies WHERE stock_code IN ({','.join('?'*len(companies))})",
        companies
    )}
    by_co = {c: set() for c in companies}
    for r in query("""
        SELECT holder_b, holder_b_type, company_list FROM coholder_pairs
         WHERE holder_a = ? AND holder_b_type = '个人' AND holder_b != ?
    """, (name, name)):
        peer = r['holder_b']
        if not is_person_heuristic(peer, '个人'):
            continue
        for seg in (r['company_list'] or '').split(','):
            parts = seg.split('|')
            if not parts: continue
            code = parts[0].strip()
            if code.startswith('6') or code.startswith('9'): full = f'sh{code}'
            elif code.startswith('4') or code.startswith('8') or code.startswith('92'): full = f'bj{code}'
            else: full = f'sz{code}'
            if full in by_co:
                by_co[full].add(peer)
    parent = {c: c for c in companies}
    def find(x):
        while parent[x] != x: parent[x] = parent[parent[x]]; x = parent[x]
        return x
    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb: parent[ra] = rb
    for i, a in enumerate(companies):
        for b in companies[i+1:]:
            if by_co[a] & by_co[b]:
                union(a, b)
    groups = collections.defaultdict(list)
    for c in companies:
        groups[find(c)].append(c)
    raw = []
    for root, codes in groups.items():
        peers = collections.Counter()
        for c in codes:
            for p in by_co[c]:
                peers[p] += 1
        raw.append({
            'root': root,
            'size': len(codes),
            'codes': codes,
            'peers': peers,
        })
    raw.sort(key=lambda b: (-b['size'], -max(b['peers'].values()) if b['peers'] else 0))
    # 编号 + 证据 + 置信度标签
    code_to_bucket = {}
    buckets = []
    multi_idx = 0
    for b in raw:
        top_peer_freq = max(b['peers'].values()) if b['peers'] else 0
        is_multi = b['size'] >= 2
        if is_multi:
            multi_idx += 1
            idx = multi_idx
        else:
            idx = None
        # 证据 + 等级
        if b['size'] >= 5 and top_peer_freq >= 3:
            level = 'high'; label = '高置信'
        elif is_multi and top_peer_freq >= 2:
            level = 'mid'; label = '中置信'
        elif is_multi:
            level = 'low'; label = '低置信'
        else:
            level = 'single'; label = '单飞'
        top_peer = b['peers'].most_common(1)
        evidence = (f"与{top_peer[0][0]}同公司 {top_peer[0][1]} 次"
                    if top_peer else "无个人协同信号")
        bucket = {
            'bucket_idx': idx,
            'size': b['size'],
            'level': level,
            'label': label,
            'evidence': evidence,
            'top_peers': [{'name': p, 'freq': f} for p, f in b['peers'].most_common(5)],
            'companies': [{'code': c, 'name': code_to_name.get(c, c)} for c in sorted(b['codes'])],
        }
        buckets.append(bucket)
        for c in b['codes']:
            code_to_bucket[c] = idx  # 单飞 idx=None
    return buckets, code_to_bucket, code_to_name


@app.get('/api/person/{name}/disambiguate')
def disambiguate(name: str):
    """同名消歧端点：给前端 hub 页面用"""
    buckets, _, _ = _compute_buckets(name)
    if buckets is None:
        raise HTTPException(404, 'name not found')
    multi = [b for b in buckets if b['bucket_idx'] is not None]
    singles = [b for b in buckets if b['bucket_idx'] is None]
    return {
        'name': name,
        'total_companies': sum(b['size'] for b in buckets),
        'total_buckets': len(buckets),
        'multi_company_buckets': len(multi),
        'singletons': len(singles),
        'buckets': multi,  # 单飞合并展示在前端
        'singletons_preview': [b['companies'][0] for b in singles[:30]],
    }


@app.get('/api/discover/top-coholder-pairs')
def top_coholder_pairs(limit: int = 50, min_co: int = 3):
    """协同股东对榜：两个人在多家公司同时出现"""
    rows = query("""
        SELECT holder_a, holder_a_type, holder_b, holder_b_type,
               co_count, company_list
        FROM coholder_pairs
        WHERE holder_a_type = '个人' AND holder_b_type = '个人'
          AND holder_a < holder_b   -- 避免镜像重复
          AND co_count >= ?
        ORDER BY co_count DESC
        LIMIT ?
    """, (min_co, limit))
    return rows


HTML = r"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<title>WhoHolds v2 · A 股股东网络</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<style>
  /* === 主题色板：默认跟随系统，可被 [data-theme] 覆盖 === */
  :root {
    --bg: #f6f8fa;
    --bg-elevated: #ffffff;
    --bg-sunken: #eaeef2;
    --bg-hover: #eaeef2;
    --border: #d0d7de;
    --border-strong: #afb8c1;
    --text: #1f2328;
    --text-dim: #59636e;
    --text-faint: #818b98;
    --accent: #0969da;
    --accent-bg: #ddf4ff;
    --accent-orange: #bc4c00;
    --accent-orange-bg: #fff1e5;
    --pill-person-bg: #ddf4ff;
    --pill-person-fg: #0969da;
    --pill-inst-bg: #eaeef2;
    --pill-inst-fg: #59636e;
    --shadow: 0 1px 0 rgba(31,35,40,.04);
    --focus-grad: linear-gradient(90deg, rgba(188,76,0,.10), transparent);
    --chart-bg: transparent;
    --chart-grid: #d0d7de;
    --link: #0969da;
  }
  :root[data-theme="dark"], :root[data-theme="system"] {}
  @media (prefers-color-scheme: dark) {
    :root[data-theme="system"], :root:not([data-theme]) {
      --bg: #0d1117;
      --bg-elevated: #161b22;
      --bg-sunken: #010409;
      --bg-hover: #1c2128;
      --border: #30363d;
      --border-strong: #444c56;
      --text: #e6edf3;
      --text-dim: #9198a1;
      --text-faint: #6e7681;
      --accent: #4493f8;
      --accent-bg: #0c2d6b;
      --accent-orange: #f78166;
      --accent-orange-bg: rgba(247,129,102,.15);
      --pill-person-bg: #0c2d6b;
      --pill-person-fg: #4493f8;
      --pill-inst-bg: #21262d;
      --pill-inst-fg: #9198a1;
      --shadow: 0 1px 0 rgba(0,0,0,.3);
      --focus-grad: linear-gradient(90deg, rgba(247,129,102,.15), transparent);
      --chart-grid: #30363d;
      --link: #4493f8;
    }
  }
  :root[data-theme="dark"] {
    --bg: #0d1117;
    --bg-elevated: #161b22;
    --bg-sunken: #010409;
    --bg-hover: #1c2128;
    --border: #30363d;
    --border-strong: #444c56;
    --text: #e6edf3;
    --text-dim: #9198a1;
    --text-faint: #6e7681;
    --accent: #4493f8;
    --accent-bg: #0c2d6b;
    --accent-orange: #f78166;
    --accent-orange-bg: rgba(247,129,102,.15);
    --pill-person-bg: #0c2d6b;
    --pill-person-fg: #4493f8;
    --pill-inst-bg: #21262d;
    --pill-inst-fg: #9198a1;
    --shadow: 0 1px 0 rgba(0,0,0,.3);
    --focus-grad: linear-gradient(90deg, rgba(247,129,102,.15), transparent);
    --chart-grid: #30363d;
    --link: #4493f8;
  }

  *{box-sizing:border-box}
  html,body{margin:0}
  body{
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
    background:var(--bg);color:var(--text);font-size:14px;
    -webkit-font-smoothing:antialiased;
    transition:background .2s, color .2s;
  }
  header{
    background:var(--bg-elevated);border-bottom:1px solid var(--border);
    padding:10px 20px;display:flex;align-items:center;gap:14px;
    position:sticky;top:0;z-index:10;
    backdrop-filter:saturate(180%) blur(6px);
  }
  header h1{font-size:15px;margin:0;color:var(--text-dim);font-weight:500;letter-spacing:.3px}
  header h1 b{color:var(--text);font-weight:700}
  nav{display:flex;gap:2px}
  nav a{color:var(--text-dim);text-decoration:none;padding:6px 12px;border-radius:6px;font-size:13px;transition:all .15s}
  nav a:hover{background:var(--bg-hover);color:var(--text)}
  nav a.active{background:var(--accent-bg);color:var(--accent)}
  .icon-btn{
    background:transparent;border:1px solid var(--border);color:var(--text-dim);
    width:32px;height:32px;border-radius:6px;cursor:pointer;
    display:inline-flex;align-items:center;justify-content:center;
    font-size:15px;transition:all .15s;
  }
  .icon-btn:hover{background:var(--bg-hover);color:var(--text);border-color:var(--border-strong)}
  .search{position:relative;flex:1;max-width:480px}
  .search input{
    width:100%;background:var(--bg);border:1px solid var(--border);color:var(--text);
    padding:8px 12px 8px 32px;border-radius:8px;font-size:14px;
    transition:all .15s;
  }
  .search input:focus{outline:none;border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-bg)}
  .search::before{
    content:"";position:absolute;left:10px;top:50%;width:14px;height:14px;
    transform:translateY(-50%);
    background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16' fill='%239198a1'><path d='M11.5 7a4.5 4.5 0 1 1-9 0 4.5 4.5 0 0 1 9 0Zm-.82 4.74a6 6 0 1 1 1.06-1.06l2.79 2.79a.75.75 0 1 1-1.06 1.06l-2.79-2.79Z'/></svg>");
    background-size:contain;background-repeat:no-repeat;pointer-events:none;
  }
  .search-results{
    position:absolute;top:40px;left:0;right:0;
    background:var(--bg-elevated);border:1px solid var(--border);
    border-radius:8px;max-height:380px;overflow:auto;display:none;z-index:20;
    box-shadow:0 8px 24px rgba(0,0,0,.12);
  }
  .search-results.show{display:block}
  .sr-group{padding:8px 12px;color:var(--text-faint);font-size:11px;text-transform:uppercase;letter-spacing:.5px;border-top:1px solid var(--border)}
  .sr-group:first-child{border-top:none}
  .sr-item{padding:8px 14px;cursor:pointer}
  .sr-item:hover{background:var(--bg-hover)}
  .sr-item .tag{font-size:11px;color:var(--text-faint);margin-left:8px}

  main{padding:20px;max-width:1400px;margin:0 auto}
  .card{
    background:var(--bg-elevated);border:1px solid var(--border);
    border-radius:10px;padding:18px;margin-bottom:14px;box-shadow:var(--shadow);
  }
  .card h2{font-size:12px;color:var(--text-dim);margin:0 0 14px;text-transform:uppercase;letter-spacing:.6px;font-weight:600}
  .row{display:flex;gap:14px}
  .col{flex:1;min-width:0}
  @media(max-width:900px){.row{flex-direction:column}}

  table{width:100%;border-collapse:collapse;font-size:13px}
  thead th{
    text-align:left;color:var(--text-dim);font-weight:500;
    padding:9px 12px;border-bottom:1px solid var(--border);
    font-size:11px;text-transform:uppercase;letter-spacing:.5px;
    user-select:none;background:var(--bg-elevated);
    position:sticky;top:0;
  }
  th.sortable{cursor:pointer}
  th.sortable:hover{color:var(--text)}
  th .sort{display:inline-block;margin-left:4px;color:var(--text-faint);font-size:9px;opacity:.5}
  th.sort-asc .sort, th.sort-desc .sort{color:var(--accent);opacity:1}
  th.sort-asc .sort::before{content:"▲"}
  th.sort-desc .sort::before{content:"▼"}
  th.sortable:not(.sort-asc):not(.sort-desc) .sort::before{content:"⇅"}
  td{padding:10px 12px;border-bottom:1px solid var(--border)}
  tbody tr:last-child td{border-bottom:none}
  tbody tr:hover td{background:var(--bg-hover)}
  td a{color:var(--link);text-decoration:none;font-weight:500}
  td a:hover{text-decoration:underline}
  td.num{font-variant-numeric:tabular-nums;text-align:right}

  .pill{display:inline-block;padding:2px 9px;border-radius:12px;font-size:11px;color:var(--pill-inst-fg);background:var(--pill-inst-bg);font-weight:500}
  .pill.person{color:var(--pill-person-fg);background:var(--pill-person-bg)}
  .pill.inst{color:var(--pill-inst-fg);background:var(--pill-inst-bg)}

  .chart{height:260px}
  .empty{color:var(--text-faint);font-style:italic;padding:20px 0;text-align:center}
  .hint{color:var(--text-dim);font-size:13px;line-height:1.6}
  .badge{display:inline-block;background:var(--bg-hover);color:var(--text-dim);padding:2px 7px;border-radius:4px;font-size:11px;margin-left:8px;font-weight:500}
  select{background:var(--bg-elevated);color:var(--text);border:1px solid var(--border);padding:6px 28px 6px 10px;border-radius:6px;font-size:13px;cursor:pointer;appearance:none;
    background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16' fill='%239198a1'><path d='M4.427 9.427l3.396 3.396a.25.25 0 00.354 0l3.396-3.396A.25.25 0 0011.396 9H4.604a.25.25 0 00-.177.427z'/></svg>");
    background-position:right 8px center;background-repeat:no-repeat;background-size:14px;
  }
  select:focus{outline:none;border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-bg)}

  .focus-banner{
    padding:18px 20px;background:var(--focus-grad);
    border-left:3px solid var(--accent-orange);border-radius:8px;
    margin-bottom:14px;
  }
  .focus-banner h2{font-size:20px;margin:0 0 6px;color:var(--text);text-transform:none;letter-spacing:0;font-weight:700;display:flex;align-items:center;gap:10px}
  .stat-row{display:flex;flex-wrap:wrap;gap:20px;color:var(--text-dim);font-size:13px;margin-top:6px}
  .stat-row b{color:var(--text);font-weight:600}
  .stat-row a{color:var(--accent);text-decoration:none}
  .stat-row a:hover{text-decoration:underline}

  /* 分页 */
  .pager{display:flex;align-items:center;justify-content:space-between;margin-top:12px;color:var(--text-dim);font-size:12px}
  .pager-controls{display:flex;gap:4px;align-items:center}
  .pager-btn{
    background:var(--bg-elevated);border:1px solid var(--border);color:var(--text);
    padding:4px 10px;border-radius:6px;cursor:pointer;font-size:12px;min-width:30px;
  }
  .pager-btn:hover:not(:disabled){background:var(--bg-hover)}
  .pager-btn:disabled{opacity:.4;cursor:not-allowed}
  .pager-btn.active{background:var(--accent);color:#fff;border-color:var(--accent)}
</style></head>
<body>
<header>
  <h1>Who<b>Holds</b> <span class="badge">spike v2</span></h1>
  <nav>
    <a href="#/discover" data-route="discover">发现</a>
  </nav>
  <div class="search">
    <input id="q" placeholder="搜索人物 或 公司 (代码/名字)…" autocomplete="off">
    <div class="search-results" id="sr"></div>
  </div>
  <button id="themeBtn" class="icon-btn" title="主题：跟随系统 / 浅色 / 深色">🌗</button>
</header>
<main id="main"></main>

<script>
const $ = s => document.querySelector(s);
const $main = $('#main');
const $q = $('#q');
const $sr = $('#sr');

const fmt = {
  pct: v => v == null ? '—' : (+v).toFixed(2) + '%',
  num: v => v == null ? '—' : v.toLocaleString('zh-CN'),
  date: d => d ? `${d.slice(0,4)}-${d.slice(4,6)}-${d.slice(6,8)}` : '',
  money: v => {
    if(v == null) return '—';
    if(v >= 1e8) return (v/1e8).toFixed(1) + ' 亿';
    if(v >= 1e4) return (v/1e4).toFixed(1) + ' 万';
    return v.toFixed(0);
  }
};

// === 主题：system / light / dark 三档循环 ===
const THEMES = ['system', 'light', 'dark'];
const ICONS = {system:'🌗', light:'☀️', dark:'🌙'};
let theme = localStorage.getItem('theme') || 'system';
function applyTheme(){
  document.documentElement.setAttribute('data-theme', theme);
  $('#themeBtn').textContent = ICONS[theme];
  $('#themeBtn').title = `主题：${ {system:'跟随系统', light:'浅色', dark:'深色'}[theme] }（点击切换）`;
  // 通知所有 ECharts 重绘
  if(window._charts) window._charts.forEach(c => { try{ c.dispose(); }catch(e){} });
  window._charts = [];
  if(typeof route === 'function') route();
}
function cycleTheme(){ theme = THEMES[(THEMES.indexOf(theme)+1) % THEMES.length]; localStorage.setItem('theme', theme); applyTheme(); }
// 监听系统颜色变化（仅当 system 模式时）
if(window.matchMedia){
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => { if(theme==='system') applyTheme(); });
}

// 读 CSS 变量供 ECharts 用
function cssvar(name){ return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
function chartTheme(){
  return {
    bg: 'transparent',
    text: cssvar('--text'),
    textDim: cssvar('--text-dim'),
    grid: cssvar('--chart-grid'),
    accent: cssvar('--accent'),
    accentOrange: cssvar('--accent-orange'),
  };
}
function initChart(el){ const c = echarts.init(el); window._charts.push(c); return c; }

// === 排序：把一个表格变成可排序 ===
// columns: [{key, label, format, type, className, html}]
// type: 'string' | 'number' | 'date'  default 'string'
function renderSortable(rows, columns, initKey, initDir){
  let sortKey = initKey || null;
  let sortDir = initDir || 'desc';

  const tbl = document.createElement('table');
  const thead = document.createElement('thead');
  const trh = document.createElement('tr');
  columns.forEach(c => {
    const th = document.createElement('th');
    th.classList.add('sortable');
    th.dataset.key = c.key;
    th.innerHTML = `${c.label}<span class="sort"></span>`;
    if(c.className) th.classList.add(c.className);
    th.onclick = () => {
      if(sortKey === c.key) sortDir = (sortDir === 'asc' ? 'desc' : 'asc');
      else { sortKey = c.key; sortDir = (c.type === 'number' ? 'desc' : 'asc'); }
      render();
    };
    trh.appendChild(th);
  });
  thead.appendChild(trh);
  tbl.appendChild(thead);
  const tbody = document.createElement('tbody');
  tbl.appendChild(tbody);

  function render(){
    // 表头排序状态
    [...trh.children].forEach(th => {
      th.classList.remove('sort-asc','sort-desc');
      if(th.dataset.key === sortKey) th.classList.add(sortDir === 'asc' ? 'sort-asc' : 'sort-desc');
    });
    // 排序
    let sorted = rows.slice();
    if(sortKey){
      const col = columns.find(c => c.key === sortKey);
      const t = col?.type || 'string';
      const dir = sortDir === 'asc' ? 1 : -1;
      sorted.sort((a, b) => {
        let va = a[sortKey], vb = b[sortKey];
        if(va == null && vb == null) return 0;
        if(va == null) return 1;
        if(vb == null) return -1;
        if(t === 'number'){ return (va - vb) * dir; }
        return String(va).localeCompare(String(vb), 'zh') * dir;
      });
    }
    tbody.innerHTML = sorted.map(r => {
      return '<tr>' + columns.map(c => {
        let val = c.html ? c.html(r) : (c.format ? c.format(r[c.key], r) : (r[c.key] ?? '—'));
        return `<td${c.className ? ' class="'+c.className+'"' : ''}>${val}</td>`;
      }).join('') + '</tr>';
    }).join('');
  }
  render();
  return tbl;
}

// === 分页：用 renderSortable 包一层 ===
function renderPaged(rows, columns, opts){
  opts = opts || {};
  const pageSize = opts.pageSize || 20;
  const initSort = opts.initSort || {};

  const wrap = document.createElement('div');
  const tableWrap = document.createElement('div');
  wrap.appendChild(tableWrap);

  const pager = document.createElement('div');
  pager.className = 'pager';
  wrap.appendChild(pager);

  let page = 0;
  let sortKey = initSort.key || null;
  let sortDir = initSort.dir || 'desc';

  function sortedRows(){
    if(!sortKey) return rows.slice();
    const col = columns.find(c => c.key === sortKey);
    const t = col?.type || 'string';
    const dir = sortDir === 'asc' ? 1 : -1;
    return rows.slice().sort((a,b) => {
      let va = a[sortKey], vb = b[sortKey];
      if(va == null && vb == null) return 0;
      if(va == null) return 1;
      if(vb == null) return -1;
      if(t === 'number') return (va - vb) * dir;
      return String(va).localeCompare(String(vb), 'zh') * dir;
    });
  }

  function render(){
    const all = sortedRows();
    const totalPages = Math.max(1, Math.ceil(all.length / pageSize));
    if(page >= totalPages) page = totalPages - 1;
    if(page < 0) page = 0;
    const slice = all.slice(page * pageSize, (page + 1) * pageSize);

    // 表格
    const tbl = document.createElement('table');
    const thead = document.createElement('thead');
    const trh = document.createElement('tr');
    columns.forEach(c => {
      const th = document.createElement('th');
      th.classList.add('sortable');
      if(c.className) th.classList.add(c.className);
      th.dataset.key = c.key;
      th.innerHTML = `${c.label}<span class="sort"></span>`;
      if(c.key === sortKey) th.classList.add(sortDir === 'asc' ? 'sort-asc' : 'sort-desc');
      th.onclick = () => {
        if(sortKey === c.key) sortDir = (sortDir === 'asc' ? 'desc' : 'asc');
        else { sortKey = c.key; sortDir = (c.type === 'number' ? 'desc' : 'asc'); }
        page = 0;
        render();
      };
      trh.appendChild(th);
    });
    thead.appendChild(trh);
    tbl.appendChild(thead);
    const tbody = document.createElement('tbody');
    tbody.innerHTML = slice.map((r, i) => {
      return '<tr>' + columns.map(c => {
        let val;
        if(c.key === '__index') val = page * pageSize + i + 1;
        else if(c.html) val = c.html(r, page * pageSize + i);
        else if(c.format) val = c.format(r[c.key], r);
        else val = r[c.key] ?? '—';
        return `<td${c.className ? ' class="'+c.className+'"' : ''}>${val}</td>`;
      }).join('') + '</tr>';
    }).join('');
    tbl.appendChild(tbody);
    tableWrap.innerHTML = '';
    tableWrap.appendChild(tbl);

    // 分页器
    const pages = [];
    const win = 2;
    for(let i = 0; i < totalPages; i++){
      if(i === 0 || i === totalPages - 1 || (i >= page - win && i <= page + win)) pages.push(i);
      else if(pages[pages.length-1] !== '…') pages.push('…');
    }
    pager.innerHTML = `
      <span>共 <b>${all.length}</b> 条，第 ${page+1}/${totalPages} 页</span>
      <div class="pager-controls">
        <button class="pager-btn" data-act="prev" ${page===0?'disabled':''}>‹</button>
        ${pages.map(p => p === '…' ? '<span style="padding:0 4px">…</span>'
          : `<button class="pager-btn ${p===page?'active':''}" data-page="${p}">${p+1}</button>`).join('')}
        <button class="pager-btn" data-act="next" ${page===totalPages-1?'disabled':''}>›</button>
      </div>
    `;
    pager.querySelectorAll('.pager-btn').forEach(b => {
      b.onclick = () => {
        if(b.dataset.act === 'prev') page = Math.max(0, page - 1);
        else if(b.dataset.act === 'next') page = Math.min(totalPages - 1, page + 1);
        else page = +b.dataset.page;
        render();
      };
    });
  }
  render();
  return wrap;
}

async function api(url){ const r = await fetch(url); if(!r.ok) throw new Error(r.status); return r.json(); }

// --- 搜索 ---
let searchTimer;
$q.oninput = () => {
  clearTimeout(searchTimer);
  const v = $q.value.trim();
  if(!v){ $sr.classList.remove('show'); return; }
  searchTimer = setTimeout(async () => {
    const d = await api(`/api/search?q=${encodeURIComponent(v)}`);
    let html = '';
    if(d.people.length){
      html += '<div class="sr-group">个人股东</div>';
      d.people.forEach(p => {
        html += `<div class="sr-item" data-route="#/p/${encodeURIComponent(p.name)}">${p.name}<span class="tag">人物</span></div>`;
      });
    }
    if(d.companies.length){
      html += '<div class="sr-group">上市公司</div>';
      d.companies.forEach(c => {
        html += `<div class="sr-item" data-route="#/c/${c.stock_code}">${c.stock_name}<span class="tag">${c.stock_code}</span></div>`;
      });
    }
    if(!html) html = '<div class="empty">无匹配</div>';
    $sr.innerHTML = html;
    $sr.classList.add('show');
    $sr.querySelectorAll('.sr-item').forEach(el => el.onclick = () => {
      location.hash = el.dataset.route;
      $sr.classList.remove('show');
      $q.value = '';
    });
  }, 180);
};
document.addEventListener('click', e => { if(!e.target.closest('.search')) $sr.classList.remove('show'); });

// --- 路由 ---
window.addEventListener('hashchange', route);
window.addEventListener('load', () => {
  $('#themeBtn').onclick = cycleTheme;
  applyTheme(); // applyTheme 会触发 route()
});

async function route(){
  if(!window._charts) window._charts = [];
  const h = location.hash || '#/discover';
  const parts = h.replace(/^#\//, '').split('/');
  document.querySelectorAll('nav a').forEach(a => a.classList.toggle('active', a.dataset.route === parts[0]));
  $main.innerHTML = '<div class="hint">加载中…</div>';
  try{
    if(parts[0] === 'p'){
      const name = decodeURIComponent(parts[1] || '');
      const bucket = parts[2] ? +parts[2] : null;
      await renderPerson(name, bucket);
    }
    else if(parts[0] === 'c') await renderCompany(parts[1] || '');
    else if(parts[0] === 'n') await renderNetwork(decodeURIComponent(parts[1] || ''));
    else await renderDiscover();
  }catch(e){
    $main.innerHTML = `<div class="card">加载失败：${e.message}</div>`;
  }
}

// 桶等级 → 颜色 / 标签
const LEVEL = {
  high:   {color:'#3fb950', label:'🟢 高置信'},
  mid:    {color:'#d4a72c', label:'🟡 中置信'},
  low:    {color:'#db6d28', label:'🟠 低置信'},
  single: {color:'#a0a0a0', label:'⚪ 单飞'},
};

// --- 同名 hub 页（多桶时显示） ---
async function renderPersonHub(name, disamb){
  $main.innerHTML = `
    <div class="focus-banner" style="border-left-color:#d4a72c;background:linear-gradient(90deg, rgba(212,167,44,.12), transparent)">
      <h2>「${name}」<span class="pill" style="background:#fff8c5;color:#9a6700">⚠ 同名疑似多人</span></h2>
      <div class="stat-row">
        <span>名义合计 <b>${disamb.total_companies}</b> 家上市公司</span>
        <span>拆出 <b>${disamb.multi_company_buckets}</b> 个多公司实体 + <b>${disamb.singletons}</b> 个单飞</span>
      </div>
    </div>
    <div class="card hint" style="line-height:1.8">
      东方财富 API 把所有叫「${name}」的不同自然人合并成一条返回。用"两家公司是否共享非平凡个人协同股东"做拓扑分簇后，
      拆出多个候选真实实体。<b>选一个进去看具体的持仓 / 时间线 / 协同</b>：
    </div>
    <div class="card">
      <h2>候选实体（按规模降序）</h2>
      <div id="hubBuckets" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px"></div>
    </div>
    ${disamb.singletons ? `
    <div class="card">
      <h2>单飞实体 · ${disamb.singletons} 家</h2>
      <div class="hint" style="margin-bottom:10px">
        这些公司里「${name}」没和任何个人股东协同 — 拓扑信号无法把它们和其他实体桶关联起来。
        这 ${disamb.singletons} 家几乎可以肯定是 ${disamb.singletons} 个不同的真实「${name}」（或个别真同人但单飞）。
        点击公司直接看该公司的前十大股东列表。
      </div>
      <div style="display:flex;flex-wrap:wrap;gap:8px;max-height:200px;overflow:auto">
        ${disamb.singletons_preview.map(c => `<a href="#/c/${c.code}" class="badge" style="font-size:12px;padding:4px 10px">${c.name}</a>`).join('')}
        ${disamb.singletons > disamb.singletons_preview.length ? `<span class="hint" style="padding:4px 10px">…+${disamb.singletons - disamb.singletons_preview.length}</span>` : ''}
      </div>
    </div>
    ` : ''}
  `;
  $('#hubBuckets').innerHTML = disamb.buckets.map(b => {
    const L = LEVEL[b.level];
    return `
      <a href="#/p/${encodeURIComponent(name)}/${b.bucket_idx}" style="text-decoration:none;color:inherit">
        <div style="background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:14px;border-left:4px solid ${L.color};cursor:pointer;transition:transform .1s;height:100%">
          <div style="display:flex;align-items:baseline;justify-content:space-between;margin-bottom:6px">
            <b style="font-size:15px;color:var(--text)">「${name}」#${b.bucket_idx}</b>
            <span style="font-size:11px;color:${L.color};font-weight:600">${L.label}</span>
          </div>
          <div style="color:var(--text);font-size:13px;margin-bottom:8px"><b>${b.size}</b> 家公司</div>
          <div class="hint" style="font-size:12px;margin-bottom:8px">${b.evidence}</div>
          <div style="font-size:12px;line-height:1.7;color:var(--text-dim);max-height:60px;overflow:hidden">
            ${b.companies.slice(0, 6).map(c => c.name).join(' · ')}${b.companies.length > 6 ? ' …' : ''}
          </div>
        </div>
      </a>
    `;
  }).join('');
}

// --- 人物视角 ---
async function renderPerson(name, bucket){
  // 没指定 bucket 时，先看消歧情况决定走 hub 还是 entity
  if(bucket == null){
    let disamb = null;
    try { disamb = await api(`/api/person/${encodeURIComponent(name)}/disambiguate`); }
    catch(e){
      $main.innerHTML = `<div class="card">未找到「${name}」相关数据。</div>`; return;
    }
    // 多桶 → 显示 hub
    if(disamb.multi_company_buckets >= 2 || (disamb.multi_company_buckets >= 1 && disamb.singletons >= 5)){
      return renderPersonHub(name, disamb);
    }
    // 单桶 → 直接渲染 entity（不传 bucket，端点会返回全部 = 该桶 = 全名字数据）
  }
  // entity 页
  const url = bucket != null ? `/api/person/${encodeURIComponent(name)}?bucket=${bucket}` : `/api/person/${encodeURIComponent(name)}`;
  const d = await api(url);
  const wd = d.wikidata || {};
  const latestTotal = d.total_value_series.length ? d.total_value_series[d.total_value_series.length-1].market_value : null;
  const orange = 'var(--accent-orange)';
  const bm = d.bucket_meta;
  const L = bm ? LEVEL[bm.level] : null;

  $main.innerHTML = `
    ${bm ? `<div class="hint" style="margin-bottom:8px">
      <a href="#/p/${encodeURIComponent(d.name)}" style="color:var(--accent);text-decoration:none">← 返回同名 hub</a>
    </div>` : ''}
    <div class="focus-banner" ${bm ? `style="border-left-color:${L.color};background:linear-gradient(90deg, ${L.color}26, transparent)"` : ''}>
      <h2>${d.name}${bm ? ` #${bm.bucket_idx}` : ''} <span class="pill person">个人股东</span>${bm ? ` <span class="pill" style="background:${L.color}33;color:${L.color}">${L.label}</span>` : ''}</h2>
      <div class="stat-row">
        <span>${bm ? `本实体共 <b>${d.companies.length}</b> 家公司` : `出现在 <b>${d.companies.length}</b> 家上市公司`}</span>
        ${bm ? `<span class="hint">${bm.evidence}</span>` : ''}
        ${latestTotal ? `<span>当前总持仓市值 <b style="color:${orange}">${fmt.money(latestTotal)}</b></span>` : ''}
        ${wd.qid ? `<span>Wikidata <a href="https://www.wikidata.org/wiki/${wd.qid}" target="_blank"><b>${wd.qid}</b></a> <span class="hint">(可能对应该实体或别的同名实体)</span></span>` : '<span class="hint">Wikidata 无条目</span>'}
        ${wd.birth ? `<span>生于 <b>${wd.birth}</b></span>` : ''}
      </div>
    </div>
    <div class="row">
      <div class="col card">
        <h2>人物资料 ${wd.qid ? '· Wikidata' : ''}</h2>
        ${wd.qid ? `
          <div style="line-height:1.7">
            <div><b>${wd.label || name}</b> <span class="hint">${wd.description || ''}</span></div>
            ${wd.occupations ? `<div>职业：${wd.occupations}</div>` : ''}
            ${wd.employer ? `<div>雇主：${wd.employer}</div>` : ''}
            ${wd.zh_wiki ? `<div><a href="${wd.zh_wiki}" target="_blank">维基百科 ↗</a></div>` : ''}
          </div>
        ` : '<div class="empty">未找到匹配的 Wikidata 条目（可能是冷门人物或重名严重）</div>'}
      </div>
      <div class="col card">
        <h2>持仓公司</h2>
        <div id="pCompanies"></div>
      </div>
    </div>
    <div class="row">
      <div class="col card">
        <h2>持股比例时间线</h2>
        <div id="ptl" class="chart"></div>
      </div>
      <div class="col card">
        <h2>持仓市值时间线（按当时收盘价）</h2>
        <div id="pvtl" class="chart"></div>
      </div>
    </div>
    ${d.coholders && d.coholders.length ? `
    <div class="card">
      <h2>协同股东 · 在同公司出现过的其他个人</h2>
      <div class="hint" style="margin-bottom:8px">点击进入对方人物视角；协同次数高的几乎都是家族 / 一致行动人。</div>
      <div id="pCoholders"></div>
    </div>
    ` : ''}
    <div class="card">
      <a href="#/n/${encodeURIComponent(d.name)}">展开 Ego-Network →</a>
    </div>
  `;
  if(d.coholders && d.coholders.length){
    $('#pCoholders').appendChild(renderSortable(d.coholders, [
      {key:'name', label:'股东',
        html: r => `<a href="#/p/${encodeURIComponent(r.name)}">${r.name}</a>`},
      {key:'co_count', label:'同公司次数', type:'number', className:'num',
        html: r => `<b style="color:${orange}">${r.co_count}</b>`},
    ], 'co_count', 'desc'));
  }
  // 可排序表格
  $('#pCompanies').appendChild(renderSortable(d.companies, [
    {key:'stock_name', label:'公司', html: r => `<a href="#/c/${r.stock_code}">${r.stock_name}</a>`},
    {key:'latest_pct', label:'当前 %', type:'number', className:'num', format: v => fmt.pct(v)},
    {key:'latest_holdings', label:'持股数', type:'number', className:'num', format: v => fmt.num(v)},
    {key:'latest_mv', label:'当前市值', type:'number', className:'num',
      html: r => `<b style="color:${orange}">${fmt.money(r.latest_mv)}</b>`},
    {key:'latest_rank', label:'名次', type:'number', className:'num', format: v => '#' + v},
    {key:'first_quarter', label:'首/末报告期',
      html: r => `<span class="hint" style="font-size:11px">${fmt.date(r.first_quarter)} → ${fmt.date(r.last_quarter)}</span>`},
  ], 'latest_mv', 'desc'));

  // 图表（用 CSS 变量取色）
  const t = chartTheme();
  const dates = [...new Set(d.companies.flatMap(c => c.series.map(s => fmt.date(s.date))))].sort();

  const c1 = initChart(document.getElementById('ptl'));
  c1.setOption({
    backgroundColor: t.bg,
    legend: {data: d.companies.map(c => c.stock_name), textStyle:{color:t.text}, top:0},
    tooltip: {trigger:'axis'},
    xAxis: {type:'category', axisLabel:{color:t.textDim}, axisLine:{lineStyle:{color:t.grid}}, splitLine:{lineStyle:{color:t.grid}}, data: dates},
    yAxis: {type:'value', name:'持股 %', nameTextStyle:{color:t.textDim}, axisLabel:{color:t.textDim}, splitLine:{lineStyle:{color:t.grid}}},
    grid: {top:36, left:50, right:20, bottom:30},
    series: d.companies.map(c => ({
      name: c.stock_name, type:'line', smooth:true, symbol:'circle', symbolSize:6,
      data: c.series.map(s => [fmt.date(s.date), s.pct])
    }))
  });

  const c2 = initChart(document.getElementById('pvtl'));
  const perCo = d.companies.map(c => ({
    name: c.stock_name, type:'bar', stack:'mv', barMaxWidth:30,
    data: dates.map(dx => {
      const m = c.series.find(s => fmt.date(s.date) === dx);
      return m ? (m.market_value || 0) / 1e8 : 0;
    })
  }));
  c2.setOption({
    backgroundColor: t.bg,
    legend: {data: d.companies.map(c => c.stock_name), textStyle:{color:t.text}, top:0},
    tooltip: {trigger:'axis', valueFormatter: v => v.toFixed(0) + ' 亿'},
    xAxis: {type:'category', axisLabel:{color:t.textDim, fontSize:10}, axisLine:{lineStyle:{color:t.grid}}, data: dates},
    yAxis: {type:'value', name:'市值（亿元）', nameTextStyle:{color:t.textDim}, axisLabel:{color:t.textDim, formatter: v => v + ' 亿'}, splitLine:{lineStyle:{color:t.grid}}},
    grid: {top:36, left:60, right:20, bottom:30},
    series: perCo
  });
}

// --- 公司视角 ---
async function renderCompany(code, date){
  const url = date ? `/api/company/${code}?date=${date}` : `/api/company/${code}`;
  const d = await api(url);
  const orange = 'var(--accent-orange)';
  $main.innerHTML = `
    <div class="focus-banner">
      <h2>${d.stock_name} <span class="badge">${d.stock_code}</span></h2>
      <div class="stat-row">
        <span><b>${d.available_dates.length}</b> 个季报数据</span>
        <span>当前期: <b>${fmt.date(d.current_date)}</b></span>
      </div>
    </div>
    <div class="card">
      <h2>报告期</h2>
      <select id="dateSel">
        ${d.available_dates.map(x => `<option value="${x}" ${x===d.current_date?'selected':''}>${fmt.date(x)}</option>`).join('')}
      </select>
    </div>
    <div class="card">
      <h2>当期前十大股东</h2>
      <div id="cTop10"></div>
    </div>
    <div class="card">
      <h2>股权结构变迁（堆叠区面图）</h2>
      <div id="cstack" class="chart" style="height:340px"></div>
    </div>
  `;
  document.getElementById('dateSel').onchange = e => renderCompany(code, e.target.value);

  $('#cTop10').appendChild(renderSortable(d.top10, [
    {key:'rank', label:'#', type:'number', className:'num'},
    {key:'holder_name', label:'股东',
      html: r => r.is_person ? `<a href="#/p/${encodeURIComponent(r.holder_name)}">${r.holder_name}</a>` : r.holder_name},
    {key:'holder_nature', label:'性质',
      html: r => `<span class="pill ${r.is_person?'person':'inst'}">${r.holder_nature || (r.is_person?'个人(推断)':'机构(推断)')}</span>`},
    {key:'holdings', label:'持股', type:'number', className:'num', format: v => fmt.num(v)},
    {key:'pct_total', label:'占比', type:'number', className:'num', format: v => fmt.pct(v)},
    {key:'market_value', label:'市值', type:'number', className:'num',
      html: r => `<b style="color:${orange}">${fmt.money(r.market_value)}</b>`},
    {key:'change_pct', label:'变动', type:'number', className:'num',
      html: r => `${r.change_value || '—'}${r.change_pct ? ` (${(+r.change_pct).toFixed(1)}%)` : ''}`},
  ], 'rank', 'asc'));

  // 堆叠区面图
  const t = chartTheme();
  const chart = initChart(document.getElementById('cstack'));
  const dates = [...new Set(d.stack_series.map(r => r.report_date))].sort();
  const holders = [...new Set(d.stack_series.map(r => r.holder_name))];
  const counts = {};
  d.stack_series.forEach(r => counts[r.holder_name] = (counts[r.holder_name]||0)+1);
  const major = holders.filter(h => counts[h] >= 3);
  const map = {};
  d.stack_series.forEach(r => {
    map[r.report_date] = map[r.report_date] || {};
    const key = major.includes(r.holder_name) ? r.holder_name : '其他';
    map[r.report_date][key] = (map[r.report_date][key]||0) + r.pct_total;
  });
  const series = [...major, '其他'].map(h => ({
    name: h, type:'line', stack:'all', smooth:true, symbol:'none',
    areaStyle:{opacity:.7},
    data: dates.map(d => map[d]?.[h] || 0)
  }));
  chart.setOption({
    backgroundColor: t.bg,
    legend: {data:[...major, '其他'], textStyle:{color:t.text}, top:0, type:'scroll'},
    tooltip: {trigger:'axis'},
    xAxis: {type:'category', data: dates.map(fmt.date), axisLabel:{color:t.textDim, fontSize:10}, axisLine:{lineStyle:{color:t.grid}}},
    yAxis: {type:'value', name:'累计持股 %', nameTextStyle:{color:t.textDim}, axisLabel:{color:t.textDim}, splitLine:{lineStyle:{color:t.grid}}},
    grid: {top:40, left:50, right:20, bottom:30},
    series
  });
}

// --- 网络 ---
async function renderNetwork(focus){
  const html = `
    <div class="focus-banner">
      <h2>Ego-Network · 焦点: ${focus}</h2>
      <div class="stat-row hint" id="netStats">加载中…</div>
    </div>
    <div class="card">
      <span class="hint">跳数:</span>
      <select id="hops"><option value="1">1 跳</option><option value="2">2 跳</option></select>
      <span class="hint" style="margin-left:14px">持股阈值:</span>
      <select id="minpct"><option value="0">不限</option><option value="0.5">≥ 0.5%</option><option value="1">≥ 1%</option><option value="3">≥ 3%</option></select>
    </div>
    <div class="card">
      <div id="net" class="chart" style="height:560px"></div>
    </div>
    <div class="card hint">
      ⚠️ 当前 timeline.db 只有 美的 + 比亚迪 两家公司数据，跨公司关联接近无。等抓取更多公司或协同分析数据接入后，2 跳网络才会显出价值。
    </div>
  `;
  $main.innerHTML = html;
  const draw = async () => {
    const hops = +document.getElementById('hops').value;
    const min_pct = +document.getElementById('minpct').value;
    const d = await api(`/api/network?focus=${encodeURIComponent(focus)}&hops=${hops}&min_pct=${min_pct}`);
    document.getElementById('netStats').innerHTML =
      `<span><b>${d.stats.companies}</b> 公司</span><span><b>${d.stats.people}</b> 个人</span><span><b>${d.stats.institutions}</b> 机构</span><span><b>${d.edges.length}</b> 边</span>`;
    const t = chartTheme();
    const chart = initChart(document.getElementById('net'));
    chart.setOption({
      backgroundColor: t.bg,
      tooltip:{},
      series:[{
        type:'graph', layout:'force', roam:true, draggable:true,
        data: d.nodes, edges: d.edges,
        label:{show:true, position:'right', color:t.text, fontSize:11},
        lineStyle:{color:t.textDim, opacity:.45, width:1.2},
        force:{repulsion:240, edgeLength:[60,140], gravity:.1},
      }]
    }, true);
    chart.off('click');
    chart.on('click', p => {
      if(p.dataType !== 'node') return;
      if(p.data.id.startsWith('p:')) location.hash = '#/p/' + encodeURIComponent(p.data.name);
      else if(p.data.id.startsWith('c:')) location.hash = '#/c/' + p.data.id.slice(2);
    });
  };
  document.getElementById('hops').onchange = draw;
  document.getElementById('minpct').onchange = draw;
  draw();
}

// --- 发现 ---
async function renderDiscover(){
  const [top, pairs] = await Promise.all([
    api('/api/discover/top-cross-holders?limit=500'),
    api('/api/discover/top-coholder-pairs?limit=300&min_co=3'),
  ]);
  const orange = 'var(--accent-orange)';
  $main.innerHTML = `
    <div class="card">
      <h2>欢迎</h2>
      <div class="hint">来自东方财富"股东协同分析"的全市场快照（最新报告期）。搜索框可输入任意人名 / 公司。当前数据：<b>${top.length === 500 ? '500+' : top.length}</b> 个高频个人股东、<b>${pairs.length === 300 ? '300+' : pairs.length}</b> 组关联股东对。</div>
    </div>
    <div class="card">
      <h2>高频跨公司个人股东榜</h2>
      <div id="discTable"></div>
    </div>
    <div class="card">
      <h2>协同股东对榜 · 两人在 N 家公司同时出现</h2>
      <div class="hint" style="margin-bottom:10px">协同次数 ≥ 3 视为有意义。这种关系几乎都是 <b>家族 / 夫妻 / 一致行动人</b>。</div>
      <div id="pairTable"></div>
    </div>
    <div class="card hint">
      未来榜单：新进前十大、关联公司簇、本期异动榜 —— 需要 timeline 数据全市场化（在线增量抓取每只股票的季度数据）。
    </div>
  `;
  $('#discTable').appendChild(renderPaged(top, [
    {key:'__index', label:'#', className:'num'},
    {key:'holder_name', label:'姓名',
      html: r => `<a href="#/p/${encodeURIComponent(r.holder_name)}">${r.holder_name}</a>${r.n_companies >= 5 ? ' <span class="pill" style="background:#fff8c5;color:#9a6700;font-size:10px">⚠ 疑似同名多人</span>' : ''}`},
    {key:'n_companies', label:'名义公司数', type:'number', className:'num',
      html: r => `<b>${r.n_companies}</b>`},
    {key:'total_value', label:'已知持仓总市值', type:'number', className:'num',
      html: r => r.total_value ? `<b style="color:${orange}">${fmt.money(r.total_value)}</b>`
                              : `<span class="hint">—</span>`},
    {key:'companies', label:'持仓公司（仅前若干家）',
      html: r => `<span class="hint" style="font-size:12px">${r.companies}</span>`},
  ], {pageSize: 20, initSort: {key:'n_companies', dir:'desc'}}));

  $('#pairTable').appendChild(renderPaged(pairs, [
    {key:'__index', label:'#', className:'num'},
    {key:'holder_a', label:'股东 A',
      html: r => `<a href="#/p/${encodeURIComponent(r.holder_a)}">${r.holder_a}</a>`},
    {key:'holder_b', label:'股东 B',
      html: r => `<a href="#/p/${encodeURIComponent(r.holder_b)}">${r.holder_b}</a>`},
    {key:'co_count', label:'同公司次数', type:'number', className:'num',
      html: r => `<b style="color:${orange}">${r.co_count}</b>`},
  ], {pageSize: 20, initSort: {key:'co_count', dir:'desc'}}));
}
</script>
</body></html>
"""


@app.get('/', response_class=HTMLResponse)
def root():
    return HTML


if __name__ == '__main__':
    uvicorn.run(app, host='127.0.0.1', port=8766, log_level='warning')
