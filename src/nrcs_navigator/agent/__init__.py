"""Agent package (AI Engineer owns).

Assembles the single LLM and the five tools into a ReAct agent.

    prompts   System prompt and any tool description text.
    llms      Model factory; returns a chat model for the chosen provider so
              the premier model and the cheaper model are interchangeable.
    graph     LangGraph wiring: binds tools to the model and runs the
              Reason / Act / Observe loop.

notebooks/02_agent_definition.ipynb imports build_agent from here.
"""
