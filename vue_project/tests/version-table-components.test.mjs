import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const currentDir = path.dirname(fileURLToPath(import.meta.url));
const assemblySource = fs.readFileSync(
  path.resolve(currentDir, '../src/components/accession/AssemblyVersionTable.vue'),
  'utf8'
);
const annotationSource = fs.readFileSync(
  path.resolve(currentDir, '../src/components/accession/AnnotationVersionTable.vue'),
  'utf8'
);

test('assembly version table exposes accession and revision modes', () => {
  assert.match(assemblySource, /name:\s*'AssemblyVersionTable'/);
  assert.match(assemblySource, /rows:\s*\{\s*type:\s*Array/);
  assert.match(assemblySource, /currentAssemblyId:\s*\{\s*type:\s*\[Number, String\]/);
  assert.match(assemblySource, /validator:\s*\(value\)\s*=>\s*\['accession', 'revision'\]\.includes\(value\)/);
  assert.match(assemblySource, /showActions:\s*\{\s*type:\s*Boolean/);
  assert.match(assemblySource, /emits:\s*\['select'\]/);
  assert.match(assemblySource, /item\.display_name \|\| item\.assembly_name \|\| item\.name \|\| '-'/);
  assert.match(assemblySource, /item\.assembly_accession \|\| item\.standard_id \|\| '-'/);
  assert.match(assemblySource, /class="assembly-name-action"[\s\S]*?@click="selectAssembly\(item\)"/);
  assert.match(assemblySource, /this\.\$emit\('select', item\)/);
  assert.match(assemblySource, /class="current-badge"/);
  assert.match(assemblySource, /v-if="!rows\.length"/);
});

test('annotation version table supports assembly and default columns', () => {
  assert.match(annotationSource, /name:\s*'AnnotationVersionTable'/);
  assert.match(annotationSource, /rows:\s*\{\s*type:\s*Array/);
  assert.match(annotationSource, /showAssembly:\s*\{\s*type:\s*Boolean/);
  assert.match(annotationSource, /showDefault:\s*\{\s*type:\s*Boolean/);
  assert.match(annotationSource, /showActions:\s*\{\s*type:\s*Boolean/);
  assert.match(annotationSource, /emits:\s*\['view-files'\]/);
  assert.match(annotationSource, /item\.standard_id \|\| item\.annotation_code \|\| '-'/);
  assert.match(annotationSource, /item\.source_name \|\| item\.source_database \|\| '-'/);
  assert.match(annotationSource, /item\.is_default \? defaultYesLabel : defaultNoLabel/);
  assert.match(annotationSource, /columnCount\(\)/);
  assert.match(annotationSource, /v-if="!rows\.length"/);
});

test('version table components stay presentation-only', () => {
  for (const source of [assemblySource, annotationSource]) {
    assert.doesNotMatch(source, /axios|useRoute|useRouter|window\.open/);
  }
});
