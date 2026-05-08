from research_agent.agent import Agent
from research_agent.models import ModelResponse, ToolCall


class TeamModel:
    def __init__(self):
        self.calls = 0

    def generate(self, messages, tools, system_prompt):
        self.calls += 1
        if self.calls == 1:
            return ModelResponse(
                output_text="forming team",
                tool_calls=[ToolCall(id="team-1", name="team_register", arguments={"name": "researcher", "role": "research"})],
            )
        if self.calls == 2:
            return ModelResponse(
                output_text="sending protocol request",
                tool_calls=[ToolCall(id="msg-1", name="team_send", arguments={"sender": "lead", "recipient": "researcher", "content": "Draft a plan", "message_type": "plan_request"})],
            )
        return ModelResponse(output_text="done")


def test_agent_exposes_team_tools_and_records_team_messages(tmp_path):
    agent = Agent(model=TeamModel(), skills_dir=tmp_path, workspace_root=tmp_path)

    result = agent.run("Coordinate a teammate")

    assert result == "done"
    tool_names = [tool["name"] for tool in agent._tool_definitions()]
    assert "team_register" in tool_names
    assert "team_send" in tool_names
    inbox_path = tmp_path / ".team" / "inbox" / "researcher.jsonl"
    assert inbox_path.exists()
