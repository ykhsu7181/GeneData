import test from 'node:test'
import assert from 'node:assert/strict'
import { getTopNavActiveGroup, isTopNavGroupActive, normalizeTopNavPath, topNavGroups } from '../src/config/topNavConfig.mjs'

test('normalizeTopNavPath aliases legacy detail and card routes', () => {
  assert.equal(normalizeTopNavPath('/'), '/dashboard')
  assert.equal(normalizeTopNavPath('/annotation-card'), '/annotation')
  assert.equal(normalizeTopNavPath('/core-variable-blocks-card'), '/core-variable-blocks')
  assert.equal(normalizeTopNavPath('/accession-detail'), '/accession-card')
})

test('getTopNavActiveGroup maps data routes to data overview group', () => {
  assert.equal(getTopNavActiveGroup('/data-overview'), 'dataOverview')
  assert.equal(getTopNavActiveGroup('/genome-card'), 'dataOverview')
  assert.equal(getTopNavActiveGroup('/annotation-card'), 'dataOverview')
  assert.equal(getTopNavActiveGroup('/transcriptome-overview'), 'dataOverview')
})

test('getTopNavActiveGroup maps tools routes to tools group', () => {
  assert.equal(getTopNavActiveGroup('/core-variable-blocks'), 'tools')
  assert.equal(getTopNavActiveGroup('/codon-card'), 'tools')
  assert.equal(getTopNavActiveGroup('/tools/codonw'), 'tools')
})

test('isTopNavGroupActive only marks the owning group active', () => {
  assert.equal(isTopNavGroupActive('accession', '/accession-detail'), true)
  assert.equal(isTopNavGroupActive('tools', '/annotation'), false)
})

test('topNavGroups keeps agreed secondary navigation structure', () => {
  assert.equal(topNavGroups.dataOverview.labelKey, 'nav.dataResources')
  assert.equal(topNavGroups.dataOverview.path, '/data-overview')
  assert.deepEqual(
    topNavGroups.dataOverview.children.map((item) => [item.labelKey, item.path]),
    [
      ['nav.rawData', '/raw-data'],
      ['nav.dataOverview', '/data-overview'],
      ['nav.genome', '/genome-card'],
      ['nav.annotation', '/annotation'],
      ['nav.transcriptomeOverview', '/transcriptome-overview']
    ]
  )
  assert.deepEqual(
    topNavGroups.tools.children.map((item) => item.path),
    ['/core-variable-blocks', '/codon-card', '/tools/codonw']
  )
})
