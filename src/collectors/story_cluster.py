"""Story clustering — group related articles together.

Algorithm: entity-based greedy clustering.
Articles sharing 2+ vendor tags within the same ISO week are merged into one cluster.
"""
import json
from collections import defaultdict
from datetime import datetime
from typing import Optional


def _parse_tags(tags_json: Optional[str]) -> set[str]:
    if not tags_json:
        return set()
    try:
        return set(json.loads(tags_json))
    except Exception:
        return set()


def _week_key(pub) -> str:
    if isinstance(pub, str):
        try:
            pub = datetime.fromisoformat(pub.replace("Z", "+00:00"))
        except Exception:
            pub = datetime.now()
    elif pub is None:
        pub = datetime.now()
    iso = pub.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def assign_clusters(articles: list[dict]) -> list[dict]:
    """Assign cluster_id and cluster_size to a list of article dicts.

    Each dict must have: id, vendor_tags (JSON str or list), published_at.
    Returns a new list (original dicts not mutated) with cluster_id and cluster_size set.
    Raises ValueError if articles is empty.
    """
    if not articles:
        raise ValueError("assign_clusters requires a non-empty article list")

    result = [dict(a) for a in articles]
    cid_counter = [1]

    # Group indices by ISO week
    by_week: dict[str, list[int]] = defaultdict(list)
    for i, art in enumerate(result):
        art["cluster_id"] = None
        art["cluster_size"] = 1
        by_week[_week_key(art.get("published_at"))].append(i)

    for indices in by_week.values():
        for i in indices:
            if result[i]["cluster_id"] is not None:
                continue

            tags_i = _parse_tags(
                result[i].get("vendor_tags")
                if isinstance(result[i].get("vendor_tags"), str)
                else json.dumps(result[i].get("vendor_tags") or [])
            )
            cid = cid_counter[0]
            cid_counter[0] += 1
            result[i]["cluster_id"] = cid
            members = [i]

            for j in indices:
                if i == j or result[j]["cluster_id"] is not None:
                    continue
                tags_j = _parse_tags(
                    result[j].get("vendor_tags")
                    if isinstance(result[j].get("vendor_tags"), str)
                    else json.dumps(result[j].get("vendor_tags") or [])
                )
                if len(tags_i & tags_j) >= 2:
                    result[j]["cluster_id"] = cid
                    members.append(j)

            for m in members:
                result[m]["cluster_size"] = len(members)

    # Assign any remaining singletons
    for art in result:
        if art["cluster_id"] is None:
            art["cluster_id"] = cid_counter[0]
            cid_counter[0] += 1

    return result
