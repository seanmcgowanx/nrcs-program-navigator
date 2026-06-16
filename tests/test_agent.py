"""Unit tests for agent assembly.

The agent's external dependencies (the provider SDKs, the LLM itself, and the
Postgres checkpointer) are stubbed, so these run on a bare checkout with no API
key or database. The one genuinely end-to-end check -- that an out of scope
input is declined by the system prompt with no tool call -- needs a real model
and database, so it is guarded behind RUN_AGENT_INTEGRATION and skipped by
default.

Coverage:
    - The model factory (agent/llms.py) routes premier (gpt-*) and cheaper
      (gemini-*) identifiers to the right providers, defaults to the premier
      model, and rejects an unknown name.
    - All four tools are bound to the agent.
    - build_agent wires the chosen model, the tools, the system prompt, and a
      checkpointer together.
    - [integration] An out of scope input results in a graceful decline driven
      by the system prompt scope guard, with no tool call.
"""

import sys
import types

import os

import pytest

from nrcs_navigator import config
from nrcs_navigator.agent import graph, llms, prompts


# --------------------------------------------------------------------------- #
# Model factory (agent/llms.py)
# --------------------------------------------------------------------------- #


def _install_fake_provider(monkeypatch, module_name, class_name, captured):
    """Inject a fake provider module so get_model's lazy import resolves to it.

    Records the constructor kwargs (and which provider was hit) without needing
    the real SDK or an API key.
    """
    module = types.ModuleType(module_name)

    class _FakeModel:
        def __init__(self, **kwargs):
            captured.clear()
            captured.update(kwargs)
            captured["provider"] = class_name

    setattr(module, class_name, _FakeModel)
    monkeypatch.setitem(sys.modules, module_name, module)
    return captured


class TestModelFactory:
    def test_gpt_routes_to_openai(self, monkeypatch):
        captured = {}
        _install_fake_provider(monkeypatch, "langchain_openai", "ChatOpenAI", captured)

        llms.get_model("gpt-4o")

        assert captured["provider"] == "ChatOpenAI"
        assert captured["model"] == "gpt-4o"
        assert captured["temperature"] == config.AGENT_TEMPERATURE

    def test_gemini_routes_to_google(self, monkeypatch):
        captured = {}
        _install_fake_provider(
            monkeypatch, "langchain_google_genai", "ChatGoogleGenerativeAI", captured
        )

        llms.get_model("gemini-1.5-pro")

        assert captured["provider"] == "ChatGoogleGenerativeAI"
        assert captured["model"] == "gemini-1.5-pro"

    def test_defaults_to_premier_model(self, monkeypatch):
        captured = {}
        # The default premier model in this project is a gpt-* identifier.
        assert config.PREMIER_MODEL.startswith("gpt")
        _install_fake_provider(monkeypatch, "langchain_openai", "ChatOpenAI", captured)

        llms.get_model()

        assert captured["model"] == config.PREMIER_MODEL

    def test_unknown_model_raises(self):
        with pytest.raises(ValueError):
            llms.get_model("llama-3")


# --------------------------------------------------------------------------- #
# Tool binding
# --------------------------------------------------------------------------- #


class TestToolBinding:
    def test_all_four_tools_bound(self):
        names = {t.name for t in graph.TOOLS}
        assert names == {
            "eligibility_screener",
            "payment_estimator",
            "practice_matcher",
            "program_availability",
        }
        # Four tools, not five -- scope handling is in the prompt, not a tool.
        assert len(graph.TOOLS) == 4


# --------------------------------------------------------------------------- #
# build_agent wiring
# --------------------------------------------------------------------------- #


class TestBuildAgent:
    def test_wires_model_tools_prompt_and_checkpointer(self, monkeypatch):
        sentinel_model = object()
        sentinel_checkpointer = object()
        sentinel_agent = object()
        seen = {}

        monkeypatch.setattr(graph.llms, "get_model", lambda name=None: sentinel_model)
        monkeypatch.setattr(graph, "_checkpointer", lambda: sentinel_checkpointer)

        def fake_create_react_agent(model, tools, prompt, checkpointer):
            seen.update(
                model=model, tools=tools, prompt=prompt, checkpointer=checkpointer
            )
            return sentinel_agent

        monkeypatch.setattr(graph, "create_react_agent", fake_create_react_agent)

        agent = graph.build_agent("gpt-4o")

        assert agent is sentinel_agent
        assert seen["model"] is sentinel_model
        assert seen["tools"] is graph.TOOLS
        assert seen["prompt"] == prompts.SYSTEM_PROMPT
        assert seen["checkpointer"] is sentinel_checkpointer

    def test_passes_model_name_through_to_factory(self, monkeypatch):
        requested = {}

        def fake_get_model(name=None):
            requested["name"] = name
            return object()

        monkeypatch.setattr(graph.llms, "get_model", fake_get_model)
        monkeypatch.setattr(graph, "_checkpointer", lambda: object())
        monkeypatch.setattr(
            graph, "create_react_agent", lambda *a, **k: object()
        )

        graph.build_agent("gemini-1.5-pro")

        assert requested["name"] == "gemini-1.5-pro"


# --------------------------------------------------------------------------- #
# Scope guard (integration -- needs a real model + database)
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(
    not os.environ.get("RUN_AGENT_INTEGRATION"),
    reason="needs a live model and database; set RUN_AGENT_INTEGRATION to run",
)
def test_out_of_scope_input_declines_without_tool_call():
    """A CRP question is out of scope: the prompt should make the agent decline
    and redirect with no tool call."""
    agent = graph.build_agent()
    result = agent.invoke(
        {"messages": [("user", "How do I enroll my land in CRP?")]},
        config={"configurable": {"thread_id": "test-scope-guard"}},
    )
    messages = result["messages"]
    # No tool was invoked -- the model answered directly.
    assert not any(getattr(m, "tool_calls", None) for m in messages)
    answer = messages[-1].content.lower()
    assert "fsa" in answer
