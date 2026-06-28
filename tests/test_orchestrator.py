"""Tests for the Orchestrator Router."""

import pytest
from src.agents.orchestrator import Orchestrator, TOOLS


def test_registry_shape():
    """Ensure all registered tools have the required shape."""
    assert "ask_mentor" in TOOLS
    assert "convene_board" in TOOLS
    assert "finance_summary" in TOOLS
    assert "safe_to_spend" in TOOLS
    assert "scan_signals" in TOOLS
    
    for name, tool in TOOLS.items():
        assert tool.name == name
        assert tool.description
        assert tool.arg_hint
        assert callable(tool.func)


def test_dispatching_mentor(monkeypatch):
    """Test dispatching to ask_mentor."""
    orch = Orchestrator()
    
    def fake_route(user_input):
        return {"tool": "ask_mentor", "args": {"question": "How are you?"}}
    monkeypatch.setattr(orch, "route", fake_route)
    
    class FakeMentor:
        def ask(self, q):
            class FakeResp:
                answer = f"Mentor says: {q}"
            return FakeResp()
    
    import src.agents.orchestrator as orch_module
    monkeypatch.setattr(orch_module, "Mentor", FakeMentor)
    
    result = orch.run("dummy input")
    assert result.tool_used == "ask_mentor"
    assert result.output == "Mentor says: How are you?"


def test_dispatching_board(monkeypatch):
    """Test dispatching to convene_board."""
    orch = Orchestrator()
    
    def fake_route(user_input):
        return {"tool": "convene_board", "args": {"decision": "Should I buy a boat?"}}
    monkeypatch.setattr(orch, "route", fake_route)
    
    class FakeRuling:
        verdict = "No boat for you."
    
    import src.agents.orchestrator as orch_module
    monkeypatch.setattr(orch_module, "convene_board", lambda d: FakeRuling())
    
    result = orch.run("dummy input")
    assert result.tool_used == "convene_board"
    assert result.output == "No boat for you."


def test_unknown_tool_fallback(monkeypatch):
    """Test fallback to ask_mentor when tool is unknown."""
    orch = Orchestrator()
    
    def fake_route(user_input):
        return {"tool": "does_not_exist", "args": {}}
    monkeypatch.setattr(orch, "route", fake_route)
    
    class FakeMentor:
        def ask(self, q):
            class FakeResp:
                answer = "Fallback mentor output."
            return FakeResp()
    
    import src.agents.orchestrator as orch_module
    monkeypatch.setattr(orch_module, "Mentor", FakeMentor)
    
    result = orch.run("some random input")
    assert result.tool_used == "ask_mentor"
    assert result.args == {"question": "some random input"}
    assert result.output == "Fallback mentor output."


def test_bad_args_fallback(monkeypatch):
    """Test fallback to ask_mentor when a tool crashes (e.g. bad args)."""
    orch = Orchestrator()
    
    def fake_route(user_input):
        return {"tool": "scan_signals", "args": {}}  # Missing args
    monkeypatch.setattr(orch, "route", fake_route)
    
    class FakeMentor:
        def ask(self, q):
            class FakeResp:
                answer = "Fallback due to exception."
            return FakeResp()
    
    import src.agents.orchestrator as orch_module
    monkeypatch.setattr(orch_module, "Mentor", FakeMentor)
    
    result = orch.run("bad args input")
    assert result.tool_used == "ask_mentor"
    assert result.output == "Fallback due to exception."


def test_route_parsing_error(monkeypatch):
    """Test that if the LLM output is garbage, route() falls back safely."""
    orch = Orchestrator()
    
    class FakeLLM:
        def generate(self, prompt, **kwargs):
            return "This is not json."
    
    orch.llm = FakeLLM()
    
    routing = orch.route("I want to do a thing")
    assert routing["tool"] == "ask_mentor"
    assert routing["args"] == {"question": "I want to do a thing"}
