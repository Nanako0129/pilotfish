import assert from "node:assert/strict";
import test from "node:test";

import { banner } from "./cli.mjs";

test("banner greets the user", () => {
  assert.equal(banner({ id: "u-1", name: "Nana" }), "Welcome, Nana <u-1>!");
});
