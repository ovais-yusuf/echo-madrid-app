import test from "node:test";
import assert from "node:assert/strict";
import {simulateTable} from "../lib/simulator.ts";
const rows = [1,2,3].map(id => ({position:id,team:{id,name:`Club ${id}`},played:1,won:0,drawn:1,lost:0,points:1,goals_for:0,goals_against:0}));
test("simulator adds one game and never mutates official rows", () => {
  const before = structuredClone(rows);
  const result = simulateTable(rows,2,1,3,0);
  assert.deepEqual(rows,before);
  assert.equal(result[0].team.id,2);
  assert.equal(result[0].points,4);
  assert.equal(result[0].won,1);
  assert.equal(result.find(r => r.team.id===1).lost,1);
  assert.equal(result.find(r => r.team.id===3).played,1);
});
test("draw awards one point to each club", () => {
  const result=simulateTable(rows,1,2,2,2);
  assert.equal(result[0].points,2);
  assert.equal(result[1].points,2);
  assert.equal(result[0].drawn,2);
});
test("invalid clubs and scores are rejected", () => {
  for (const args of [[1,1,0,0],[1,99,0,0],[1,2,-1,0],[1,2,1.5,0],[1,2,NaN,0]]) {
    assert.throws(() => simulateTable(rows,...args));
  }
});
