from research_agent.llm import OpenAIChatModel
from research_agent.models import Message


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeHTTPClient:
    def __init__(self, payload):
        self.payload = payload
        self.requests = []

    def post(self, url, headers, json, timeout):
        self.requests.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return FakeResponse(self.payload)


def test_openai_chat_model_sends_system_messages_and_tools_and_parses_tool_calls():
    client = FakeHTTPClient(
        {
            "choices": [
                {
                    "message": {
                        "content": "I should search first.",
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "search_web",
                                    "arguments": '{"query": "Acme competitors"}',
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ]
        }
    )
    model = OpenAIChatModel(api_key="test-key", model="gpt-test", http_client=client)

    response = model.generate(
        messages=[Message(role="user", content="Research Acme")],
        tools=[{"name": "search_web", "description": "Search the web", "input_schema": {"type": "object"}}],
        system_prompt="You are a research agent.",
    )

    assert response.output_text == "I should search first."
    assert response.stop_reason == "tool_use"
    assert response.tool_calls[0].id == "call_1"
    assert response.tool_calls[0].name == "search_web"
    assert response.tool_calls[0].arguments == {"query": "Acme competitors"}
    assert client.requests[0]["url"].endswith("/chat/completions")
    assert client.requests[0]["json"]["messages"][0] == {"role": "system", "content": "You are a research agent."}
    assert client.requests[0]["json"]["tools"][0]["function"]["name"] == "search_web"
