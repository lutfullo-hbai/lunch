import assert from "node:assert/strict";
import { test } from "node:test";

import { niceMax } from "../assets/js/bar-chart.js";

test("axis max is a round number just above the tallest bar", () => {
  assert.equal(niceMax(135000), 150000); // 0 / 50 ming / 100 ming / 150 ming
  assert.equal(niceMax(90000), 90000); // 0 / 30 ming / 60 ming / 90 ming
  assert.equal(niceMax(407000), 450000);
  assert.equal(niceMax(5000), 6000);
});

test("empty chart still has a scale", () => {
  assert.equal(niceMax(0), 3);
});
