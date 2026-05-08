from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer

from research_agent.config import AgentPaths
from research_agent.factory import (
    build_demo_agent,
    build_live_agent,
    build_live_prompt,
    load_project_env,
    resolve_api_key,
)
from research_agent.plugins import PluginManager
from research_agent.protocols import ProtocolManager
from research_agent.scheduler import ScheduleManager
from research_agent.task_runtime import TaskManager
from research_agent.team import MessageBus, TeammateManager
from research_agent.worktrees import WorktreeManager

app = typer.Typer(help="Research agent CLI")
task_app = typer.Typer(help="Durable task graph commands")
schedule_app = typer.Typer(help="Schedule commands")
team_app = typer.Typer(help="Persistent teammate commands")
protocol_app = typer.Typer(help="Team protocol commands")
worktree_app = typer.Typer(help="Worktree isolation commands")
plugin_app = typer.Typer(help="External plugin tool commands")
app.add_typer(task_app, name="task")
app.add_typer(schedule_app, name="schedule")
app.add_typer(team_app, name="team")
app.add_typer(protocol_app, name="protocol")
app.add_typer(worktree_app, name="worktree")
app.add_typer(plugin_app, name="plugin")

# Backward-compatible aliases used by tests and by older integrations.
_build_demo_agent = build_demo_agent
_build_live_agent = build_live_agent
_build_live_prompt = build_live_prompt


class CliState:
    def __init__(self, paths: AgentPaths) -> None:
        self.paths = paths


def _project_root() -> Path:
    return Path.cwd().resolve()


@app.callback()
def main(
    ctx: typer.Context,
    workspace: Optional[Path] = typer.Option(
        None,
        "--workspace",
        help="Workspace root containing agent state directories such as .tasks, .schedules, .team, and plugins/.",
    ),
) -> None:
    fallback_workspace = os.getenv("RESEARCH_AGENT_WORKSPACE") or _project_root()
    ctx.obj = CliState(AgentPaths.from_workspace(workspace or fallback_workspace))


def _state(ctx: typer.Context) -> CliState:
    if ctx.obj is None:
        fallback_workspace = os.getenv("RESEARCH_AGENT_WORKSPACE") or _project_root()
        ctx.obj = CliState(AgentPaths.from_workspace(fallback_workspace))
    return ctx.obj


def _paths(ctx: typer.Context) -> AgentPaths:
    return _state(ctx).paths


def _task_manager(ctx: typer.Context) -> TaskManager:
    return TaskManager(_paths(ctx).tasks_dir)


def _schedule_manager(ctx: typer.Context) -> ScheduleManager:
    return ScheduleManager(_paths(ctx).schedules_dir)


def _teammate_manager(ctx: typer.Context) -> TeammateManager:
    return TeammateManager(_paths(ctx).team_dir)


def _message_bus(ctx: typer.Context) -> MessageBus:
    return MessageBus(_paths(ctx).team_dir)


def _protocol_manager(ctx: typer.Context) -> ProtocolManager:
    return ProtocolManager(_paths(ctx).team_dir)


def _worktree_manager(ctx: typer.Context) -> WorktreeManager:
    paths = _paths(ctx)
    return WorktreeManager(paths.worktrees_dir, workspace_root=paths.workspace_root, task_manager=_task_manager(ctx))


def _plugin_manager(ctx: typer.Context) -> PluginManager:
    return PluginManager(_paths(ctx).plugins_dir)


def _print_progress(message: str) -> None:
    typer.echo(f"[progress] {message}")


def _slugify_filename(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "research-note"


def _default_note_path(*, paths: AgentPaths, query: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return paths.notes_dir / f"{timestamp}-{_slugify_filename(query)[:80]}.md"


def _write_markdown_note(markdown: str, *, paths: AgentPaths, query: str, output: Optional[Path] = None) -> Path:
    note_path = (output or _default_note_path(paths=paths, query=query)).expanduser().resolve()
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text(markdown, encoding="utf-8")
    return note_path


def _resolve_api_key(api_key: Optional[str], *, project_root: Path) -> str:
    try:
        return resolve_api_key(api_key, project_root=project_root)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


def _make_demo_agent(*, paths: AgentPaths):
    try:
        return _build_demo_agent(paths=paths)
    except TypeError:
        return _build_demo_agent()


def _make_live_agent(*, api_key: str, paths: AgentPaths, progress_callback):
    try:
        return _build_live_agent(api_key=api_key, paths=paths, progress_callback=progress_callback)
    except TypeError:
        return _build_live_agent(api_key=api_key, progress_callback=progress_callback)


def _close_agent(agent) -> None:
    closer = getattr(agent, "close", None)
    if callable(closer):
        closer()


@app.command()
def demo(
    ctx: typer.Context,
    query: str,
    output: Optional[Path] = typer.Option(None, "--output", help="Optional output path for the generated markdown note. Defaults to notes/<timestamp>-<query>.md inside the workspace."),
) -> None:
    """Run the tutorial-style demo loop once for a query."""
    paths = _paths(ctx)
    result = _make_demo_agent(paths=paths).run(query)
    note_path = _write_markdown_note(result, paths=paths, query=query, output=output)
    typer.echo(result)
    typer.echo(f"\n[saved] {note_path}")


@app.command()
def research(
    ctx: typer.Context,
    query: str,
    api_key: Optional[str] = typer.Option(None, "--api-key", help="Explicit OpenAI API key for live mode; otherwise use OPENAI_API_KEY."),
    output: Optional[Path] = typer.Option(None, "--output", help="Optional output path for the generated markdown note. Defaults to notes/<timestamp>-<query>.md inside the workspace."),
) -> None:
    """Run the live research agent against real web data and a real LLM API."""
    paths = _paths(ctx)
    resolved_api_key = _resolve_api_key(api_key, project_root=paths.workspace_root)
    agent = _make_live_agent(api_key=resolved_api_key, paths=paths, progress_callback=_print_progress)
    try:
        result = agent.run(_build_live_prompt(query))
    finally:
        _close_agent(agent)
    note_path = _write_markdown_note(result, paths=paths, query=query, output=output)
    typer.echo(result)
    typer.echo(f"\n[saved] {note_path}")


@app.command()
def chat(
    ctx: typer.Context,
    live: bool = typer.Option(False, "--live", help="Use the live LLM + web tools instead of the deterministic demo."),
    api_key: Optional[str] = typer.Option(None, "--api-key", help="Explicit OpenAI API key for live mode; otherwise use OPENAI_API_KEY."),
) -> None:
    """Simple command-line chat that runs a fresh tutorial-style demo loop per query."""
    paths = _paths(ctx)
    mode_label = "live research" if live else "tutorial demo"
    typer.echo(f"{mode_label.title()} chat. Type a research question, or `quit` to exit.")
    while True:
        query = typer.prompt("research")
        if query.strip().lower() in {"quit", "exit"}:
            typer.echo("Goodbye.")
            raise typer.Exit()
        if live:
            resolved_api_key = _resolve_api_key(api_key, project_root=paths.workspace_root)
            agent = _make_live_agent(api_key=resolved_api_key, paths=paths, progress_callback=_print_progress)
            prompt = _build_live_prompt(query)
        else:
            agent = _make_demo_agent(paths=paths)
            prompt = query
        try:
            typer.echo(agent.run(prompt))
        finally:
            _close_agent(agent)
        typer.echo("\n---\n")


@task_app.command("create")
def task_create(
    ctx: typer.Context,
    subject: str,
    prompt: Optional[str] = typer.Option(None, "--prompt", help="Prompt or research query to run for this task later."),
    description: str = typer.Option("", "--description", help="Optional task description."),
) -> None:
    manager = _task_manager(ctx)
    task = manager.create(subject=subject, description=description, prompt=prompt or "")
    typer.echo(manager.render([task]))


@task_app.command("list")
def task_list(ctx: typer.Context, status: Optional[str] = typer.Option(None, "--status", help="Optional status filter.")) -> None:
    manager = _task_manager(ctx)
    typer.echo(manager.render(manager.list_tasks(status=status)))


@task_app.command("ready")
def task_ready(ctx: typer.Context) -> None:
    manager = _task_manager(ctx)
    typer.echo(manager.render(manager.ready_tasks()))


@task_app.command("complete")
def task_complete(ctx: typer.Context, task_id: int) -> None:
    manager = _task_manager(ctx)
    task = manager.update(task_id, status="completed")
    typer.echo(manager.render([task]))


@task_app.command("run")
def task_run(
    ctx: typer.Context,
    task_id: int,
    live: bool = typer.Option(False, "--live", help="Use the live research stack for this task."),
    api_key: Optional[str] = typer.Option(None, "--api-key", help="Explicit OpenAI API key for live mode."),
    output: Optional[Path] = typer.Option(None, "--output", help="Optional output path for the generated markdown note. Defaults to notes/<timestamp>-<task-subject>.md inside the workspace."),
) -> None:
    manager = _task_manager(ctx)
    paths = _paths(ctx)
    task = manager.get(task_id)
    manager.update(task_id, status="in_progress")
    if live:
        resolved_api_key = _resolve_api_key(api_key, project_root=paths.workspace_root)
        agent = _make_live_agent(api_key=resolved_api_key, paths=paths, progress_callback=_print_progress)
        try:
            result = agent.run(_build_live_prompt(task.prompt or task.subject))
        finally:
            _close_agent(agent)
    else:
        result = _make_demo_agent(paths=paths).run(task.prompt or task.subject)
    manager.update(task_id, status="completed", result=result)
    note_path = _write_markdown_note(result, paths=paths, query=task.subject, output=output)
    typer.echo(result)
    typer.echo(f"\n[saved] {note_path}")


@schedule_app.command("create")
def schedule_create(
    ctx: typer.Context,
    cron_expr: str,
    prompt: str,
    recurring: bool = typer.Option(True, "--recurring/--once", help="Recurring by default; use --once for a one-shot schedule."),
) -> None:
    record = _schedule_manager(ctx).create(cron_expr=cron_expr, prompt=prompt, recurring=recurring)
    typer.echo(f"[{record.id}] cron={record.cron_expr} prompt={record.prompt} recurring={record.recurring}")


@schedule_app.command("list")
def schedule_list(ctx: typer.Context) -> None:
    typer.echo(_schedule_manager(ctx).render())


@schedule_app.command("run-due")
def schedule_run_due(
    ctx: typer.Context,
    live: bool = typer.Option(False, "--live", help="Use the live research stack for due jobs."),
    api_key: Optional[str] = typer.Option(None, "--api-key", help="Explicit OpenAI API key for live mode."),
) -> None:
    paths = _paths(ctx)
    manager = _schedule_manager(ctx)
    due_jobs = manager.collect_due_prompts(datetime.now())
    if not due_jobs:
        typer.echo("No schedules due.")
        return
    live_agent = None
    if live:
        resolved_api_key = _resolve_api_key(api_key, project_root=paths.workspace_root)
        live_agent = _make_live_agent(api_key=resolved_api_key, paths=paths, progress_callback=_print_progress)
    try:
        for job in due_jobs:
            typer.echo(f"[{job.id}] {job.prompt}")
            if live_agent is not None:
                result = live_agent.run(_build_live_prompt(job.prompt))
            else:
                result = _make_demo_agent(paths=paths).run(job.prompt)
            typer.echo(result)
            typer.echo("\n---\n")
    finally:
        if live_agent is not None:
            _close_agent(live_agent)


@team_app.command("register")
def team_register(
    ctx: typer.Context,
    name: str,
    role: str,
    status: str = typer.Option("working", "--status", help="Initial teammate status."),
) -> None:
    member = _teammate_manager(ctx).register(name=name, role=role, status=status)
    typer.echo(f"{member.name} ({member.role}) status={member.status}")


@team_app.command("list")
def team_list(ctx: typer.Context) -> None:
    members = _teammate_manager(ctx).list_members()
    if not members:
        typer.echo("No teammates.")
        return
    for member in members:
        typer.echo(f"{member.name} ({member.role}) status={member.status}")


@team_app.command("send")
def team_send(
    ctx: typer.Context,
    sender: str,
    recipient: str,
    content: str,
    message_type: str = typer.Option("message", "--type", help="Team message type."),
) -> None:
    message = _message_bus(ctx).send(sender=sender, recipient=recipient, content=content, message_type=message_type)
    typer.echo(f"Sent {message.message_type} from {message.sender} to {message.recipient}")


@team_app.command("inbox")
def team_inbox(ctx: typer.Context, recipient: str) -> None:
    messages = _message_bus(ctx).read_inbox(recipient)
    if not messages:
        typer.echo("Inbox empty.")
        return
    for message in messages:
        typer.echo(f"{message.sender}: {message.content}")


@protocol_app.command("shutdown-request")
def protocol_shutdown_request(ctx: typer.Context, target: str) -> None:
    request = _protocol_manager(ctx).create_shutdown_request(target=target)
    typer.echo(f"shutdown_request {request.request_id} pending for {request.target}")


@protocol_app.command("shutdown-respond")
def protocol_shutdown_respond(
    ctx: typer.Context,
    request_id: str,
    approve: bool = typer.Option(True, "--approve/--reject"),
    reason: str = typer.Option("", "--reason"),
) -> None:
    request = _protocol_manager(ctx).record_shutdown_response(request_id, approve=approve, reason=reason)
    typer.echo(f"shutdown_request {request.request_id} {request.status}")


@protocol_app.command("plan-request")
def protocol_plan_request(ctx: typer.Context, sender: str, recipient: str, plan: str) -> None:
    request = _protocol_manager(ctx).create_plan_request(sender=sender, recipient=recipient, plan=plan)
    typer.echo(f"plan_request {request.request_id} pending")


@protocol_app.command("plan-respond")
def protocol_plan_respond(
    ctx: typer.Context,
    request_id: str,
    approve: bool = typer.Option(True, "--approve/--reject"),
    reason: str = typer.Option("", "--reason"),
) -> None:
    request = _protocol_manager(ctx).record_plan_response(request_id, approve=approve, reason=reason)
    typer.echo(f"plan_request {request.request_id} {request.status}")


@worktree_app.command("create")
def worktree_create(
    ctx: typer.Context,
    name: str,
    task_id: Optional[int] = typer.Option(None, "--task-id", help="Optional task id to bind this lane to."),
) -> None:
    record = _worktree_manager(ctx).create(name=name, task_id=task_id)
    typer.echo(f"{record.name} state={record.state} kind={record.kind}")


@worktree_app.command("list")
def worktree_list(ctx: typer.Context) -> None:
    records = _worktree_manager(ctx).list()
    if not records:
        typer.echo("No worktrees.")
        return
    for record in records:
        typer.echo(f"{record.name} state={record.state} task_id={record.task_id}")


@plugin_app.command("list")
def plugin_list(ctx: typer.Context) -> None:
    definitions = _plugin_manager(ctx).definitions()
    if not definitions:
        typer.echo("No plugin tools.")
        return
    for definition in definitions:
        typer.echo(definition["name"])
