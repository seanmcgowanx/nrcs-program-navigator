"""Agent package.

Assembles the single LLM and the four tools into a ReAct agent.

    prompts   System prompt (role, scope guard, elicitation flow) and tool text.
    llms      Model factory; returns a chat model for the chosen provider so
              the premier model and the cheaper model are interchangeable.
    graph     LangGraph wiring: binds tools to the model and runs the
              Reason / Act / Observe loop.

notebooks/02_agent_definition.ipynb imports build_agent from here.
"""
