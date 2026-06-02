"""Unit tests for agent assembly.

Planned coverage:
    - build_agent returns a runnable for each supported model name.
    - All four tools are bound to the model.
    - The model factory (agent/llms.py) routes premier and cheaper identifiers
      to the right providers.
    - An out of scope input results in a graceful decline driven by the system
      prompt scope guard (no tool call).

No tests implemented yet; this is a scaffold.
"""
