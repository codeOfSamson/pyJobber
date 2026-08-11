from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException

from api.cluster_runner import ClusterRunner
from api.dependencies import get_cluster_runner, get_current_user
from api.schemas.runs import RunRequest, RunResponse
from api.services.run_service import RunService

router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.post("", response_model=RunResponse)
def trigger_run(
    payload: RunRequest,
    cluster_runner: ClusterRunner = Depends(get_cluster_runner),
    user=Depends(get_current_user),
):
    service = RunService(cluster_runner)
    try:
        task_arn = service.trigger(sites=payload.sites, search_term=payload.search_term)
    except ClientError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return RunResponse(task_arn=task_arn)
