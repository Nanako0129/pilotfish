import assert from "node:assert/strict";
import test from "node:test";

import { Session } from "../src/session.js";

test("commits finalized usage into status-line state", () => {
  const session = new Session();
  session.startAssistant("response-1");

  assert.equal(session.committedUsage(), null);

  session.finishAssistant("response-1", {
    inputTokens: 2300,
    outputTokens: 400,
  });

  assert.deepEqual(session.committedUsage(), {
    inputTokens: 2300,
    outputTokens: 400,
  });
});

test("a new provisional response preserves the prior committed snapshot", () => {
  const session = new Session();
  session.startAssistant("response-1");
  session.finishAssistant("response-1", {
    inputTokens: 2300,
    outputTokens: 400,
  });

  session.startAssistant("response-2");

  assert.deepEqual(session.committedUsage(), {
    inputTokens: 2300,
    outputTokens: 400,
  });
});
