"""NRCS Conservation Program Navigator.

Top level package for the AAI-510 final team project. Exposes the data
pipeline, the five agent tools, the LangGraph agent, and the evaluation
harness as importable submodules so the notebooks stay thin.

Subpackages:
    data        Pipeline building blocks (CSV load, eCFR embedding, vector store).
    tools       The five tools the agent can call.
    agent       LLM factory, prompts, and the ReAct graph assembly.
    evaluation  Eval datasets, LLM as judge, and trace runner.
"""
