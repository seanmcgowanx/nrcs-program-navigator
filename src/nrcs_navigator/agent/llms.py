"""Model factory for the multiple model comparison.

The whole multi model evaluation hinges on being able to swap the agent's LLM
without changing any tool or graph code. This module is that seam.

Intended responsibilities:
    - get_model(name): return a configured LangChain chat model for a given
      identifier. Routes to langchain-openai for the premier model (e.g.
      gpt-4o) and to langchain-google-genai for the cheaper / free leg (e.g.
      gemini-2.0-flash). Adding Anthropic or a Databricks hosted model later
      means adding one branch here.
    - Read default model names and temperature from config so .env controls
      which models run.
    - Optionally expose a small cost table (input/output price per token) per
      model to support the ROI calculation in the evaluation notebook.

The returned model must support tool / function calling so graph.py can bind
the five tools to it.
"""
