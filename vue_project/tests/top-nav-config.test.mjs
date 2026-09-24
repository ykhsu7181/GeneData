import test from 'node:test'
import assert from 'node:assert/strict'
import { getTopNavActiveGroup, isTopNavGroupActive, normalizeTopNavPath, topNavItems } from '../src/config/topNavConfig.mjs'

test('top navigation exposes the agreed five first-level entries in order', () => {
  assert.deepEqual(
    topNavItems.map((item) => [item.key, item.path]),
    [
      ['home', '/dashboard'],
      ['accession', '/accession-card'],
      ['assembly', '/assembly'],
      ['data', '/data-overview'],
      ['more', undefined]
    ]
  )
})

test('Data and More contain only the agreed secondary entries', () => {
  const data = topNavItems.find((item) => item.key === 'data')
  const more = topNavItems.find((item) => item.key === 'more')

  assert.deepEqual(data.children.map((item) => [item.labelKey, item.path]), [
    ['nav.dataOverview', '/data-overview'],
    ['nav.researchGroupRawData', '/raw-data']
  ])
  assert.deepEqual(more.children.map((item) => [item.labelKey, item.path]), [
    ['nav.annotation', '/annotation'],
    ['nav.transcriptomeOverview', '/transcriptome-overview']
  ])
})

test('normalizeTopNavPath aliases legacy detail and card routes', () => {
  assert.equal(normalizeTopNavPath('/'), '/dashboard')
  assert.equal(normalizeTopNavPath('/annotation-card'), '/annotation')
  assert.equal(normalizeTopNavPath('/core-variable-blocks-card'), '/core-variable-blocks')
  assert.equal(normalizeTopNavPath('/accession-detail'), '/accession-card')
})

test('active group mapping covers visible navigation destinations', () => {
  const cases = {
    '/dashboard': 'home',
    '/accession-card': 'accession',
    '/accession-detail': 'accession',
    '/accession-map': 'accession',
    '/assembly': 'assembly',
    '/data': 'data',
    '/data-chart': 'data',
    '/data-overview': 'data',
    '/raw-data': 'data',
    '/genome-card': null,
    '/annotation': 'more',
    '/annotation-card': 'more',
    '/transcriptome': 'more',
    '/transcriptome-overview': 'more'
  }

  Object.entries(cases).forEach(([path, group]) => assert.equal(getTopNavActiveGroup(path), group))
})

test('hidden tools and placeholder routes do not activate a first-level entry', () => {
  assert.equal(getTopNavActiveGroup('/core-variable-blocks'), null)
  assert.equal(getTopNavActiveGroup('/codon-card'), null)
  assert.equal(getTopNavActiveGroup('/tools/codonw'), null)
  assert.equal(getTopNavActiveGroup('/placeholder'), null)
  assert.equal(isTopNavGroupActive('more', '/codon-card'), false)
})
