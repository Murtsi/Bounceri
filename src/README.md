# src/

Your application code goes here. Suggested layout once the stack is chosen:

```
src/
├── app/            # UI routes or entrypoints
├── components/     # reusable UI
├── lib/            # pure logic, no I/O
├── server/         # API handlers, services
└── db/             # schema, migrations, seed data
```

Rules of thumb:

- `lib/` stays framework-free and unit-testable.
- No secrets at import time; read env in one module (`src/lib/env.*`).
- The demo path is sacred: keep a seed script that produces the exact demo state.
