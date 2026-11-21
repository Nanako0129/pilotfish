import assert from "node:assert/strict";
import test from "node:test";

import { reportLine } from "./report.mjs";
import { encodeUser } from "./store.mjs";

test("reportLine renders a stored user", () => {
  assert.equal(reportLine(encodeUser({ id: "u-1", name: "Nana" })), "user: Nana <u-1>");
});
