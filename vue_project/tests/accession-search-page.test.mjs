import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const currentDir = path.dirname(fileURLToPath(import.meta.url));
const source = fs.readFileSync(
  path.resolve(currentDir, '../src/views/AccessionCard.vue'),
  'utf8'
);

test('accession card is a searchable landing page', () => {
  assert.match(source, /v-model="selectedAccession"/);
  assert.match(source, /搜索 Accession \/ 品种 \/ 亚群/);
  assert.match(source, /\/files\/query\/organisms\//);
  assert.match(source, /<el-empty[^>]+description=/);
  assert.match(source, /<AccessionDetailTableView v-if="routeAccession" embedded/);
  assert.doesNotMatch(source, /page-kicker">\s*ACCESSION\s*</);
  assert.doesNotMatch(source, /\/files\/accessions\//);
  assert.doesNotMatch(source, /accessionDetail/);
});

test('selecting an accession keeps the canonical page and expands inline details', () => {
  assert.match(source, /name:\s*'accession-card'/);
  assert.match(source, /accession:\s*normalizedAccession/);
  assert.match(source, /handleSearchVisibleChange/);
  assert.match(source, /fetchAccessions\(''\)/);
});
