from research_agent.agent import Agent
from research_agent.models import ModelResponse, ToolCall
from research_agent.tools import ToolRegistry


class FakeResearchModel:
    def __init__(self):
        self.calls = 0
        self.seen_tools = []

    def generate(self, messages, tools, system_prompt):
        self.calls += 1
        self.seen_tools.append([tool["name"] for tool in tools])
        if self.calls == 1:
            return ModelResponse(
                output_text="searching",
                tool_calls=[ToolCall(id="search-1", name="search_web", arguments={"query": "Acme competitors", "max_results": 2})],
            )
        if self.calls == 2:
            return ModelResponse(
                output_text="reading",
                tool_calls=[ToolCall(id="fetch-1", name="fetch_webpage", arguments={"url": "https://example.com/acme"})],
            )
        return ModelResponse(
            output_text="# Research note\n\n## Company\nAcme\n\n## Findings\n- Acme is a design collaboration company.\n- Competitors include adjacent design and whiteboarding tools."
        )


def test_agent_can_complete_live_research_flow_with_search_and_fetch_tools(tmp_path):
    registry = ToolRegistry()
    registry.register(
        "search_web",
        lambda query, max_results=5: [
            {"title": "Acme Official Site", "url": "https://example.com/acme", "snippet": "Acme builds design tools."}
        ],
        description="Search the public web for relevant pages.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_results": {"type": "integer"},
            },
            "required": ["query"],
        },
    )
    registry.register(
        "fetch_webpage",
        lambda url: {
            "title": "Acme Overview",
            "url": url,
            "content": "Acme is a design collaboration company. It competes with tools for product design and whiteboarding.",
        },
        description="Fetch and extract readable webpage content.",
        input_schema={
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    )

    model = FakeResearchModel()
    agent = Agent(model=model, tool_registry=registry, skills_dir=tmp_path, compact_after_messages=10)

    result = agent.run("Research Acme competitors")

    assert "# Research note" in result
    assert model.calls == 3
    assert any(message.role == "tool" and "Acme Official Site" in message.content for message in agent.messages)
    assert any(message.role == "tool" and "design collaboration company" in message.content for message in agent.messages)
    assert "fetch_webpage" in model.seen_tools[0]


def test_agent_returns_tool_error_to_model_instead_of_crashing_on_live_tool_failure(tmp_path):
    class ErrorModel:
        def __init__(self):
            self.calls = 0

        def generate(self, messages, tools, system_prompt):
            self.calls += 1
            if self.calls == 1:
                return ModelResponse(
                    output_text="fetching",
                    tool_calls=[ToolCall(id="fetch-1", name="fetch_webpage", arguments={"url": "https://example.com/fail"})],
                )
            return ModelResponse(output_text="final answer after tool failure")

    registry = ToolRegistry()
    registry.register(
        "fetch_webpage",
        lambda url: (_ for _ in ()).throw(RuntimeError("network timeout")),
        description="Fetch and extract readable webpage content.",
        input_schema={
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    )
    agent = Agent(model=ErrorModel(), tool_registry=registry, skills_dir=tmp_path, compact_after_messages=10)

    result = agent.run("Research Acme competitors")

    assert result == "final answer after tool failure"
    assert any(message.role == "tool" and "Tool execution failed for fetch_webpage" in message.content for message in agent.messages)


def test_agent_emits_progress_messages_for_model_and_live_tools(tmp_path):
    class ProgressModel:
        def __init__(self):
            self.calls = 0

        def generate(self, messages, tools, system_prompt):
            self.calls += 1
            if self.calls == 1:
                return ModelResponse(
                    output_text="searching",
                    tool_calls=[ToolCall(id="search-1", name="search_web", arguments={"query": "Figma competitors", "max_results": 2})],
                )
            return ModelResponse(output_text="final answer")

    registry = ToolRegistry()
    registry.register(
        "search_web",
        lambda query, max_results=5: [{"title": "Result", "url": "https://example.com", "snippet": "Example"}],
        description="Search the public web for relevant pages.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_results": {"type": "integer"},
            },
            "required": ["query"],
        },
    )

    progress_messages = []
    agent = Agent(
        model=ProgressModel(),
        tool_registry=registry,
        skills_dir=tmp_path,
        compact_after_messages=10,
        progress_callback=progress_messages.append,
    )

    result = agent.run("Research Figma competitors")

    assert result == "final answer"
    assert progress_messages == [
        "Thinking…",
        "Searching the web for: Figma competitors",
        "Finished search_web.",
        "Thinking…",
    ]
