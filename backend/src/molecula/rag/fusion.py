from collections import defaultdict
from collections.abc import Iterable, Sequence

# The usual constant of reciprocal rank fusion (Cormack et al., 2009).
RRF_K = 60


def reciprocal_rank_fusion(rankings: Iterable[Sequence[str]]) -> dict[str, float]:
    """Each id's sum of 1 / (RRF_K + rank) over the rankings it is in, best first."""
    fused: dict[str, float] = defaultdict(float)
    for ranking in rankings:
        for rank, id_ in enumerate(ranking, start=1):
            fused[id_] += 1 / (RRF_K + rank)
    return dict(sorted(fused.items(), key=lambda item: item[1], reverse=True))
