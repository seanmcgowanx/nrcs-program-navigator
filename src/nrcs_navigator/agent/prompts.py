"""System prompt and tool guidance for the agent.

Keeping prompt text in one place makes it easy to iterate during evaluation
and keeps it identical across the different LLMs being compared.

Intended contents:
    - The system prompt that frames the agent as an NRCS conservation program
      navigator: who it helps, what it can and cannot do, the NRCS only scope,
      and how it should reason step by step before calling tools.
    - Instructions on when to call each of the five tools.
    - Instructions to decline out of scope requests via out_of_scope_handler
      rather than guessing.
    - Any output formatting guidance (ranked program list, payment ranges,
      practice codes, deadlines, with citations).

Text only. No logic.
"""
