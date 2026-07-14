import assert from "node:assert/strict";
import test from "node:test";

const adapters = [
  "alpha",
  "bravo",
  "charlie",
  "delta",
  "echo",
  "foxtrot",
  "golf",
  "hotel",
  "india",
  "juliet",
  "kilo",
  "lima",
];

for (const adapter of adapters) {
  test(`${adapter} normalizes the stable record contract`, async () => {
    const { normalize } = await import(`../src/adapters/${adapter}.js`);
    const source = {
      label: "  Example  ",
      enabled: "true",
      source: adapter,
    };

    assert.deepEqual(normalize(source), {
      label: "Example",
      enabled: true,
      source: adapter,
    });
    assert.equal(source.label, "  Example  ");
    assert.equal(normalize({ ...source, enabled: false }).enabled, false);
  });
}
