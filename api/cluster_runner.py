import os
from typing import List, Optional

import boto3


class ClusterRunner:
    def __init__(
        self,
        cluster: str = "autojobber",
        task_definition: str = "autojobber",
        container_name: str = "autojobber",
        region: str = "us-east-1",
    ):
        self._cluster = cluster
        self._task_definition = task_definition
        self._container_name = container_name
        self._region = region

    def trigger(self, sites: Optional[List[str]] = None, search_term: Optional[str] = None) -> str:
        subnet_id = os.environ["SUBNET_ID"]
        sg_id = os.environ["ECS_SG_ID"]

        env_overrides = []
        if sites:
            env_overrides.append({"name": "SITES_OVERRIDE", "value": ",".join(sites)})
        if search_term:
            env_overrides.append({"name": "SEARCH_TERM_OVERRIDE", "value": search_term})

        kwargs = {
            "cluster": self._cluster,
            "taskDefinition": self._task_definition,
            "launchType": "FARGATE",
            "networkConfiguration": {
                "awsvpcConfiguration": {
                    "subnets": [subnet_id],
                    "securityGroups": [sg_id],
                    "assignPublicIp": "ENABLED",
                }
            },
        }
        if env_overrides:
            kwargs["overrides"] = {
                "containerOverrides": [{"name": self._container_name, "environment": env_overrides}]
            }

        client = boto3.client("ecs", region_name=self._region)
        response = client.run_task(**kwargs)
        return response["tasks"][0]["taskArn"]
