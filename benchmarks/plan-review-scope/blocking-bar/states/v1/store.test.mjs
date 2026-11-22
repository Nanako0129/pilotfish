import assert from "node:assert/strict";
import test from "node:test";

import { decodeUser, encodeUser } from "./store.mjs";

test("version 2 payloads round trip", () => {
  const user = { id: "u-1", name: "Nana" };
  assert.deepEqual(decodeUser(encodeUser(user)), user);
});

test("version 2 writes carry user_id and no user", () => {
  const raw = JSON.parse(encodeUser({ id: "u-1", name: "Nana" }));
  assert.equal(raw.version, 2);
  assert.equal(raw.user_id, "u-1");
  assert.equal("user" in raw, false);
});

test("version 1 legacy payloads still decode", () => {
  const legacy = JSON.stringify({ version: 1, user: "u-9", name: "Old" });
  assert.equal(decodeUser(legacy).name, "Old");
});

test("unsupported versions are rejected", () => {
  assert.throws(() => decodeUser(JSON.stringify({ version: 3 })), /unsupported version/);
});
