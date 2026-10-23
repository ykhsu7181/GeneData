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
  assert.match(source, /<template v-if="!routeAccession">/);
  assert.match(source, /<AccessionPortalHeader/);
  assert.match(source, /<AccessionSearchPanel @select="openAccession"/);
  assert.match(source, /<AccessionDetailTableView v-else embedded/);
  assert.doesNotMatch(source, /page-kicker">\s*ACCESSION\s*</);
  assert.doesNotMatch(source, /\/files\/accessions\//);
  assert.doesNotMatch(source, /accessionDetail/);
  assert.doesNotMatch(source, /localStorage/);
});

test('selecting an accession keeps the canonical page and expands inline details', () => {
  assert.match(source, /name:\s*'accession-card'/);
  assert.match(source, /accession:\s*normalizedAccession/);
  assert.match(source, /delete query\.organism/);
  assert.match(source, /<AccessionDetailTableView v-else embedded/);
});
