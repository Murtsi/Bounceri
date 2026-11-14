# Private traffic log imports

`POST /api/imports/traffic` requires the existing administrator bearer token before reading the body. It accepts a JSON envelope with a format, UTF-8 line data and permission/source provenance. Imports are private by default and do not replace the live source, queue paid reviews, train a model, create trusted labels or activate enforcement.

```json
{
  "format": "normalized_jsonl",
  "synthetic": false,
  "public_demo": false,
  "provenance": {"kind": "owner_log", "permission_confirmed": true},
  "data": "{\"ts\":\"2026-11-15T12:00:00Z\",\"ip\":\"192.0.2.1\",\"method\":\"GET\",\"path\":\"/products\",\"status\":200}\n"
}
```

The 201 response contains `case`, `source_key` and `report`. Source keys use a new `import/<opaque-id>` namespace. The source is an immutable private SQL archive; its normalized requests, safe report/provenance, redacted investigation and local assessment commit in one transaction. A case failure rolls back every row. The original live source is untouched. Case source kind is `uploaded_log`; non-synthetic imports participate in the existing real-origin filter and display as Imported traffic. Public inspection still requires an explicitly synthetic import and `public_demo:true`; a real/private import cannot become public by default.

## Formats and unavailable data

- `caddy_jsonl`: one default Caddy access JSON object per line. Required fields are ts, client_ip or remote_ip in request, method, uri and status.
- `normalized_jsonl`: one object per line with required ts, ip, method, path and status. Optional bytes, user_agent, headers, content_type and username have explicit missingness. Timestamps are finite Unix seconds or timezone-aware ISO strings converted to UTC. Status is an integer 100–599; response bytes are integer 0–2^63-1. IPs are canonical plain IPv4/IPv6, not hostnames/scoped addresses.
- `nginx_combined` / `apache_combined`: the standard combined layout with IP/identity/user, [day/EnglishMonth/year:time offset], quoted request, status, bytes, referer and user agent. Their callbacks share centralized validation/redaction. A dash byte count or UA is unavailable. Full headers, content type and login targets cannot be recovered from combined logs. Custom layouts must have a deliberately registered parser; they are not guessed.

The parser registry only converts a line into the canonical shape. The shared validator enforces core types, removes secrets and creates availability masks. Uploaded private flags cannot claim fields were measured. Missing core fields reject that line; later valid lines still run. Reports provide accepted/rejected/nonempty-line counts, fixed numeric error codes/positions (first 20), optional missing counters, unmapped counts, redaction/capping counters and UTC time range. No raw rejected line, target username, credential or arbitrary exception text is returned. Rejected-source coverage is explicit and makes the resulting case incomplete/review-ineligible rather than silently claiming a complete source.

## Redaction and analysis

Authorization, proxy credentials, cookies, simulator markers/signatures, bodies and unsupported headers are discarded. All request queries, fragments and absolute-URL authority/userinfo are removed. Referer URLs are discarded; only an observed presence marker is retained. The bounded header allowlist preserves the native fingerprint inputs, including Accept-Encoding. Oversized allowed values are capped and marked unavailable, so truncation cannot invent complete header fingerprints.

Login targets are HMAC-pseudonymized with a fresh per-import key after the native strip/lower normalization. Whitespace-only targets remain unknown. This matches the native case-insensitive target convention; it is not proof that a source system treats differently cased names as one account. Raw values never reach persistence or case output. Separate imports do not automatically link target identities. Path segments and allowed header values can still contain source-specific personal data that generic parsing cannot recognize; redact those before uploading and review the fixed report limitation.

Analysis runs in a fixed local child process with provider/database/simulator settings removed. It uses native deterministic rules, no learned model, no DNS and no paid requests. Project-specific honey traps are disabled for foreign logs. Unsupported header-derived features and behavior clusters are omitted when their inputs were not logged. Safe per-session availability survives the subprocess and archive; it does not expose private record annotations. Unknown account logging omits the account count instead of reporting zero, and unknown shared-target counts stay null. Counts and booleans retain their native types.

Generic URL patterns can produce local heuristic findings, but use `generic-path-patterns-v1` rather than source-site attack proof. Advisory review cannot turn them alone into confirmed maliciousness or restrictive suggestions. The imported site context and unavailable inputs are visible limitations. Uploaded labels never become evaluation truth. The evaluation CLI suppresses current-DNS/project-trap labels for imported sources, reports unknown features as missing, and refuses incomplete labeled data before training or writing metrics/models. Public source/permission attestations are recorded as owner-attested, not independently verified human/bot labels.

## Limits and failures

The complete JSON body is at most 10 MiB and must finish within 10 seconds; JSON quoting/envelope bytes count toward that cap. Parser input is at most 10 MiB, 2,000 nonempty lines, 256KiB per line and a seven-day min/max timestamp span, with a five-second parser budget. The isolated analyzer admits at most 2,000 records, 10MiB input, 8MiB output and five seconds including startup/cleanup/output validation (OS process creation itself is not preemptible). These are upper bounds; resource-heavy valid batches can hit the deadline. Preserve collection/actor grouping when splitting datasets rather than treating chunks as independent holdouts.

One import job runs per API process. The upload slot and actual thread job are guarded separately so disconnect/cancellation cannot admit another analyzer while the first job continues. A disconnected request may still finish its authorized private transaction; inspect private case history before retrying. There is no implicit idempotency promise.

- 401: administrator token missing/invalid, including malformed non-ASCII credentials.
- 408: upload timeout.
- 413: byte/line/record/span/parser limits.
- 422: invalid contract, no valid rows, unsupported data or failed/limited analysis; invalid publication is rejected before storage.
- 429: import job busy, with Retry-After.
- 503: storage unavailable.

`provenance.kind` is owner_log, public_dataset or consented_input. Every kind requires permission_confirmed:true. Public datasets also require an HTTPS source_url and license/terms reference; consented input requires a consent_reference, whose hash is retained. URL credentials/queries/fragments are removed; references are metadata only and are never fetched. These fields record provenance and permission assertions, not legal compliance or a human-study consent workflow. Study enrollment, reviewed labels and independently withheld evaluation remain later gates.

Raw uploads are not retained. Sanitized native data/report/provenance remain in an immutable source until its separately managed archival lifecycle; ordinary active-source age pruning preserves visible archive rows. Source deletion/backup lifecycle and consent withdrawal are operations/study work, not an undocumented deletion side effect of importing.
