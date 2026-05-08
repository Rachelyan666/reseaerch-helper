from research_agent.agent import Agent
from research_agent.memory_store import MemoryEntry
from research_agent.models import Message, ModelResponse, ToolCall
from research_agent.permissions import PermissionManager
from research_agent.skills import LoadedSkill
from research_agent.tools import ToolRegistry


class FakeModel:
    def __init__(self):
        self.calls = 0
        self.seen_messages = []
        self.system_prompts = []

    def generate(self, messages, tools, system_prompt):
        self.calls += 1
        self.seen_messages.append(list(messages))
        self.system_prompts.append(system_prompt)
        if self.calls == 1:
            return ModelResponse(
                output_text="planning",
                tool_calls=[ToolCall(id="1", name="todo_write", arguments={
                    "items": [
                        {"id": "discover", "content": "Discover sources", "status": "in_progress"},
                        {"id": "fetch", "content": "Fetch source text", "status": "pending"},
                    ],
                    "merge": False,
                })],
            )
        if self.calls == 2:
            return ModelResponse(
                output_text="need a skill",
                tool_calls=[ToolCall(id="2", name="skill_load", arguments={"name": "source-selection"})],
            )
        if self.calls == 3:
            return ModelResponse(
                output_text="delegate",
                tool_calls=[ToolCall(id="3", name="subagent", arguments={"task": "Review source credibility"})],
            )
        if self.calls == 4:
            return ModelResponse(
                output_text="search",
                tool_calls=[ToolCall(id="4", name="search_web", arguments={"query": "Acme competitors"})],
            )
        return ModelResponse(output_text="final answer")


class FakeSubagentRunner:
    def __init__(self):
        self.tasks = []

    def run(self, task, parent_messages):
        self.tasks.append({"task": task, "parent_messages": list(parent_messages)})
        return "Subagent summary: official site and reputable press should be prioritized"


class ApprovalRecorder:
    def __init__(self, response="allow"):
        self.response = response
        self.calls = []

    def __call__(self, tool_call):
        self.calls.append(tool_call.name)
        return self.response


def test_agent_executes_tool_calls_and_appends_tool_results(tmp_path):
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "source-selection.md").write_text(
        "---\nname: source-selection\ndescription: Prefer official and reputable sources\n---\nUse primary sources first.\n",
        encoding="utf-8",
    )

    tool_registry = ToolRegistry()
    tool_registry.register("search_web", lambda query: [{"title": "Acme", "url": "https://example.com", "snippet": "Result"}])

    model = FakeModel()
    subagent_runner = FakeSubagentRunner()
    agent = Agent(
        model=model,
        tool_registry=tool_registry,
        skills_dir=skills_dir,
        subagent_runner=subagent_runner,
        compact_after_messages=6,
    )

    result = agent.run("Research Acme")

    assert result == "final answer"
    assert model.calls == 5
    assert any(message.role == "tool" and "Discover sources" in message.content for message in agent.messages)
    assert any(message.role == "tool" and "Use primary sources first." in message.content for message in agent.messages)
    assert any(message.role == "tool" and "Subagent summary" in message.content for message in agent.messages)
    assert subagent_runner.tasks[0]["task"] == "Review source credibility"


def test_agent_compacts_history_after_threshold(tmp_path):
    tool_registry = ToolRegistry()
    model = FakeModel()
    subagent_runner = FakeSubagentRunner()
    agent = Agent(
        model=model,
        tool_registry=tool_registry,
        skills_dir=tmp_path,
        subagent_runner=subagent_runner,
        compact_after_messages=3,
    )

    agent.messages = [
        Message(role="user", content="one"),
        Message(role="assistant", content="two"),
        Message(role="user", content="three"),
        Message(role="assistant", content="four"),
    ]

    agent._compact_if_needed()

    assert agent.messages[0].role == "system"
    assert "Earlier conversation summary" in agent.messages[0].content


def test_agent_applies_permissions_hooks_memory_prompt_building_and_recovery(tmp_path):
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "source-selection.md").write_text(
        "---\nname: source-selection\ndescription: Prefer official and reputable sources\n---\nUse primary sources first.\n",
        encoding="utf-8",
    )

    memory_dir = tmp_path / ".memory"
    memory_dir.mkdir()
    (memory_dir / "official-sources.md").write_text(
        "---\nkind: project\ntitle: Official sources\ndescription: Prefer official sources\n---\nPrefer official company sources before commentary.\n",
        encoding="utf-8",
    )
    (tmp_path / "CLAUDE.md").write_text("# Local instructions\nDo not publish speculative claims.\n", encoding="utf-8")
    (tmp_path / ".hooks.json").write_text(
        '{"PreToolUse": [{"matcher": "search_web", "command": "python -c \\\"import sys; sys.stderr.write(\'remember source quality\'); raise SystemExit(2)\\\""}], "PostToolUse": [{"matcher": "search_web", "command": "python -c \\\"import sys; sys.stderr.write(\'audit logged\'); raise SystemExit(2)\\\""}]}',
        encoding="utf-8",
    )

    class RecoveringModel:
        def __init__(self):
            self.calls = 0
            self.system_prompts = []

        def generate(self, messages, tools, system_prompt):
            self.calls += 1
            self.system_prompts.append(system_prompt)
            if self.calls == 1:
                return ModelResponse(output_text="partial answer", stop_reason="max_tokens")
            if self.calls == 2:
                return ModelResponse(
                    output_text="searching",
                    tool_calls=[ToolCall(id="search-1", name="search_web", arguments={"query": "Acme"})],
                )
            return ModelResponse(output_text="final answer")

    tool_registry = ToolRegistry()
    tool_registry.register("search_web", lambda query: [{"title": query, "url": "https://example.com", "snippet": "Result"}])
    approval = ApprovalRecorder(response="allow")
    permission_manager = PermissionManager(mode="auto", approval_callback=approval)
    agent = Agent(
        model=RecoveringModel(),
        tool_registry=tool_registry,
        skills_dir=skills_dir,
        compact_after_messages=20,
        permission_manager=permission_manager,
        memory_dir=memory_dir,
        hooks_path=tmp_path / ".hooks.json",
        workspace_root=tmp_path,
    )

    result = agent.run("Research Acme")

    assert result == "final answer"
    assert any(message.role == "user" and "Continue directly" in message.content for message in agent.messages)
    assert any(message.role == "system" and "remember source quality" in message.content for message in agent.messages)
    assert any(message.role == "tool" and "audit logged" in message.content for message in agent.messages)
    assert any(message.role == "tool" and '"title": "Acme"' in message.content for message in agent.messages)
    assert approval.calls == []
    assert "## Memory" in agent.model.system_prompts[0]
    assert "Prefer official company sources" in agent.model.system_prompts[0]
    assert "## CLAUDE.md Chain" in agent.model.system_prompts[0]
    assert "Do not publish speculative claims." in agent.model.system_prompts[0]
