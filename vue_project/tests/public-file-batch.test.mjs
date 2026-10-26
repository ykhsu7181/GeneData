import assert from 'node:assert/strict'
import test from 'node:test'

import {
  buildFilteredManifestUrl,
  buildPublicFileArchiveScript,
  buildPublicFileBatchScript,
  buildPublicFileCacheScript,
  expandDownloadFiles,
} from '../src/utils/publicFileBatch.mjs'

const sha = character => character.repeat(64)
const genome = {
  file_code: 'FILE000957',
  file_name: "genome.O'Brien.fasta",
  sha256: sha('a'),
  content_url: '/gd/api/v1/files/FILE000957/content/',
  companions: [{
    type: 'fai',
    file_code: 'FILE003921',
    file_name: "genome.O'Brien.fasta.fai",
    sha256: sha('b'),
    content_url: '/gd/api/v1/files/FILE003921/content/',
  }],
}

test('expands authorized companions once and can exclude them', () => {
  assert.deepEqual(
    expandDownloadFiles([genome, genome]).map(item => item.fileCode),
    ['FILE000957', 'FILE003921'],
  )
  assert.deepEqual(
    expandDownloadFiles([genome], { includeCompanions: false }).map(item => item.fileCode),
    ['FILE000957'],
  )
})

test('builds a resumable verified cache script without embedding a token', () => {
  const script = buildPublicFileCacheScript([genome], {
    baseUrl: 'https://genedata.example/gd/',
  })

  assert.match(script, /GENEDATA_TOKEN:\?Please export GENEDATA_TOKEN first/)
  assert.match(script, /GENEDATA_CACHE_DIR/)
  assert.match(script, /--continue-at -/)
  assert.match(script, /sha256sum -c -/)
  assert.match(script, /mv -f "\$partial" "\$target"/)
  assert.match(script, /FILE000957/)
  assert.match(script, /FILE003921/)
  assert.match(script, /O'"'"'Brien/, 'single quotes in file names are shell escaped')
  assert.doesNotMatch(script, /Bearer [A-Za-z0-9_-]{10,}/)
})

test('builds a filtered manifest link and omits empty filters', () => {
  assert.equal(
    buildFilteredManifestUrl(
      '/gd/api/v1/files/manifest.tsv',
      { accession: 'IR64', role: 'genome_fasta', dataset: '' },
      'https://genedata.example/public-files',
    ),
    '/gd/api/v1/files/manifest.tsv?accession=IR64&role=genome_fasta',
  )
})

test('rejects cross-origin content URLs before adding the bearer token', () => {
  assert.throws(
    () => buildPublicFileCacheScript([{
      ...genome,
      content_url: 'https://attacker.example/collect',
      companions: [],
    }], { baseUrl: 'https://genedata.example/' }),
    /Cross-origin content URL rejected/,
  )
})

test('builds a strict immutable batch workflow without embedding a token', () => {
  const script = buildPublicFileBatchScript([genome], {
    baseUrl: 'https://genedata.example/public-files',
  })

  assert.match(script, /batch:create and batch:read scopes/)
  assert.match(script, /\/gd\/api\/v1\/file-batches\//)
  assert.match(script, /"strict":true/)
  assert.match(script, /FILE000957/)
  assert.match(script, /FILE003921/)
  assert.match(script, /manifest_tsv_url/)
  assert.match(script, /GENEDATA_IDEMPOTENCY_KEY/)
  assert.doesNotMatch(script, /Bearer [A-Za-z0-9_-]{10,}/)
})

test('builds a bounded archive queue, poll, download and verification workflow', () => {
  const script = buildPublicFileArchiveScript([genome], {
    baseUrl: 'https://genedata.example/public-files',
  })

  assert.match(script, /batch:create, batch:read, batch:archive and batch:download scopes/)
  assert.match(script, /file-batches\/\$BATCH_ID\/archives\//)
  assert.match(script, /queued\|running/)
  assert.match(script, /GENEDATA_ARCHIVE_MAX_POLLS/)
  assert.match(script, /--continue-at -/)
  assert.match(script, /sha256sum -c -/)
  assert.match(script, /mv -f "\$ARCHIVE_PART" "\$ARCHIVE_FILE"/)
  assert.match(script, /FILE000957/)
  assert.match(script, /FILE003921/)
  assert.doesNotMatch(script, /Bearer [A-Za-z0-9_-]{10,}/)
})
