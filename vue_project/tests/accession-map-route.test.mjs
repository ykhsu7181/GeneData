import assert from 'node:assert/strict'
import test from 'node:test'

import {
  normalizeAccessionMapReturnPath,
  parseAccessionMapQuery,
  serializeAccessionMapQuery
} from '../src/services/accessionMapRoute.mjs'

test('map query parsing accepts the legacy organism alias and canonicalizes filters', () => {
  assert.deepEqual(parseAccessionMapQuery({
    organism: ' IR64 ',
    region: ' China ',
    sub_population: 'XI,GJ,XI'
  }), {
    accession: 'IR64',
    region: 'China',
    subPopulations: ['GJ', 'XI']
  })
  assert.deepEqual(serializeAccessionMapQuery({
    accession: ' IR64 ',
    region: '',
    subPopulations: ['XI', 'GJ', 'XI']
  }), {
    accession: 'IR64',
    sub_population: 'GJ,XI'
  })
})

test('map return path only accepts the internal accession map route', () => {
  assert.equal(
    normalizeAccessionMapReturnPath('/accession-map?region=China&sub_population=XI'),
    '/accession-map?region=China&sub_population=XI'
  )
  assert.equal(normalizeAccessionMapReturnPath('/accession-card'), '')
  assert.equal(normalizeAccessionMapReturnPath('//evil.example/accession-map'), '')
  assert.equal(normalizeAccessionMapReturnPath('https://evil.example/accession-map'), '')
  assert.equal(normalizeAccessionMapReturnPath('/accession-map-evil'), '')
})
