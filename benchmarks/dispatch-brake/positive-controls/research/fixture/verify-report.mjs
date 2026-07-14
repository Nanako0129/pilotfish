import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const report = readFileSync(new URL("./REPORT.md", import.meta.url), "utf8");
const lower = report.toLowerCase();

for (const term of [
  "surface-a",
  "surface-b",
  "scout",
  "executor",
  "verifier",
  "model",
  "background",
  "dispatch",
]) {
  assert.ok(lower.includes(term), `REPORT.md is missing ${term}`);
}

assert.match(report, /surface-a\/[^\s:]+:\d+/);
assert.match(report, /surface-b\/[^\s:]+:\d+/);

console.log("REPORT.md covers both independent surfaces with file:line evidence");
