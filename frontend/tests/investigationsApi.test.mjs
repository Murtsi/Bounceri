import assert from "node:assert/strict";
import test from "node:test";
import { investigationApi } from "../src/investigationsApi.ts";

test("case listing requests bounded pages and applies the origin filter on the server", async (t) => {
  const paths = [];
  t.mock.method(globalThis, "fetch", async (path, options) => {
    paths.push(path);
    assert.equal(options.method ?? "GET", "GET");
    return Response.json([{ id: "older-real-case" }]);
  });
  assert.deepEqual(await investigationApi.investigations("real", 100), [{ id: "older-real-case" }]);
  await investigationApi.investigations();
  assert.deepEqual(paths, [
    "/api/investigations?limit=100&offset=100&origin=real",
    "/api/investigations?limit=100&offset=0&origin=all",
  ]);
});
