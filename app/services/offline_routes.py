"""基于稀疏本地路线图的离线路线计算。"""

import heapq

from app.repositories.offline import OfflineRepository
from app.schemas.offline import OfflineRouteEdge, OfflineRoutePath


class OfflineRouteService:
    """在离线路线图上用 Dijkstra 求最短时间路径。"""

    def __init__(self, repository: OfflineRepository) -> None:
        self._graph: dict[str, list[OfflineRouteEdge]] = {}
        for edge in repository.list_route_edges():
            self._graph.setdefault(edge.origin_poi_id, []).append(edge)
            if edge.is_bidirectional:
                self._graph.setdefault(edge.destination_poi_id, []).append(self._reverse_edge(edge))

    def find_route(
        self,
        origin_poi_id: str,
        destination_poi_id: str,
    ) -> OfflineRoutePath | None:
        """返回最短时间路线；同一端点、未知或不可达端点返回 None。"""
        if origin_poi_id == destination_poi_id:
            return None
        if origin_poi_id not in self._graph:
            return None

        best: dict[str, tuple[int, int]] = {origin_poi_id: (0, 0)}
        previous: dict[str, tuple[str, OfflineRouteEdge]] = {}
        queue: list[tuple[int, int, str]] = [(0, 0, origin_poi_id)]

        while queue:
            duration_minutes, distance_meters, poi_id = heapq.heappop(queue)
            if poi_id == destination_poi_id:
                break
            if (duration_minutes, distance_meters) != best[poi_id]:
                continue
            for edge in self._graph.get(poi_id, ()):
                next_poi_id = edge.destination_poi_id
                candidate = (
                    duration_minutes + edge.duration_minutes,
                    distance_meters + edge.distance_meters,
                )
                if next_poi_id not in best or candidate < best[next_poi_id]:
                    best[next_poi_id] = candidate
                    previous[next_poi_id] = (poi_id, edge)
                    heapq.heappush(queue, (*candidate, next_poi_id))

        if destination_poi_id not in previous:
            return None

        edges: list[OfflineRouteEdge] = []
        poi_id = destination_poi_id
        while poi_id != origin_poi_id:
            previous_poi_id, edge = previous[poi_id]
            edges.append(edge)
            poi_id = previous_poi_id
        edges.reverse()

        return OfflineRoutePath(
            origin_poi_id=origin_poi_id,
            destination_poi_id=destination_poi_id,
            edges=edges,
            duration_minutes=sum(edge.duration_minutes for edge in edges),
            distance_meters=sum(edge.distance_meters for edge in edges),
            cost_cents=sum(edge.cost_cents for edge in edges),
            instructions=[edge.summary for edge in edges],
            source_ids=list(dict.fromkeys(edge.source_id for edge in edges)),
        )

    @staticmethod
    def _reverse_edge(edge: OfflineRouteEdge) -> OfflineRouteEdge:
        return edge.model_copy(
            update={
                "origin_poi_id": edge.destination_poi_id,
                "destination_poi_id": edge.origin_poi_id,
            }
        )
