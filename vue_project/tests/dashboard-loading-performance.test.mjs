import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const currentDir = path.dirname(fileURLToPath(import.meta.url));
const readSource = (relativePath) => fs.readFileSync(
  path.resolve(currentDir, relativePath),
  'utf8'
);

const dashboardSource = readSource('../src/views/DashboardHomeView.vue');
const publicIndexSource = readSource('../public/index.html');

test('portal dashboard keeps search available while featured data loads', () => {
  assert.match(dashboardSource, /<HomeHero @search="handleSearch"/);
  assert.match(dashboardSource, /:loading="isLoading"/);
  assert.match(dashboardSource, /:error="loadError"/);
  assert.doesNotMatch(dashboardSource, /v-if="isLoading"[\s\S]*?<HomeHero/);
});

test('portal dashboard does not import chart or map modules', () => {
  assert.doesNotMatch(dashboardSource, /DistributionPanel|GeoMapPanel|IntersectionObserver/);
  assert.doesNotMatch(dashboardSource, /dashboardPieCharts|dashboardMapCharts|worldMapData/);
});

test('portal entry does not load ECharts from a public CDN', () => {
  assert.doesNotMatch(publicIndexSource, /cdn\.jsdelivr\.net\/npm\/echarts|echarts\.min\.js/);
});
