from typing import List, Optional

from api.cluster_runner import ClusterRunner


class RunService:
    def __init__(self, cluster_runner: ClusterRunner):
        self._cluster_runner = cluster_runner

    def trigger(self, sites: Optional[List[str]], search_term: Optional[str]) -> str:
        return self._cluster_runner.trigger(sites=sites, search_term=search_term)
