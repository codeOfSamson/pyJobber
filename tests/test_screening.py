from unittest.mock import MagicMock, patch


def _mock_client(answer_text: str):
    mock_content = MagicMock()
    mock_content.text = answer_text
    mock_response = MagicMock()
    mock_response.content = [mock_content]
    mock_instance = MagicMock()
    mock_instance.messages.create.return_value = mock_response
    return mock_instance


def test_returns_one_answer_per_question():
    with patch("anthropic.Anthropic") as MockClient:
        MockClient.return_value = _mock_client("I have 5 years of Python experience.")
        from ai.screening import answer_screening_questions
        answers = answer_screening_questions(
            ["How many years of Python?", "Available full-time?"],
            "Resume text here.",
            "sk-ant-test",
        )
    assert len(answers) == 2
    assert answers[0] == "I have 5 years of Python experience."
    assert answers[1] == "I have 5 years of Python experience."


def test_uses_haiku_model():
    with patch("anthropic.Anthropic") as MockClient:
        mock_instance = _mock_client("Yes.")
        MockClient.return_value = mock_instance
        from ai.screening import answer_screening_questions
        answer_screening_questions(["Question?"], "Resume.", "sk-ant-test")
        call_kwargs = mock_instance.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "claude-haiku-4-5-20251001"


def test_empty_questions_returns_empty_list():
    with patch("anthropic.Anthropic"):
        from ai.screening import answer_screening_questions
        result = answer_screening_questions([], "Resume text.", "sk-ant-test")
    assert result == []
