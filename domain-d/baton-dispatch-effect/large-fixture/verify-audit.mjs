import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const report = readFileSync(new URL("./AUDIT.md", import.meta.url), "utf8");
const lower = report.toLowerCase();

for (const domain of ["domain-a", "domain-b", "domain-c", "domain-d"]) {
  assert.ok(lower.includes(domain), `AUDIT.md is missing ${domain}`);
  assert.match(
    report,
    new RegExp(`${domain}/[^\\s:]+:\\d+`, "i"),
    `AUDIT.md is missing file:line evidence for ${domain}`,
  );
}

for (const term of [
  "version",
  "provenance",
  "runtime",
  "test",
  "contradiction",
]) {
  assert.ok(lower.includes(term), `AUDIT.md is missing ${term}`);
}

console.log("AUDIT.md covers all four domains with file:line evidence");
