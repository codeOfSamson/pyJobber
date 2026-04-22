import anthropic


def answer_screening_questions(questions: list[str], resume_text: str, api_key: str) -> list[str]:
    if not questions:
        return []
    client = anthropic.Anthropic(api_key=api_key)
    answers = []
    for question in questions:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": (
                    "You are filling out a job application screening question. "
                    "Answer concisely and professionally based on this resume:\n\n"
                    f"{resume_text}\n\n"
                    f"Question: {question}"
                ),
            }],
        )
        answers.append(response.content[0].text)
    return answers
