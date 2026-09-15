import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const currentDir = path.dirname(fileURLToPath(import.meta.url));
const routerSource = fs.readFileSync(
  path.resolve(currentDir, '../src/router/index.js'),
  'utf8'
);
const pageSource = fs.readFileSync(
  path.resolve(currentDir, '../src/views/AccessionDetailTableView.vue'),
  'utf8'
);

test('accession search and detail routes render their dedicated pages', () => {
  assert.match(
    routerSource,
    /path:\s*'\/accession-card'[\s\S]*?component:\s*\(\)\s*=>\s*import\('\.\.\/views\/AccessionCard\.vue'\)/
  );
  assert.match(
    routerSource,
    /path:\s*'\/accession-detail'[\s\S]*?component:\s*\(\)\s*=>\s*import\('\.\.\/views\/AccessionDetailTableView\.vue'\)/
  );
});

test('unified accession page follows the approved information architecture', () => {
  assert.match(pageSource, /page\.accessionDetail\.title/);
  assert.match(pageSource, /page\.accessionDetail\.summary\.samples/);
  assert.match(pageSource, /page\.accessionDetail\.summary\.datasets/);
  assert.match(pageSource, /page\.accessionDetail\.tabs\.assemblies/);
  assert.match(pageSource, /page\.accessionDetail\.tabs\.datasets/);
  assert.match(pageSource, /page\.accessionDetail\.tabs\.samples/);
  assert.match(pageSource, /page\.accessionDetail\.columns\.referenceGenome/);
  assert.match(pageSource, /page\.accessionDetail\.tabs\.files/);
  assert.match(pageSource, /page\.accessionDetail\.relationship/);
  assert.match(pageSource, /page\.accessionDetail\.geography/);
  assert.match(pageSource, /page\.accessionDetail\.fields\.description/);
  assert.match(pageSource, /page\.accessionDetail\.backToSearch/);
  assert.match(pageSource, /labelKey:\s*'page\.accessionDetail\.tabs\./);
  assert.match(pageSource, /name:\s*'accession-card'/);
  assert.match(pageSource, /accessions\/\$\{encodeURIComponent\(routeAccession\.value\)\}\/summary/);
  assert.match(pageSource, /accessions\/\$\{encodeURIComponent\(routeAccession\.value\)\}\/\$\{tab\}/);
  assert.match(pageSource, /datafile_download_url/);
  assert.doesNotMatch(pageSource, /genome-files/);
  assert.doesNotMatch(pageSource, /Back to Accession Card|返回列表|创建与更新信息/);
});
