from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from research_agent.autonomy import AutonomousCoordinator
from research_agent.background import BackgroundManager
from research_agent.compaction import ContextCompactor
from research_agent.hooks import HookManager
from research_agent.memory_store import MemoryStore
from research_agent.models import Message, ToolCall
from research_agent.permissions import PermissionManager
from research_agent.plugins import PluginManager
from research_agent.prompting import SystemPromptBuilder, discover_instruction_chain
from research_agent.protocols import ProtocolManager
from research_agent.recovery import RecoveryManager, RecoveryState
from research_agent.scheduler import ScheduleManager
from research_agent.skills import SkillLibrary
from research_agent.task_runtime import TaskManager
from research_agent.team import MessageBus, TeammateManager
from research_agent.todos import TodoItem, TodoList
from research_agent.tools import ToolRegistry
from research_agent.worktrees import WorktreeManager

CORE_SYSTEM_PROMPT = """You are a research agent built following tutorial stages s01-s19.
- s01: operate as a closed loop of model -> tools -> tool results -> repeat.
- s02: prefer tools when real-world information is needed.
- s03: keep a visible todo list when tasks become multi-step.
- s04: use subagents as context boundaries for isolated subtasks.
- s05: discover skills cheaply and load them deeply only when needed.
- s06: compact older context into summaries when the transcript gets long.
- s07: pass every tool call through deny/mode/allow/ask permissions.
- s08: allow hooks to observe, block, or annotate tool usage.
- s09: inject durable memory, but treat live observations as source of truth.
- s10: assemble the system prompt from stable and dynamic sections.
- s11: recover from truncation, context overflow, and transient transport failures.
- s12: use durable task graphs for work that survives compaction and restarts.
- s13: treat background execution as another runtime lane, not another main loop.
- s14: let schedules feed the same loop from time-based triggers.
- s15: persistent teammates communicate through durable inboxes.
- s16: protocol requests use request IDs and explicit approval states.
- s17: autonomy comes from idle polling, self-claiming, and bounded shutdown behavior.
- s18: tasks answer what; worktrees answer where.
- s19: external plugin tools join the same routing, permission, and result-append path as native tools.
When performing company research, use tools to gather live evidence first, then produce a concise markdown research note grounded in fetched sources.
"""


@dataclass
class NullSubagentRunner:
    def run(self, task: str, parent_messages: list[Message]) -> str:
        return f"Subagent was not configured. Task was: {task}"


class Agent:
    def __init__(
        self,
        model: Any,
        tool_registry: ToolRegistry | None = None,
        skills_dir: Path | None = None,
        subagent_runner: Any | None = None,
        compact_after_messages: int = 12,
        permission_manager: PermissionManager | None = None,
        memory_dir: Path | None = None,
        hooks_path: Path | None = None,
        workspace_root: Path | None = None,
        recovery_manager: RecoveryManager | None = None,
        progress_callback: Callable[[str], None] | None = None,
        task_manager: TaskManager | None = None,
        background_manager: BackgroundManager | None = None,
        background_worker: Callable[[str], str] | None = None,
        schedule_manager: ScheduleManager | None = None,
        teammate_manager: TeammateManager | None = None,
        message_bus: MessageBus | None = None,
        protocol_manager: ProtocolManager | None = None,
        worktree_manager: WorktreeManager | None = None,
        plugin_manager: PluginManager | None = None,
    ) -> None:
        self.model = model
        self.tool_registry = tool_registry or ToolRegistry()
        self.skill_library = SkillLibrary(skills_dir or Path("skills"))
        self.subagent_runner = subagent_runner or NullSubagentRunner()
        self.todo_list = TodoList()
        keep_last = max(2, compact_after_messages - 1)
        self.compactor = ContextCompactor(max_messages=compact_after_messages, keep_last=keep_last)
        self.permission_manager = permission_manager or PermissionManager(mode="auto", approval_callback=lambda tool_call: "allow")
        self.memory_store = MemoryStore(memory_dir or Path(".memory"))
        self.hook_manager = HookManager(hooks_path)
        self.workspace_root = Path(workspace_root).resolve() if workspace_root else Path.cwd()
        self.recovery_manager = recovery_manager or RecoveryManager()
        self.progress_callback = progress_callback
        self.task_manager = task_manager or TaskManager(self.workspace_root / ".tasks")
        self.background_manager = background_manager or BackgroundManager(task_manager=self.task_manager)
        self.background_worker = background_worker
        self.schedule_manager = schedule_manager or ScheduleManager(self.workspace_root / ".schedules")
        self.teammate_manager = teammate_manager or TeammateManager(self.workspace_root / ".team")
        self.message_bus = message_bus or MessageBus(self.workspace_root / ".team")
        self.protocol_manager = protocol_manager or ProtocolManager(self.workspace_root / ".team")
        self.worktree_manager = worktree_manager or WorktreeManager(
            self.workspace_root / ".worktrees", workspace_root=self.workspace_root, task_manager=self.task_manager
        )
        self.plugin_manager = plugin_manager or PluginManager(self.workspace_root / "plugins")
        self.autonomy = AutonomousCoordinator(
            task_manager=self.task_manager,
            teammate_manager=self.teammate_manager,
            bus=self.message_bus,
        )
        self.messages: list[Message] = []
        self.loaded_skills: list[str] = []

    def run(self, query: str) -> str:
        self.hook_manager.run_session_start()
        self.messages = [Message(role="user", content=query)]
        recovery_state = RecoveryState()
        while True:
            self._drain_background_notifications()
            self._compact_if_needed()
            try:
                self._emit_progress("Thinking…")
                response = self.model.generate(
                    messages=self.messages,
                    tools=self._tool_definitions(),
                    system_prompt=self._build_system_prompt(),
                )
            except Exception as exc:
                decision = self.recovery_manager.choose_recovery(stop_reason=None, error_text=str(exc))
                if decision.kind == "compact":
                    self.messages = self.recovery_manager.apply_compaction(self.messages, recovery_state, self.compactor)
                    continue
                if decision.kind == "backoff":
                    self.recovery_manager.apply_backoff(recovery_state)
                    continue
                raise

            self.messages.append(Message(role="assistant", content=response.output_text, tool_calls=list(response.tool_calls)))
            if response.stop_reason == "max_tokens":
                self.messages = self.recovery_manager.apply_continuation(self.messages, recovery_state)
                continue
            if response.stop_reason != "tool_use":
                return response.output_text
            for tool_call in response.tool_calls:
                tool_result = self._execute_tool_call(tool_call)
                self.messages.append(Message(role="tool", content=tool_result, tool_call_id=tool_call.id))

    def _build_system_prompt(self) -> str:
        builder = SystemPromptBuilder(
            core_prompt=CORE_SYSTEM_PROMPT,
            tool_definitions=self._tool_definitions(),
            loaded_skills=self.loaded_skills,
            memory_entries=self.memory_store.load_relevant(limit=10),
            instruction_paths=discover_instruction_chain(self.workspace_root),
            runtime_context={"cwd": str(self.workspace_root), "mode": self.permission_manager.mode},
        )
        return builder.build()

    def _tool_definitions(self) -> list[dict[str, Any]]:
        builtins = [
            {
                "name": "todo_write",
                "description": "Create or update the visible todo list for the current research task.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "items": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},
                                    "content": {"type": "string"},
                                    "status": {"type": "string"},
                                },
                                "required": ["id", "content", "status"],
                            },
                        },
                        "merge": {"type": "boolean"},
                    },
                    "required": ["items"],
                },
            },
            {"name": "skill_list", "description": "List available skills with short descriptions.", "input_schema": {"type": "object", "properties": {}}},
            {
                "name": "skill_load",
                "description": "Load a skill in full when its guidance is relevant.",
                "input_schema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
            },
            {
                "name": "subagent",
                "description": "Delegate a bounded subtask to an isolated subagent context.",
                "input_schema": {"type": "object", "properties": {"task": {"type": "string"}}, "required": ["task"]},
            },
            {
                "name": "task_create",
                "description": "Create a durable task record with optional dependencies and a prompt.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "subject": {"type": "string"},
                        "description": {"type": "string"},
                        "blocked_by": {"type": "array", "items": {"type": "integer"}},
                        "owner": {"type": "string"},
                        "prompt": {"type": "string"},
                    },
                    "required": ["subject"],
                },
            },
            {
                "name": "task_update",
                "description": "Update a durable task status or metadata.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "integer"},
                        "status": {"type": "string"},
                        "description": {"type": "string"},
                        "owner": {"type": "string"},
                        "prompt": {"type": "string"},
                        "result": {"type": "string"},
                        "worktree": {"type": "string"},
                    },
                    "required": ["task_id"],
                },
            },
            {"name": "task_list", "description": "List durable tasks.", "input_schema": {"type": "object", "properties": {"status": {"type": "string"}}}},
            {"name": "task_ready", "description": "List tasks that are ready to start because they have no remaining blockers.", "input_schema": {"type": "object", "properties": {}}},
            {
                "name": "background_task",
                "description": "Start a background task that will report back on a later model turn.",
                "input_schema": {
                    "type": "object",
                    "properties": {"prompt": {"type": "string"}, "subject": {"type": "string"}, "task_id": {"type": "integer"}},
                    "required": ["prompt"],
                },
            },
            {
                "name": "team_register",
                "description": "Register or update a persistent teammate in the team roster.",
                "input_schema": {"type": "object", "properties": {"name": {"type": "string"}, "role": {"type": "string"}, "status": {"type": "string"}}, "required": ["name", "role"]},
            },
            {"name": "team_list", "description": "List registered teammates.", "input_schema": {"type": "object", "properties": {}}},
            {
                "name": "team_send",
                "description": "Send a durable message to another teammate inbox.",
                "input_schema": {"type": "object", "properties": {"sender": {"type": "string"}, "recipient": {"type": "string"}, "content": {"type": "string"}, "message_type": {"type": "string"}}, "required": ["sender", "recipient", "content"]},
            },
            {
                "name": "team_inbox",
                "description": "Read and drain a teammate inbox.",
                "input_schema": {"type": "object", "properties": {"recipient": {"type": "string"}}, "required": ["recipient"]},
            },
            {
                "name": "protocol_shutdown_request",
                "description": "Create a shutdown protocol request for a teammate.",
                "input_schema": {"type": "object", "properties": {"target": {"type": "string"}}, "required": ["target"]},
            },
            {
                "name": "protocol_shutdown_response",
                "description": "Approve or reject a shutdown request.",
                "input_schema": {"type": "object", "properties": {"request_id": {"type": "string"}, "approve": {"type": "boolean"}, "reason": {"type": "string"}}, "required": ["request_id", "approve"]},
            },
            {
                "name": "protocol_plan_request",
                "description": "Create a plan approval request.",
                "input_schema": {"type": "object", "properties": {"sender": {"type": "string"}, "recipient": {"type": "string"}, "plan": {"type": "string"}}, "required": ["sender", "recipient", "plan"]},
            },
            {
                "name": "protocol_plan_response",
                "description": "Approve or reject a plan request.",
                "input_schema": {"type": "object", "properties": {"request_id": {"type": "string"}, "approve": {"type": "boolean"}, "reason": {"type": "string"}}, "required": ["request_id", "approve"]},
            },
            {
                "name": "autonomy_claim_ready",
                "description": "Let a teammate auto-claim the next ready unowned task.",
                "input_schema": {"type": "object", "properties": {"teammate": {"type": "string"}}, "required": ["teammate"]},
            },
            {
                "name": "autonomy_idle_once",
                "description": "Run one idle polling cycle for a teammate.",
                "input_schema": {"type": "object", "properties": {"teammate": {"type": "string"}}, "required": ["teammate"]},
            },
            {
                "name": "worktree_create",
                "description": "Create an isolated worktree lane and optionally bind it to a task.",
                "input_schema": {"type": "object", "properties": {"name": {"type": "string"}, "task_id": {"type": "integer"}}, "required": ["name"]},
            },
            {"name": "worktree_list", "description": "List worktree lanes.", "input_schema": {"type": "object", "properties": {}}},
        ]
        return builtins + self.tool_registry.definitions() + self.plugin_manager.definitions()

    def _execute_tool_call(self, tool_call: ToolCall) -> str:
        self._emit_progress(self._describe_tool_start(tool_call))
        pre_hook = self.hook_manager.run_pre_tool_use(tool_call)
        if pre_hook.should_block:
            return f"Tool blocked by hook: {pre_hook.message}"
        if pre_hook.message:
            self.messages.append(Message(role="system", content=pre_hook.message))

        permission = self.permission_manager.decide(tool_call)
        if permission.outcome != "allow":
            return f"Permission denied ({permission.reason})"

        try:
            name = tool_call.name
            if name == "todo_write":
                result = self._handle_todo_write(tool_call.arguments)
            elif name == "skill_list":
                result = self._handle_skill_list()
            elif name == "skill_load":
                result = self._handle_skill_load(tool_call.arguments)
            elif name == "subagent":
                result = self._handle_subagent(tool_call.arguments)
            elif name == "task_create":
                result = self._handle_task_create(tool_call.arguments)
            elif name == "task_update":
                result = self._handle_task_update(tool_call.arguments)
            elif name == "task_list":
                result = self._handle_task_list(tool_call.arguments)
            elif name == "task_ready":
                result = self._handle_task_ready()
            elif name == "background_task":
                result = self._handle_background_task(tool_call.arguments)
            elif name == "team_register":
                result = self._handle_team_register(tool_call.arguments)
            elif name == "team_list":
                result = self._handle_team_list()
            elif name == "team_send":
                result = self._handle_team_send(tool_call.arguments)
            elif name == "team_inbox":
                result = self._handle_team_inbox(tool_call.arguments)
            elif name == "protocol_shutdown_request":
                result = self._handle_shutdown_request(tool_call.arguments)
            elif name == "protocol_shutdown_response":
                result = self._handle_shutdown_response(tool_call.arguments)
            elif name == "protocol_plan_request":
                result = self._handle_plan_request(tool_call.arguments)
            elif name == "protocol_plan_response":
                result = self._handle_plan_response(tool_call.arguments)
            elif name == "autonomy_claim_ready":
                result = self._handle_autonomy_claim(tool_call.arguments)
            elif name == "autonomy_idle_once":
                result = self._handle_autonomy_idle(tool_call.arguments)
            elif name == "worktree_create":
                result = self._handle_worktree_create(tool_call.arguments)
            elif name == "worktree_list":
                result = self._handle_worktree_list()
            elif self.plugin_manager.has_tool(name):
                result = self.plugin_manager.execute(name, tool_call.arguments)
            else:
                result = self.tool_registry.execute(name, tool_call.arguments)
        except Exception as exc:
            return f"Tool execution failed for {tool_call.name}: {exc}"

        self._emit_progress(f"Finished {tool_call.name}.")
        return self.hook_manager.run_post_tool_use(tool_call, result).annotated_result

    def _handle_todo_write(self, arguments: dict[str, Any]) -> str:
        items = [TodoItem(**item) for item in arguments.get("items", [])]
        if arguments.get("merge", False):
            self.todo_list.merge(items)
        else:
            self.todo_list.replace(items)
        return self.todo_list.render()

    def _handle_skill_list(self) -> str:
        return str(self.skill_library.list_skills())

    def _handle_skill_load(self, arguments: dict[str, Any]) -> str:
        loaded = self.skill_library.load_skill(arguments["name"])
        descriptor = f"{loaded.name}: {loaded.description}"
        if descriptor not in self.loaded_skills:
            self.loaded_skills.append(descriptor)
        return f"Loaded skill {loaded.name}: {loaded.description}\n\n{loaded.content}"

    def _handle_subagent(self, arguments: dict[str, Any]) -> str:
        return self.subagent_runner.run(arguments["task"], self.messages)

    def _handle_task_create(self, arguments: dict[str, Any]) -> str:
        task = self.task_manager.create(
            subject=arguments["subject"],
            description=arguments.get("description", ""),
            blocked_by=[int(item) for item in arguments.get("blocked_by", [])],
            owner=arguments.get("owner", ""),
            prompt=arguments.get("prompt", ""),
        )
        return self.task_manager.render([task])

    def _handle_task_update(self, arguments: dict[str, Any]) -> str:
        task = self.task_manager.update(
            int(arguments["task_id"]),
            status=arguments.get("status"),
            description=arguments.get("description"),
            owner=arguments.get("owner"),
            prompt=arguments.get("prompt"),
            result=arguments.get("result"),
            worktree=arguments.get("worktree"),
        )
        return self.task_manager.render([task])

    def _handle_task_list(self, arguments: dict[str, Any]) -> str:
        return self.task_manager.render(self.task_manager.list_tasks(status=arguments.get("status")))

    def _handle_task_ready(self) -> str:
        return self.task_manager.render(self.task_manager.ready_tasks())

    def _handle_background_task(self, arguments: dict[str, Any]) -> str:
        if self.background_worker is None:
            return "Background worker not configured."
        prompt = arguments["prompt"]
        task_id = arguments.get("task_id")
        run_id = self.background_manager.run(
            subject=arguments.get("subject", prompt),
            worker=lambda: self.background_worker(prompt),
            task_id=int(task_id) if task_id is not None else None,
        )
        return f"Background task {run_id} started"

    def _handle_team_register(self, arguments: dict[str, Any]) -> str:
        member = self.teammate_manager.register(name=arguments["name"], role=arguments["role"], status=arguments.get("status", "working"))
        return f"{member.name} ({member.role}) status={member.status}"

    def _handle_team_list(self) -> str:
        members = self.teammate_manager.list_members()
        if not members:
            return "No teammates."
        return "\n".join(f"{member.name} ({member.role}) status={member.status}" for member in members)

    def _handle_team_send(self, arguments: dict[str, Any]) -> str:
        message = self.message_bus.send(
            sender=arguments["sender"],
            recipient=arguments["recipient"],
            content=arguments["content"],
            message_type=arguments.get("message_type", "message"),
        )
        return f"Sent {message.message_type} from {message.sender} to {message.recipient}"

    def _handle_team_inbox(self, arguments: dict[str, Any]) -> str:
        messages = self.message_bus.read_inbox(arguments["recipient"])
        if not messages:
            return "Inbox empty."
        return "\n".join(f"{message.sender}: {message.content}" for message in messages)

    def _handle_shutdown_request(self, arguments: dict[str, Any]) -> str:
        request = self.protocol_manager.create_shutdown_request(target=arguments["target"])
        return f"shutdown_request {request.request_id} pending for {request.target}"

    def _handle_shutdown_response(self, arguments: dict[str, Any]) -> str:
        request = self.protocol_manager.record_shutdown_response(arguments["request_id"], approve=bool(arguments["approve"]), reason=arguments.get("reason", ""))
        return f"shutdown_request {request.request_id} {request.status}"

    def _handle_plan_request(self, arguments: dict[str, Any]) -> str:
        request = self.protocol_manager.create_plan_request(sender=arguments["sender"], recipient=arguments["recipient"], plan=arguments["plan"])
        return f"plan_request {request.request_id} pending"

    def _handle_plan_response(self, arguments: dict[str, Any]) -> str:
        request = self.protocol_manager.record_plan_response(arguments["request_id"], approve=bool(arguments["approve"]), reason=arguments.get("reason", ""))
        return f"plan_request {request.request_id} {request.status}"

    def _handle_autonomy_claim(self, arguments: dict[str, Any]) -> str:
        task = self.autonomy.claim_next_ready_task(arguments["teammate"])
        if task is None:
            return "No ready tasks available."
        return self.task_manager.render([task])

    def _handle_autonomy_idle(self, arguments: dict[str, Any]) -> str:
        event = self.autonomy.idle_poll_once(arguments["teammate"])
        if event is None:
            return "No work found during idle poll."
        return f"{event.kind}: {event.payload}"

    def _handle_worktree_create(self, arguments: dict[str, Any]) -> str:
        task_id = arguments.get("task_id")
        record = self.worktree_manager.create(name=arguments["name"], task_id=int(task_id) if task_id is not None else None)
        return f"{record.name} state={record.state} kind={record.kind}"

    def _handle_worktree_list(self) -> str:
        records = self.worktree_manager.list()
        if not records:
            return "No worktrees."
        return "\n".join(f"{record.name} state={record.state} task_id={record.task_id}" for record in records)

    def _emit_progress(self, message: str) -> None:
        if self.progress_callback is not None:
            self.progress_callback(message)

    def _describe_tool_start(self, tool_call: ToolCall) -> str:
        if tool_call.name == "search_web":
            return f"Searching the web for: {tool_call.arguments.get('query', '')}"
        if tool_call.name == "fetch_webpage":
            return f"Fetching webpage: {tool_call.arguments.get('url', '')}"
        if tool_call.name == "background_task":
            return f"Starting background task: {tool_call.arguments.get('prompt', '')}"
        return f"Running tool: {tool_call.name}"

    def _drain_background_notifications(self) -> None:
        for notification in self.background_manager.drain_notifications():
            suffix = f" task={notification.task_id}" if notification.task_id is not None else ""
            self.messages.append(Message(role="system", content=f"Background task {notification.run_id}{suffix} {notification.status}: {notification.result}"))

    def _compact_if_needed(self) -> None:
        self.messages = self.compactor.compact(self.messages)
