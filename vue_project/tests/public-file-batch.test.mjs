import assert from 'node:assert/strict'
import test from 'node:test'

import {
  buildFilteredManifestUrl,
  buildPublicFileArchiveScript,
  buildPublicFileBatchScript,
  buildPublicFileCacheScript,
  buildSelectedFilesTsv,
  expandDownloadFiles,
  resolveDownloadSelection,
} from '../src/utils/publicFileBatch.mjs'

const sha = character => character.repeat(64)
const genome = {
  file_code: 'FILE000957',
  file_name: "genome.O'Brien.fasta",
  sha256: sha('a'),
  content_url: '/gd/api/v1/files/FILE000957/content/',
  accessions: ['IR64'],
  assemblies: ['ASM_IR64'],
  datasets: ['DS_IR64'],
  roles: ['genome_fasta'],
  format: 'FASTA',
  size: 100,
  companions: [{
    type: 'fai',
    file_code: 'FILE003921',
    file_name: "genome.O'Brien.fasta.fai",
    sha256: sha('b'),
    size: 20,
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

test('builds a selected TSV with a fixed contract, stable order, and explicit companion', () => {
  const manifest = buildSelectedFilesTsv([genome], {
    baseUrl: 'https://genedata.example/public-files',
  })
  const lines = manifest.content.trimEnd().split('\n')

  assert.equal(lines[0], 'file_code\tfile_name\taccession\tassembly\tdataset\trole\tformat\tsize\tsha256\tcontent_url')
  assert.match(lines[1], /^FILE000957\tgenome\.O'Brien\.fasta\tIR64\tASM_IR64\tDS_IR64\tgenome_fasta\tFASTA\t100\t/)
  assert.match(lines[2], /^FILE003921\tgenome\.O'Brien\.fasta\.fai\t\t\t\t\tFAI\t20\t/)
  assert.equal(manifest.fileCount, 2)
  assert.equal(manifest.totalSize, 120)
  assert.deepEqual(manifest.warnings, [])
})

test('selected TSV de-duplicates file codes and prevents spreadsheet formulas', () => {
  const manifest = buildSelectedFilesTsv([{ ...genome, file_name: '=CMD()', companions: [] }, genome], {
    baseUrl: 'https://genedata.example/',
    includeCompanions: false,
  })

  assert.equal(manifest.fileCount, 1)
  assert.match(manifest.content, /FILE000957\t'=CMD\(\)/)
})

test('missing FAI warns while ambiguous FAI blocks selected output and scripts', () => {
  const missing = resolveDownloadSelection([{ ...genome, companions: [] }])
  assert.equal(missing.warnings.length, 1)
  assert.equal(missing.errors.length, 0)

  const ambiguous = {
    ...genome,
    companions: [genome.companions[0], { ...genome.companions[0], file_code: 'FILE003922' }],
  }
  assert.equal(resolveDownloadSelection([ambiguous]).errors.length, 1)
  assert.throws(
    () => buildSelectedFilesTsv([ambiguous], { baseUrl: 'https://genedata.example/' }),
    /Ambiguous FAI companions/,
  )
  assert.throws(
    () => buildPublicFileBatchScript([ambiguous], { baseUrl: 'https://genedata.example/' }),
    /Ambiguous FAI companions/,
  )
})

test('selected TSV rejects cross-origin content URLs', () => {
  assert.throws(
    () => buildSelectedFilesTsv([{
      ...genome,
      content_url: 'https://attacker.example/collect',
      companions: [],
    }], { baseUrl: 'https://genedata.example/' }),
    /Cross-origin content URL rejected/,
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
