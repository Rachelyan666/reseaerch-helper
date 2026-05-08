from research_agent.agent import Agent
from research_agent.models import ModelResponse, ToolCall


class BackgroundAwareModel:
    def __init__(self):
        self.calls = 0

    def generate(self, messages, tools, system_prompt):
        self.calls += 1
        if self.calls == 1:
            return ModelResponse(
                output_text="starting background research",
                tool_calls=[ToolCall(id="bg-1", name="background_task", arguments={"prompt": "Research Acme in background"})],
            )

        background_messages = [message.content for message in messages if message.role == "system" and "Background task" in message.content]
        assert background_messages
        return ModelResponse(output_text="background result received")


def test_agent_drains_background_notifications_before_next_model_call(tmp_path):
    agent = Agent(
        model=BackgroundAwareModel(),
        skills_dir=tmp_path,
        compact_after_messages=10,
        background_worker=lambda prompt: f"Finished: {prompt}",
    )

    result = agent.run("Research Acme")

    assert result == "background result received"
