# tests/

Put tests next to the code they cover (`*.test.ts`, `test_*.py`) and cross-cutting
end-to-end tests here.

Hackathon priority:

1. One happy-path E2E test of the demo flow.
2. Unit tests for the logic judges will poke at.
3. Nothing else.

Enable the `stack` job in `.github/workflows/ci.yml` to run them.
