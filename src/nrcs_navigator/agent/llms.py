"""Model factory for the multiple model comparison.

The whole multi model evaluation hinges on being able to swap the agent's LLM
without changing any tool or graph code. This module is that seam: get_model
routes a model identifier to the right provider, and build_agent takes a model
name, so the evaluation can build the same agent on two different models.

Routes by name prefix: gpt-* -> langchain-openai, gemini-* -> langchain-google-genai.
Adding Anthropic or another provider later means adding one branch here. The
returned model supports tool calling so graph.py can bind the tools to it.
"""

from langchain_core.language_models import BaseChatModel

from nrcs_navigator import config


def get_model(name: str | None = None) -> BaseChatModel:
    """Return a tool-calling chat model for the given identifier.

    Routes by name prefix so the premier and cheaper legs are interchangeable:
    gpt-* to OpenAI, gemini-* to Google. Defaults to the premier model from
    config. Temperature comes from config so traces stay reproducible. Providers
    are imported lazily so using one leg does not require the other's package or
    API key to be configured.
    """
    name = name or config.PREMIER_MODEL

    # Retry on transient errors (notably 429 rate limits) with exponential
    # backoff so a momentary token-per-minute spike self-heals instead of failing
    # the run. Tier 1 OpenAI accounts have low per-minute limits, so this matters.
    if name.startswith("gpt"):
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=name, temperature=config.AGENT_TEMPERATURE, max_retries=6
        )

    if name.startswith("gemini"):
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=name, temperature=config.AGENT_TEMPERATURE, max_retries=6
        )

    raise ValueError(
        f"Unknown model '{name}'. Expected a gpt-* (OpenAI) or gemini-* (Google) name."
    )
