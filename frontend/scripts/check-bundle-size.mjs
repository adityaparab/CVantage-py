// Performance budget (issue #94): the initial entry chunk must stay under the
// gzipped JS budget. Run after `pnpm build`. Fails CI when the budget is blown.
import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { gzipSync } from "node:zlib";

const BUDGET_KB = 250;
const ASSETS_DIR = "dist/assets";

let entries;
try {
  entries = readdirSync(ASSETS_DIR);
} catch {
  console.error(`No build output at ${ASSETS_DIR}. Run \`pnpm build\` first.`);
  process.exit(1);
}

const entry = entries.find((f) => /^index-.*\.js$/.test(f));
if (!entry) {
  console.error("Could not find the entry chunk (index-*.js) in the build output.");
  process.exit(1);
}

const gzippedKb = gzipSync(readFileSync(path.join(ASSETS_DIR, entry))).length / 1024;
console.log(`Entry ${entry}: ${gzippedKb.toFixed(1)} KB gzipped (budget ${BUDGET_KB} KB)`);

if (gzippedKb > BUDGET_KB) {
  console.error(`FAIL: entry bundle is ${(gzippedKb - BUDGET_KB).toFixed(1)} KB over budget.`);
  process.exit(1);
}
console.log("OK: within the performance budget.");
