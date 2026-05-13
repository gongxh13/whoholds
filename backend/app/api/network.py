from __future__ import annotations

from fastapi import APIRouter

from app.db.connection import connect
from app.models import NetworkEdge, NetworkNode, NetworkResponse, NetworkStats
from app.services.heuristics import is_person_heuristic

router = APIRouter(tags=["network"])

NODE_CAP = 100  # design.md §三铁律: hard upper bound for graph rendering.


@router.get("/network", response_model=NetworkResponse)
def network(focus: str, hops: int = 1, min_pct: float = 0.0) -> NetworkResponse:
    seen_people: set[str] = set()
    seen_companies: set[str] = set()
    nodes: dict[str, NetworkNode] = {}
    edges: list[NetworkEdge] = []
    truncated = False

    def add_person(name: str, nature: str | None, hop: int) -> None:
        if name in seen_people:
            return
        seen_people.add(name)
        nodes[f"p:{name}"] = NetworkNode(
            id=f"p:{name}",
            label=name,
            kind="person" if is_person_heuristic(name, nature) else "inst",
            is_person=is_person_heuristic(name, nature),
            hop=hop,
        )

    def add_company(code: str, name: str, hop: int) -> None:
        if code in seen_companies:
            return
        seen_companies.add(code)
        nodes[f"c:{code}"] = NetworkNode(
            id=f"c:{code}", label=name, kind="company", hop=hop
        )

    add_person(focus, "个人", hop=0)

    try:
        with connect("holdings") as conn:
            focus_companies = conn.execute(
                "SELECT DISTINCT stock_code, stock_name FROM top10_holders WHERE holder_name = ?",
                (focus,),
            ).fetchall()
            for r in focus_companies:
                if len(nodes) >= NODE_CAP:
                    truncated = True
                    break
                add_company(r["stock_code"], r["stock_name"], hop=1)
                edges.append(
                    NetworkEdge(
                        source=f"p:{focus}",
                        target=f"c:{r['stock_code']}",
                        weight=2.0,
                        kind="focus",
                    )
                )
                peers = conn.execute(
                    """
                    SELECT t.holder_name, t.pct_total, fh.holder_nature
                    FROM top10_holders t
                    LEFT JOIN top10_free_holders fh
                           ON t.stock_code = fh.stock_code
                          AND t.report_date = fh.report_date
                          AND t.holder_name = fh.holder_name
                    WHERE t.stock_code = ? AND t.report_date = (
                        SELECT MAX(report_date) FROM top10_holders WHERE stock_code = ?
                    ) AND t.holder_name != ?
                    """,
                    (r["stock_code"], r["stock_code"], focus),
                ).fetchall()
                for h in peers:
                    if len(nodes) >= NODE_CAP:
                        truncated = True
                        break
                    if (h["pct_total"] or 0) < min_pct:
                        continue
                    add_person(h["holder_name"], h["holder_nature"], hop=1)
                    edges.append(
                        NetworkEdge(
                            source=f"p:{h['holder_name']}",
                            target=f"c:{r['stock_code']}",
                            weight=float(h["pct_total"] or 0),
                            kind="holding",
                        )
                    )

            if hops >= 2 and not truncated:
                extras = [k.removeprefix("p:") for k in nodes if k.startswith("p:") and k != f"p:{focus}"]
                for p in extras[:20]:
                    if len(nodes) >= NODE_CAP:
                        truncated = True
                        break
                    extra_companies = conn.execute(
                        """
                        SELECT DISTINCT stock_code, stock_name FROM top10_holders
                        WHERE holder_name = ? AND stock_code NOT IN (
                            SELECT DISTINCT stock_code FROM top10_holders WHERE holder_name = ?
                        )
                        """,
                        (p, focus),
                    ).fetchall()
                    for c in extra_companies:
                        if len(nodes) >= NODE_CAP:
                            truncated = True
                            break
                        add_company(c["stock_code"], c["stock_name"], hop=2)
                        edges.append(
                            NetworkEdge(
                                source=f"p:{p}",
                                target=f"c:{c['stock_code']}",
                                weight=0.5,
                                kind="indirect",
                            )
                        )
    except Exception:
        pass

    return NetworkResponse(
        focus=focus,
        nodes=list(nodes.values()),
        edges=edges,
        stats=NetworkStats(n_nodes=len(nodes), n_edges=len(edges), truncated=truncated),
    )
