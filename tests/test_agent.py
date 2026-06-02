"""Unit tests for agent assembly.

Planned coverage:
    - build_agent returns a runnable for each supported model name.
    - All five tools are bound to the model.
    - The model factory (agent/llms.py) routes premier and cheaper identifiers
      to the right providers.
    - An out of scope input results in a graceful decline.

No tests implemented yet; this is a scaffold.
"""
