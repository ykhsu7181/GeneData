import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const currentDir = path.dirname(fileURLToPath(import.meta.url));
const sourcePath = path.resolve(currentDir, '../src/views/AccessionCard.vue');
const source = fs.readFileSync(sourcePath, 'utf8');

test('accession card is retained only as the accession search entry', () => {
  assert.match(source, /accession-workbench/);
  assert.match(source, /请选择一个 accession 查看详情/);
  assert.match(source, /name:\s*'accession-card'/);
  assert.match(source, /<AccessionDetailTableView v-if="routeAccession" embedded/);
  assert.doesNotMatch(source, /Accession overview/);
  assert.doesNotMatch(source, /goToDetailTable/);
  assert.doesNotMatch(source, />Current Modules</);
  assert.doesNotMatch(source, />Assemblies</);
});

test('accession card no longer contains resource-card or hierarchy-graph implementations', () => {
  assert.doesNotMatch(source, /class="resource-grid"/);
  assert.doesNotMatch(source, /class="hierarchy-graph"/);
  assert.doesNotMatch(source, /const resourceCards = computed/);
  assert.doesNotMatch(source, /const updateHierarchyLines =/);
});
