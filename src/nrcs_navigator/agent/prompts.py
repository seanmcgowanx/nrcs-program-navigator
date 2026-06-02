"""System prompt and tool guidance for the agent.

Keeping prompt text in one place makes it easy to iterate during evaluation
and keeps it identical across the different LLMs being compared.

Intended contents:

  1. Role and scope framing.
     - Frames the agent as an NRCS conservation program navigator: who it
       helps (farmers and landowners) and what it can do (rank programs,
       estimate payments, match practice codes, surface deadlines for EQIP,
       CSP, ACEP, RCPP).
     - Scope guard lives HERE in the system prompt, not in a tool. In scope
       requests (NRCS program guidance) drive the agent toward its four tools.
       Out of scope requests get a polite decline plus a redirect, with no
       tool call and no guessing. Examples of out of scope: CRP questions
       (administered by FSA, a separate agency, so redirect to the local FSA
       office), legal or tax advice, and unrelated chit chat (redirect to the
       local NRCS service center). This is what satisfies the rubric
       requirement to gracefully handle out of scope queries.

  2. Elicitation flow (multi turn).
     - Before screening eligibility, the agent should gather the farmer's
       profile when it is missing: state and county, acreage, current
       practices or operation type, and the primary resource concern (for
       example soil erosion, water quality, grazing land health).
     - The agent asks for the missing fields one conversational step at a
       time rather than dumping a form, and proceeds to tool calls once it
       has enough to screen. Collected fields accumulate in the graph state
       (see agent/graph.py) so the agent does not re ask.

  3. Reasoning and tool guidance.
     - How to reason step by step (Reason, Act, Observe) before calling a
       tool, and when to call each of the four tools: eligibility_screener
       (which programs fit), practice_matcher (applicable practice codes),
       payment_estimator (dollar ranges; note that ACEP is appraisal based,
       so it redirects the user to the local NRCS office rather than quoting
       a rate), deadline_lookup (current ranking dates).

  4. Output formatting guidance.
     - Ranked program list, payment ranges, practice codes, and deadlines,
       each with a citation back to the source (regulation section, practice
       standard, or scraped page).

Text only. No logic.
"""
