"""同名股东消歧 - 实验。

对给定姓名 N，拿到他出现的所有 (公司, 期) appearances，
通过"两家公司共享几个其他个人股东"作为边权，
对公司做连通分量 / 社区发现，每个社区 = 一个候选"实体"。

这是 Layer 2 的核心算法（强联结规则）。验证它在 吕强、张秀、王传福
这样不同重名严重程度的案例上表现如何。
"""
import os
import sqlite3
import collections

DB = os.path.join(os.path.dirname(__file__), 'timeline.db')

# 平凡协同股东：所有人都会跟它们 co-occur，忽略
TRIVIAL_NAMES_KEYWORDS = ['公司', '集团', '银行', '基金', '委员会', '中心',
                          '合伙', '有限', '股份', '控股', '投资', '资本', '资管',
                          '管理', '信托', '保险', '证券', '财险', '财产', '人寿',
                          '财务', 'LIMITED', 'NOMINEES', '工会', '协会', 'HKSCC']

def is_individual(name: str) -> bool:
    up = name.upper()
    return not any(k in name or k in up for k in TRIVIAL_NAMES_KEYWORDS)


def get_individual_coholders_per_company(conn, name: str):
    """返回 dict: company_code -> set(其他个人股东姓名)"""
    # 拿 name 出现的所有公司
    companies = [r[0] for r in conn.execute(
        "SELECT DISTINCT stock_code FROM holder_companies WHERE holder_name = ?", (name,)
    )]
    by_company = {c: set() for c in companies}

    # 对 name 的每个协同伙伴 X，查 X 在哪些公司也出现
    for r in conn.execute("""
        SELECT holder_b, holder_b_type, company_list FROM coholder_pairs
         WHERE holder_a = ? AND holder_b_type = '个人' AND holder_b != ?
    """, (name, name)):
        peer = r[0]
        if not is_individual(peer):
            continue
        # company_list 是逗号分隔的 code|name|date，表示 name 和 peer 在哪几家公司同时出现
        for seg in (r[2] or '').split(','):
            parts = seg.split('|')
            if len(parts) >= 1:
                # 加市场前缀
                code = parts[0].strip()
                if code.startswith('6') or code.startswith('9'): full = f'sh{code}'
                elif code.startswith('4') or code.startswith('8') or code.startswith('92'): full = f'bj{code}'
                else: full = f'sz{code}'
                if full in by_company:
                    by_company[full].add(peer)
    return by_company


def union_find_components(companies, edges):
    """简单并查集找连通分量"""
    parent = {c: c for c in companies}
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb: parent[ra] = rb
    for a, b, _ in edges:
        union(a, b)
    groups = collections.defaultdict(set)
    for c in companies:
        groups[find(c)].add(c)
    return list(groups.values())


def disambiguate(conn, name: str, min_shared_peers: int = 1, verbose: bool = True):
    """对一个名字尝试消歧"""
    by_company = get_individual_coholders_per_company(conn, name)
    companies = list(by_company.keys())
    if verbose:
        print(f"\n{'='*70}")
        print(f"消歧: {name}  ({len(companies)} 家公司)")
        print('='*70)

    # 构图：边权 = 共同的"其他个人股东"个数
    edges = []
    for i, a in enumerate(companies):
        for b in companies[i+1:]:
            shared = by_company[a] & by_company[b]
            if len(shared) >= min_shared_peers:
                edges.append((a, b, shared))

    if verbose:
        print(f"边数（共享 ≥ {min_shared_peers} 个个人协同股东）: {len(edges)}")

    components = union_find_components(companies, edges)
    components.sort(key=lambda s: -len(s))

    if verbose:
        print(f"连通分量数: {len(components)}")
        # 取公司名做展示
        code_to_name = dict(conn.execute(
            f"SELECT stock_code, stock_name FROM holder_companies WHERE stock_code IN ({','.join('?'*len(companies))})",
            companies
        ).fetchall())
        print()
        for i, comp in enumerate(components, 1):
            if len(comp) >= 2 or len(components) <= 8:
                print(f"  桶 {i}: {len(comp)} 家")
                # 展示前 8 家
                comp_list = sorted(comp)
                for c in comp_list[:8]:
                    # 展示这家公司里的其他个人协同股东
                    peers = sorted(by_company[c])[:5]
                    print(f"    - {code_to_name.get(c, c):12s} 协同人: {' / '.join(peers) if peers else '无'}")
                if len(comp_list) > 8:
                    print(f"    ... +{len(comp_list)-8} 家")
        if sum(1 for c in components if len(c) == 1) > 5:
            singletons = [c for c in components if len(c) == 1]
            print(f"  其他 {len(singletons)} 个孤立桶（这些公司里 {name} 没和其他个人股东协同 → 大概率不同人 或 单飞）")
    return components, by_company


if __name__ == '__main__':
    conn = sqlite3.connect(DB)

    # 重名严重的几位
    for name in ['吕强', '张秀', '陈峰', '李欣', '徐国新']:
        disambiguate(conn, name)

    # 已知应该是同一人的（对照组）
    for name in ['王传福', '夏佐全', '方洪波']:
        disambiguate(conn, name)
