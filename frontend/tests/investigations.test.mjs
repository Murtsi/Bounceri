import assert from "node:assert/strict";
import test from "node:test";
import { capabilityState, formatScore, reviewState, sourceState } from "../src/investigationPresentation.ts";

test("future modules cannot appear implemented merely because a server enables them", () => {
  assert.equal(capabilityState("spot_the_swarm", { enabled: true }).enabled, false);
  assert.equal(capabilityState("clean_traffic", { enabled: true, implemented: true }).enabled, true);
  assert.equal(capabilityState("clean_traffic", { enabled: true, implemented: false }).enabled, false);
  assert.equal(capabilityState("clean_traffic", undefined).label, "Status unavailable");
});

test("provenance is explicit; missing provenance is never labelled real", () => {
  assert.equal(sourceState({ kind: "fixture", synthetic: true }).label, "Synthetic fixture");
  assert.equal(sourceState({ kind: "monitored_traffic", synthetic: true }).synthetic, true);
  assert.equal(sourceState({ kind: "monitored_traffic", synthetic: false }).label, "Real traffic");
  assert.equal(sourceState({ kind: "fixture", synthetic: false }).label, "Fixture · origin unverified");
  assert.equal(sourceState(undefined).label, "Origin unavailable");
});

test("a missing, invalid or out-of-range detector score never becomes a confident number", () => {
  assert.equal(formatScore(null), "Not reported");
  assert.equal(formatScore(undefined), "Not reported");
  assert.equal(formatScore(NaN), "Not reported");
  assert.equal(formatScore(9), "Not reported");
  assert.equal(formatScore(0), "0.00 / 1");
  assert.equal(formatScore(0.75), "0.75 / 1");
});

test("review absence, outage, budget deferral, failure and unknown state stay distinct", () => {
  assert.equal(reviewState("not_requested").label, "Not requested");
  assert.equal(reviewState("completed").label, "Completed");
  assert.equal(reviewState("failed").tone, "danger");
  assert.equal(reviewState("unavailable").label, "Unavailable");
  assert.equal(reviewState("deferred_budget").label, "Deferred · budget");
  assert.equal(reviewState("new_server_state").label, "Unknown review status");
});
