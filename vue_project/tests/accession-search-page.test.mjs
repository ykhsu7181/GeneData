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
  assert.match(source, /page\.accessionCard\.searchPlaceholder/);
  assert.match(source, /\/files\/query\/organisms\//);
  assert.match(source, /<el-empty[^>]+description=/);
  assert.doesNotMatch(source, /\/files\/accessions\//);
  assert.doesNotMatch(source, /accessionDetail/);
});

test('selecting an accession opens the dedicated detail route', () => {
  assert.match(source, /name:\s*'accession-detail'/);
  assert.match(source, /query:\s*\{\s*accession\s*\}/);
  assert.match(source, /handleSearchVisibleChange/);
  assert.match(source, /fetchOrganisms\(''\)/);
});
