from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Optional

import httpx

from research_agent.agent import Agent
from research_agent.config import AgentPaths
from research_agent.demo import TutorialDemoModel
from research_agent.llm import OpenAIChatModel
from research_agent.subagents import FunctionSubagentRunner
from research_agent.tools import ToolRegistry
from research_agent.web import DuckDuckGoSearchTool, WebPageFetcher


ProgressCallback = Callable[[str], None]


def load_project_env(project_root: Path | None = None) -> Path | None:
    root = Path(project_root).resolve() if project_root is not None else Path.cwd().resolve()
    env_path = root / ".env"
    if not env_path.exists():
        return None

    placeholder_fragments = {"your_", "placeholder", "changeme", "paste_"}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        normalized = value.lower().replace("-", "_")
        if not key or key in os.environ or not value:
            continue
        if any(fragment in normalized for fragment in placeholder_fragments):
            continue
        os.environ[key] = value
    return env_path


def build_live_prompt(query: str) -> str:
    return (
        f"Research this company/market topic: {query}. "
        "Use live search and webpage fetching tools before answering. "
        "Return a markdown note with sections: Query, Key Findings, Evidence, Competitors/Peers, Risks or Unknowns, and Sources. "
        "Ground every substantive claim in fetched source material."
    )


def resolve_api_key(api_key: Optional[str], *, project_root: Path | None = None) -> str:
    load_project_env(project_root)
    resolved_api_key = api_key or os.getenv("OPENAI_API_KEY")
    if not resolved_api_key:
        raise ValueError("OPENAI_API_KEY must be set or an explicit api_key must be provided for live mode.")
    return resolved_api_key


def build_demo_agent(
    *,
    paths: AgentPaths | None = None,
    enable_background: bool = True,
    progress_callback: ProgressCallback | None = None,
) -> Agent:
    resolved_paths = paths or AgentPaths.from_workspace()
    registry = ToolRegistry()
    registry.register(
        "search_web",
        lambda query: [{"title": f"Official results for {query}", "url": f"https://example.com/search?q={query.replace(' ', '+')}", "snippet": "Demo search result. Replace with a real search provider in the next step."}],
        description="Search the web for relevant sources.",
        input_schema={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    )
    subagent_runner = FunctionSubagentRunner(worker=lambda task, parent_messages: f"Subagent summary for `{task}`: prioritize official sites and reputable reporting.")
    background_worker = None
    if enable_background:
        background_worker = lambda prompt: build_demo_agent(paths=resolved_paths, enable_background=False).run(prompt)
    return Agent(
        model=TutorialDemoModel(),
        tool_registry=registry,
        skills_dir=resolved_paths.resolved_skills_dir(),
        subagent_runner=subagent_runner,
        compact_after_messages=8,
        workspace_root=resolved_paths.workspace_root,
        progress_callback=progress_callback,
        memory_dir=resolved_paths.memory_dir,
        hooks_path=resolved_paths.hooks_path,
        background_worker=background_worker,
    )


def build_live_agent(
    *,
    api_key: Optional[str] = None,
    paths: AgentPaths | None = None,
    progress_callback: ProgressCallback | None = None,
    enable_background: bool = True,
) -> Agent:
    resolved_paths = paths or AgentPaths.from_workspace()
    resolved_api_key = resolve_api_key(api_key, project_root=resolved_paths.workspace_root)
    registry = ToolRegistry()
    shared_client = httpx.Client()
    search_tool = DuckDuckGoSearchTool(http_client=shared_client)
    fetcher = WebPageFetcher(http_client=shared_client)
    registry.register(
        "search_web",
        search_tool.search,
        description="Search the public web for relevant pages about a company, market, competitors, products, or funding.",
        input_schema={"type": "object", "properties": {"query": {"type": "string", "description": "Search query."}, "max_results": {"type": "integer", "description": "Maximum number of results to return.", "default": 5}}, "required": ["query"]},
    )
    registry.register(
        "fetch_webpage",
        fetcher.fetch,
        description="Fetch a webpage and extract readable article or page text for analysis.",
        input_schema={"type": "object", "properties": {"url": {"type": "string", "description": "Absolute URL to fetch."}}, "required": ["url"]},
    )
    subagent_runner = FunctionSubagentRunner(worker=lambda task, parent_messages: f"Subagent note for `{task}`: prioritize official company pages, product docs, pricing pages, and recent reputable reporting.")
    background_worker = None
    if enable_background:
        background_worker = lambda prompt: build_live_agent(api_key=api_key, paths=resolved_paths, enable_background=False).run(build_live_prompt(prompt))
    agent = Agent(
        model=OpenAIChatModel(api_key=resolved_api_key, http_client=shared_client),
        tool_registry=registry,
        skills_dir=resolved_paths.resolved_skills_dir(),
        subagent_runner=subagent_runner,
        compact_after_messages=12,
        workspace_root=resolved_paths.workspace_root,
        progress_callback=progress_callback,
        memory_dir=resolved_paths.memory_dir,
        hooks_path=resolved_paths.hooks_path,
        background_worker=background_worker,
    )
    agent.close = shared_client.close  # type: ignore[attr-defined]
    return agent
