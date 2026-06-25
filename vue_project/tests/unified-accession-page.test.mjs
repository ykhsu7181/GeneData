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
    /path:\s*'\/accession-card'[\s\S]*?beforeEnter:\s*\(to\)\s*=>[\s\S]*?name:\s*'accession-detail'/
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
  assert.match(pageSource, /Annotation\s*\/\s*注释版本/);
  assert.match(pageSource, /相关文件/);
  assert.match(pageSource, /关系概览/);
  assert.match(pageSource, /创建与更新信息/);
  assert.match(pageSource, /描述/);
  assert.doesNotMatch(pageSource, /Back to Accession Card|返回列表/);
  assert.doesNotMatch(pageSource, /expandedAssemblies|expandedAnnotations/);
  assert.doesNotMatch(pageSource, /assemblyEntries|annotationEntries/);
});
