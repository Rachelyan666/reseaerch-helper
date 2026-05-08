from __future__ import annotations

from research_agent.models import ModelResponse, ToolCall


class TutorialDemoModel:
    """Deterministic model used to exercise the tutorial-aligned loop through s19."""

    def __init__(self) -> None:
        self.calls = 0
        self.query: str | None = None

    def generate(self, messages, tools, system_prompt):
        self.calls += 1
        if self.query is None:
            self.query = next((message.content for message in messages if message.role == "user"), "research topic")
        query = self.query
        if self.calls == 1:
            return ModelResponse(
                output_text="Planning the work.",
                tool_calls=[
                    ToolCall(
                        id="todo-1",
                        name="todo_write",
                        arguments={
                            "items": [{"id": "discover", "content": f"Discover sources for: {query}", "status": "in_progress"}],
                            "merge": False,
                        },
                    )
                ],
            )
        if self.calls == 2:
            return ModelResponse(output_text="Registering a teammate.", tool_calls=[ToolCall(id="team-1", name="team_register", arguments={"name": "researcher", "role": "research"})])
        if self.calls == 3:
            return ModelResponse(output_text="Creating a durable task.", tool_calls=[ToolCall(id="task-1", name="task_create", arguments={"subject": f"Research {query}", "prompt": query})])
        if self.calls == 4:
            return ModelResponse(output_text="Creating a worktree lane.", tool_calls=[ToolCall(id="wt-1", name="worktree_create", arguments={"name": query.lower().replace(' ', '-')[:20]})])
        if self.calls == 5:
            return ModelResponse(output_text="Searching for sources.", tool_calls=[ToolCall(id="search-1", name="search_web", arguments={"query": query})])
        return ModelResponse(
            output_text=(
                f"# Research note\n\n"
                f"## Query\n- {query}\n\n"
                f"## Summary\n- Demonstrated the tutorial-aligned s01-s19 harness using todos, teammates, durable tasks, worktree lanes, permissions, hooks, prompt assembly, and recovery scaffolding.\n"
                f"- Live research and plugin tools can now fit into the same loop without changing the core architecture."
            )
        )
