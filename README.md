# Research Agent

A Python command-line research agent for market and company research.

It can:
- run a no-API demo mode
- run live web research with an OpenAI-compatible model
- save every result as a markdown note
- keep durable local state for tasks, schedules, team inboxes, plugins, and worktrees

This repo is designed so someone can clone it, install it, and get a result quickly.

## What you get

- **CLI app** via `research-agent`
- **Demo mode** that works without API keys
- **Live research mode** with `search_web` and `fetch_webpage`
- **Markdown output** saved to `notes/` by default
- **Workspace-aware runtime** so generated state stays in one folder
- **Small Python API** for scripting

## Requirements

- Python **3.9+**
- macOS, Linux, or another environment with Python virtualenv support

## Quickstart

### 1) Clone and install

```bash
git clone https://github.com/Rachelyan666/reseaerch-helper.git
cd research-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

If you want the test tools too:

```bash
pip install -e '.[dev]'
```

### 2) Run the demo mode

This requires **no API key** and is the easiest way for someone to confirm the project works.

```bash
research-agent demo "Figma competitors"
```

What happens:
- the markdown note is printed to the terminal
- the same note is saved under `notes/` in the active workspace

Example saved path:

```text
notes/20260507-231602-figma-competitors.md
```

### 3) Run live research mode

Create a local `.env` from the example file:

```bash
cp .env.example .env
```

Then set your API key in `.env`:

```env
OPENAI_API_KEY=your_real_key_here
```

Now run:

```bash
research-agent research "Figma competitors"
```

You can also pass a custom output file:

```bash
research-agent research "Figma competitors" --output ./figma-competitors.md
```

## The easiest way for other people to run this repo

If your goal is GitHub friendliness, this is the best onboarding path:

1. **Keep demo mode front and center**  
   People should be able to run something useful without setting up secrets first.

2. **Show the exact 5 commands to install and run**  
   Avoid making readers infer setup steps.

3. **Use `.env.example` for live mode**  
   This repo already supports that flow.

4. **Save output to a predictable place**  
   This repo saves markdown notes to `notes/` by default.

5. **Keep generated files out of git**  
   Runtime directories like `notes/`, `.tasks/`, and `.team/` should not be committed.

6. **Make the README work for first-time visitors**  
   The first successful run should be obvious and fast.

## CLI usage

### Core commands

```bash
research-agent demo "Figma competitors"
research-agent research "Figma competitors"
research-agent chat
research-agent chat --live
```

### Save output to a specific file

```bash
research-agent demo "Acme competitors" --output ./acme-demo.md
research-agent research "Acme competitors" --output ./acme-live.md
```

### Use a separate workspace

By default, the workspace is the current directory.

To isolate runtime state somewhere else:

```bash
research-agent --workspace ~/research-agent-data demo "B2B design tools"
```

Or set an environment variable:

```bash
export RESEARCH_AGENT_WORKSPACE=~/research-agent-data
```

## Workspace layout

The workspace root stores local runtime state and generated output:

- `notes/` — generated markdown research notes
- `.tasks/` — durable tasks
- `.schedules/` — schedule records
- `.team/` — teammate roster, inboxes, and protocol state
- `.worktrees/` — isolated work lanes
- `.memory/` — local durable memory
- `plugins/` — external plugin manifests
- `skills/` — optional workspace-specific skills
- `.hooks.json` — optional hook configuration

If `skills/` does not exist in the workspace, the package falls back to bundled default skills.

## Live mode configuration

The CLI auto-loads `.env` from the workspace root for live commands.

Minimum setup:

```env
OPENAI_API_KEY=your_real_key_here
```

Optional overrides:

```env
OPENAI_MODEL=gpt-4.1-mini
OPENAI_BASE_URL=https://api.openai.com/v1
```

## Python API

```python
from research_agent import AgentPaths, build_live_agent, build_live_prompt

paths = AgentPaths.from_workspace("~/research-agent-data")
agent = build_live_agent(api_key="...", paths=paths)
result = agent.run(build_live_prompt("Figma competitors"))
print(result)
agent.close()
```

## More CLI commands

### Durable tasks

```bash
research-agent task create "Collect sources" --prompt "Research Acme competitors"
research-agent task list
research-agent task ready
research-agent task run 1
research-agent task run 1 --output ./task-1-note.md
```

### Scheduling

```bash
research-agent schedule create "30 9 * * 1" "Run weekly market scan"
research-agent schedule list
research-agent schedule run-due
```

### Team runtime

```bash
research-agent team register researcher research
research-agent team list
research-agent team send researcher reviewer "Please check source quality"
research-agent team inbox reviewer
```

### Worktree isolation

```bash
research-agent worktree create market-scan
research-agent worktree list
```

### Plugins

```bash
research-agent plugin list
```

## Verify the install

After installation, these should work:

```bash
research-agent --help
python -m research_agent --help
research-agent demo "AMD competitors"
```

## Development

Install dev dependencies:

```bash
pip install -e '.[dev]'
```

Run tests:

```bash
pytest -q
```

## Troubleshooting

### `research-agent: command not found`

Your virtualenv is probably not activated.

```bash
source .venv/bin/activate
```

### Live mode says `OPENAI_API_KEY must be set`

Create `.env` from the example file and set a real key:

```bash
cp .env.example .env
```

Then edit:

```env
OPENAI_API_KEY=your_real_key_here
```

### I only want to see whether the repo works

Use demo mode first:

```bash
research-agent demo "Figma competitors"
```

## Suggested next GitHub improvements

These are the highest-value next steps for making the repo even easier for others:

1. **Add a LICENSE file** so people know how they can use the code.
2. **Add GitHub Actions CI** to run `pytest -q` on every push.
3. **Add a sample output note** under `examples/` so visitors can see expected results instantly.
4. **Add screenshots or terminal GIFs** for the README.
5. **Publish a first tagged release** once the CLI shape feels stable.

## Current scope

This package currently includes the tutorial-style runtime through s19:
- s01-s11 core loop, tools, compaction, permissions, hooks, memory, prompt assembly, recovery
- s12-s14 durable tasks, background work, scheduling
- s15-s19 persistent teammates, protocols, bounded autonomy, worktree lanes, and plugin tool routing
