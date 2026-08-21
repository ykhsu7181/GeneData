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
  assert.match(pageSource, /Accession\s*·/);
  assert.match(pageSource, /样本数/);
  assert.match(pageSource, /数据集数/);
  assert.match(pageSource, /组装版本/);
  assert.match(pageSource, /数据集/);
  assert.match(pageSource, /样本/);
  assert.match(pageSource, /<th>参考基因组<\/th>/);
  assert.match(pageSource, /相关文件/);
  assert.match(pageSource, /关系概览/);
  assert.match(pageSource, /地理信息/);
  assert.match(pageSource, /描述/);
  assert.match(pageSource, /返回品种信息/);
  assert.match(pageSource, /name:\s*'accession-card'/);
  assert.match(pageSource, /accessions\/\$\{encodeURIComponent\(routeAccession\.value\)\}\/summary/);
  assert.match(pageSource, /accessions\/\$\{encodeURIComponent\(routeAccession\.value\)\}\/\$\{tab\}/);
  assert.match(pageSource, /datafile_download_url/);
  assert.doesNotMatch(pageSource, /genome-files/);
  assert.doesNotMatch(pageSource, /Back to Accession Card|返回列表/);
  assert.doesNotMatch(pageSource, /创建与更新信息/);
});
