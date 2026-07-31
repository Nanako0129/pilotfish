import assert from "node:assert/strict";
import test from "node:test";

import { decodeUser, encodeUser } from "./store.mjs";

test("version 1 payloads round trip", () => {
  const user = { id: "u-1", name: "Nana" };
  assert.deepEqual(decodeUser(encodeUser(user)), user);
});
