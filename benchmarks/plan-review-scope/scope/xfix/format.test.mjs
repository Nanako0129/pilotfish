import assert from "node:assert/strict";
import test from "node:test";

import { formatUser } from "./format.mjs";

test("formatUser renders name and id", () => {
  assert.equal(formatUser({ id: "u-1", name: "Nana" }), "Nana <u-1>");
});
