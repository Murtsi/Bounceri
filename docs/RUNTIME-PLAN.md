# Selected Bounceri runtime direction

The owner selected option B: Microsoft-Decision-1 assessments followed by a stronger final reviewer. Featherless replaces Gemini as the reviewer provider. Clean the traffic is the first implementation priority; social coordination and propaganda analysis follow only after the web-traffic product is measured and deployed.

## Intended flow

Hostinger-hosted log/auth ingestion → local session/campaign evidence → Microsoft-Decision-1 through Hostinger Router → Featherless reviewer → evidence validation and recorded advisory verdict → dashboard.

The reviewer must receive original supporting evidence as well as Decision-1 findings, preserve uncertainty, cite evidence and record revisions rather than overwrite earlier decisions. No automatic blocking is planned. Model outputs are not trusted training labels.

## Implemented provider groundwork

The existing S7 explanation client defaults to Featherless and requires an explicit model ID plus `FEATHERLESS_API_KEY`. It retains grounded fallback text, bounds response length, disables automatic retries and never changes paid providers automatically. The cache distinguishes configured provider/model choices. No credentials are committed or automatically persisted.

S7 still explains the local scorer's verdict; it is not yet the final decision orchestrator. Decision-1 calls, final-review schemas, the usage ledger, asynchronous case queue and dashboard remain implementation work. The repository's current explanation-only rule continues to describe the existing code; replacing it with final advisory review requires the new orchestration implementation and evaluation.

## Before enabling live calls

Verify the actual Hostinger Decision-1 model/endpoint and the permitted Featherless model IDs, account plan, credit balance and prices. Do not assume an API key proves model access or that promotional balances transfer between services. Retain the agreed $5 total paid-inference target and enforce it in the future orchestrator's usage ledger; client token limits alone are not a total-spend cap.

Training, data generation and automated evaluation remain local/CPU and require no LLM calls. Calls must be case-based, cached by evidence version and compared with the local baseline on held-out data. The live app remains on Hostinger; model inference is served remotely.
