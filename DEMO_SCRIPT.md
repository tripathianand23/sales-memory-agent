# Sales Memory Agent Demo Script

## Scene 1: Open Dashboard And Show Memory Health

Open **Dashboard**. Show the Hindsight memory health panel:

- Hindsight enabled
- Configured
- Reachable
- Bank ID
- Fallback status

Explain that the app uses real Hindsight when credentials are configured and clearly marks fallback mode when they are not.

## Scene 2: Log Sarah Chen At CloudNova

Open **Log Interaction** and enter:

- Prospect: Sarah Chen
- Company: CloudNova
- Role: VP Revenue Operations
- Interaction type: Discovery call
- Meeting notes: Sarah wants reps to remember expansion context before every renewal call.
- Objection: Security concerns
- Competitor: Gong
- Budget: $150K if security review passes
- Timeline: Pilot this quarter
- Decision makers: Sarah Chen and CISO Marcus Lee
- Next steps: Send security packet and schedule RevOps workflow review

Submit the interaction.

## Scene 3: Show Retained Hindsight Payload

On the submission result, show:

- "Memory retained in Hindsight" if configured, or the explicit fallback warning
- Retained payload preview
- Tags for prospect, company, deal ID, and `memory_type:sales_interaction`
- Timestamp

Explain: the meeting is not just saved to the app database; it is retained as long-term sales memory.

## Scene 4: Generate Generic Follow-up Without Memory

Open **Generate Follow-up Email** for Sarah Chen. Point to **Without Memory**. It is polite, but generic.

## Scene 5: Generate Personalized Follow-up With Hindsight Recall

On the same page, show **With Hindsight Memory**. It should reference Sarah's CloudNova context, security concern, Gong, budget, stakeholders, and next step.

## Scene 6: Open Memory Inspector

Open **Memory Inspector**, select Sarah Chen / CloudNova, and show:

- Raw recalled Hindsight memories
- Tags
- Metadata
- Timestamp
- Retain and recall activity

## Scene 7: Explain Why The Agent Improves

Explain:

- The generic assistant only knows the current prompt.
- Sales Memory Agent retains prospect history in Hindsight.
- Later brief and email generation recall that history.
- Hindsight `reflect()` turns remembered context into a better deal strategy.

Closing line:

> Sales teams do not need another stateless assistant. They need an agent that remembers the account, learns the deal, and makes every next touch smarter.
