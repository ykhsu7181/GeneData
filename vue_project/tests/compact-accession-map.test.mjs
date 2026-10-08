import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const currentDir = path.dirname(fileURLToPath(import.meta.url));
const source = fs.readFileSync(
  path.resolve(currentDir, '../src/components/accession/CompactAccessionMap.vue'),
  'utf8'
);

test('compact accession map renders the summary coordinates on the existing world map', () => {
  assert.match(source, /import \* as echarts from 'echarts'/);
  assert.match(source, /worldMapData/);
  assert.match(source, /echarts\.registerMap\('world'/);
  assert.match(source, /coordinateSystem:\s*'geo'/);
  assert.match(source, /value:\s*\[longitude, latitude\]/);
  assert.match(source, /type:\s*'effectScatter'/);
});

test('compact accession map resizes and disposes its chart instance', () => {
  assert.match(source, /window\.addEventListener\('resize', resizeMap\)/);
  assert.match(source, /window\.removeEventListener\('resize', resizeMap\)/);
  assert.match(source, /mapInstance\?\.dispose\(\)/);
});
