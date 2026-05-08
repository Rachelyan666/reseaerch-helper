from research_agent import Agent, AgentPaths, build_demo_agent, build_live_prompt


def test_public_api_exports_primary_entrypoints():
    assert Agent is not None
    assert AgentPaths is not None
    assert callable(build_demo_agent)
    assert build_live_prompt("Acme")
