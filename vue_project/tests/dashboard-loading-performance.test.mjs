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
const distributionSource = readSource('../src/components/DistributionPanel.vue');
const geoMapSource = readSource('../src/components/GeoMapPanel.vue');
const publicIndexSource = readSource('../public/index.html');

test('dashboard does not render empty data panels while loading', () => {
  assert.match(dashboardSource, /<template v-if="isLoading">/);
  assert.match(dashboardSource, /<template v-else>/);
  assert.doesNotMatch(dashboardSource, /<section v-if="isLoading" class="dashboard-skeleton-grid/);
});

test('dashboard charts are loaded lazily instead of blocking route navigation', () => {
  assert.doesNotMatch(publicIndexSource, /cdn\.jsdelivr\.net\/npm\/echarts|echarts\.min\.js/);
  assert.doesNotMatch(distributionSource, /import \* as echarts from 'echarts'/);
  assert.doesNotMatch(geoMapSource, /import \* as echarts from 'echarts'/);
  assert.match(distributionSource, /import\('@\/utils\/dashboardPieCharts'\)/);
  assert.match(geoMapSource, /import\('@\/utils\/dashboardMapCharts'\)/);
  assert.match(geoMapSource, /import\('@\/data\/worldMapData\.js'\)/);
});

test('map resize does not rebuild the full map option', () => {
  const resizeFunction = geoMapSource.match(
    /const resizeMap = \(\) => \{([\s\S]*?)\n    \}/
  );
  assert.ok(resizeFunction);
  assert.match(resizeFunction[1], /mapInstance\.value\.resize\(\)/);
  assert.doesNotMatch(resizeFunction[1], /renderMap\(\)/);
});
