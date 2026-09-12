import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const source = readFileSync(resolve(process.cwd(), 'src/views/AnnotationView.vue'), 'utf8')

assert.match(
  source,
  /await replaceRouteQuery\(buildNormalizedQuery\(\{\s*accession: value\s*\}\)\);\s*await handleRouteParams\(\);/,
  'Annotation accession selection should immediately resolve hierarchy and load annotation data'
)

console.log('annotation accession context sync source checks passed')
