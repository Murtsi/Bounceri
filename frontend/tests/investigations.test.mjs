import assert from "node:assert/strict";
import test from "node:test";
import {
  formatEvaluationMetric,
  assessmentStage,
  capabilityState,
  formatScore,
  reviewState,
  sourceState,
} from "../src/investigationPresentation.ts";

test("evaluation shows published counts and intervals without inventing missing or invalid rates", () => {
  assert.deepEqual(
    formatEvaluationMetric({ numerator: 0, denominator: 14, value: 0, ci95_lower: 0, ci95_upper: 0.21531 }),
    { count: "0 / 14", percent: "0.00%", interval: "0.00%–21.53%" },
  );
  assert.deepEqual(formatEvaluationMetric({ numerator: 0, denominator: 0, value: 0 }), {
    count: "0 / 0",
    percent: "Not reported",
    interval: "Not reported",
  });
  assert.deepEqual(
    formatEvaluationMetric({ numerator: 15, denominator: 14, value: 1.1, ci95_lower: 0.9, ci95_upper: 0.2 }),
    { count: "Not reported", percent: "Not reported", interval: "Not reported" },
  );
});

test("actual API assessment stage takes precedence with a legacy kind fallback", () => {
  assert.equal(assessmentStage({ stage: "decision_model" }), "decision_model");
  assert.equal(assessmentStage({ stage: "local", kind: "reviewer" }), "local");
  assert.equal(assessmentStage({ kind: "reviewer" }), "reviewer");
  assert.equal(assessmentStage({}), undefined);
});

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


test("uploaded traffic has an explicit origin without claiming verified human identity", () => {
  assert.equal(sourceState({ kind: "uploaded_log", synthetic: false }).label, "Imported traffic");
});
