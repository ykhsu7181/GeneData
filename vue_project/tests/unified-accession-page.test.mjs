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
  assert.match(pageSource, /<div class="page-heading">[\s\S]*?<nav class="accession-breadcrumb"/);
  assert.match(pageSource, /<router-link :to="\{ name: 'dashboard-home' \}">/);
  assert.doesNotMatch(pageSource, /class="context-back"|parentReturnLabel/);
  assert.match(pageSource, /<router-link :to="parentLocation">/);
  assert.match(pageSource, /normalizeAccessionMapReturnPath\(route\.query\.return_to\)/);
  assert.match(pageSource, /<div class="heading-row">/);
  assert.match(pageSource, /page\.accessionDetail\.searchPlaceholder/);
  assert.match(pageSource, /type="search"/);
  assert.match(pageSource, /const submitSearch = async/);
  assert.match(pageSource, /page\.accessionDetail\.tabs\.datasets/);
  assert.match(pageSource, /page\.accessionDetail\.tabs\.samples/);
  assert.match(pageSource, /page\.accessionDetail\.assemblyInformation/);
  assert.match(pageSource, /relationship\.assemblies/);
  assert.match(pageSource, /import AssemblyVersionTable from '@\/components\/accession\/AssemblyVersionTable\.vue'/);
  assert.match(pageSource, /<AssemblyVersionTable[\s\S]*?:rows="relationship\.assemblies \|\| \[\]"/);
  assert.match(pageSource, /:action-label="\$t\('page\.accessionDetail\.viewGenome'\)"/);
  assert.match(pageSource, /@select="openAssembly"/);
  assert.match(pageSource, /query = \{ from: 'accession' \}/);
  assert.match(pageSource, /router\.push\(\{ name: 'assembly-detail', params: \{ assemblyId: assembly\.id \}, query \}\)/);
  assert.match(pageSource, /import AnnotationVersionTable from '@\/components\/accession\/AnnotationVersionTable\.vue'/);
  assert.match(pageSource, /<AnnotationVersionTable[\s\S]*?:rows="tabRows"/);
  assert.match(pageSource, /@view-files="openFiles\('annotation', \$event\.id\)"/);
  assert.match(pageSource, /page\.accessionDetail\.tabs\.files/);
  assert.match(pageSource, /page\.accessionDetail\.relationship/);
  assert.match(pageSource, /page\.accessionDetail\.geography/);
  assert.match(pageSource, /<CompactAccessionMap/);
  assert.match(pageSource, /:latitude="geography\.latitude"/);
  assert.match(pageSource, /:longitude="geography\.longitude"/);
  assert.match(pageSource, /page\.accessionDetail\.fields\.description/);
  assert.match(pageSource, /labelKey:\s*'page\.accessionDetail\.tabs\./);
  assert.match(pageSource, /accessions\/\$\{encodeURIComponent\(requestedAccession\)\}\/summary/);
  assert.match(pageSource, /accessions\/\$\{encodeURIComponent\(routeAccession\.value\)\}\/\$\{tab\}/);
  assert.match(pageSource, /datafile_download_url/);
  assert.doesNotMatch(pageSource, /page\.accessionDetail\.tabs\.assemblies/);
  assert.doesNotMatch(pageSource, /summary-grid|summaryCards/);
  assert.doesNotMatch(pageSource, /genome-files/);
  assert.doesNotMatch(pageSource, /v-for="item in relationship\.assemblies/);
  assert.doesNotMatch(pageSource, /Back to Accession Card|返回列表|创建与更新信息/);
});
