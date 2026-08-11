from api.cluster_runner import ClusterRunner


def test_trigger_calls_run_task_with_expected_params(mocker, monkeypatch):
    monkeypatch.setenv("SUBNET_ID", "subnet-123")
    monkeypatch.setenv("ECS_SG_ID", "sg-456")
    fake_client = mocker.Mock()
    fake_client.run_task.return_value = {"tasks": [{"taskArn": "arn:aws:ecs:fake"}]}
    mocker.patch("boto3.client", return_value=fake_client)

    runner = ClusterRunner()
    task_arn = runner.trigger()

    assert task_arn == "arn:aws:ecs:fake"
    kwargs = fake_client.run_task.call_args.kwargs
    assert kwargs["cluster"] == "autojobber"
    assert kwargs["taskDefinition"] == "autojobber"
    assert kwargs["networkConfiguration"]["awsvpcConfiguration"]["subnets"] == ["subnet-123"]
    assert "overrides" not in kwargs


def test_trigger_adds_container_overrides_for_sites_and_search_term(mocker, monkeypatch):
    monkeypatch.setenv("SUBNET_ID", "subnet-123")
    monkeypatch.setenv("ECS_SG_ID", "sg-456")
    fake_client = mocker.Mock()
    fake_client.run_task.return_value = {"tasks": [{"taskArn": "arn:aws:ecs:fake"}]}
    mocker.patch("boto3.client", return_value=fake_client)

    runner = ClusterRunner()
    runner.trigger(sites=["cakeresume", "linkedin"], search_term="rust developer")

    kwargs = fake_client.run_task.call_args.kwargs
    env = kwargs["overrides"]["containerOverrides"][0]["environment"]
    assert {"name": "SITES_OVERRIDE", "value": "cakeresume,linkedin"} in env
    assert {"name": "SEARCH_TERM_OVERRIDE", "value": "rust developer"} in env
