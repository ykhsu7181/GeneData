const normalizedText = value => String(value ?? '').trim()

const safePathSegment = value => {
  const normalized = normalizedText(value)
    .replace(/[\\/]+/g, '_')
    .split('')
    .map(character => {
      const code = character.charCodeAt(0)
      return code < 32 || code === 127 ? '_' : character
    })
    .join('')
    .replace(/^\.+$/, '_')
  return normalized || 'unnamed'
}

const shellQuote = value => `'${String(value ?? '').replace(/'/g, `'"'"'`)}'`

const downloadItem = item => {
  const fileCode = normalizedText(item?.file_code)
  const fileName = normalizedText(item?.file_name)
  const sha256 = normalizedText(item?.sha256).toLowerCase()
  const contentUrl = normalizedText(item?.content_url)
  if (!fileCode || !fileName || !/^[0-9a-f]{64}$/.test(sha256) || !contentUrl) return null
  const size = Number(item?.size)
  return { fileCode, fileName, sha256, contentUrl, size: Number.isFinite(size) ? size : 0 }
}

export const expandDownloadFiles = (rows, { includeCompanions = true } = {}) => {
  const files = new Map()
  for (const row of rows || []) {
    const candidates = includeCompanions ? [row, ...(row?.companions || [])] : [row]
    for (const candidate of candidates) {
      const item = downloadItem(candidate)
      if (item && !files.has(item.fileCode)) files.set(item.fileCode, item)
    }
  }
  return [...files.values()]
}

export const buildPublicFileCacheScript = (
  rows,
  { baseUrl, includeCompanions = true } = {},
) => {
  const files = expandDownloadFiles(rows, { includeCompanions })
  if (!files.length) return ''
  const origin = new URL(baseUrl).origin
  const calls = files.map(file => {
    const resolvedUrl = new URL(file.contentUrl, origin)
    if (resolvedUrl.origin !== origin) {
      throw new Error(`Cross-origin content URL rejected for ${file.fileCode}`)
    }
    const contentUrl = resolvedUrl.toString()
    return [
      'download_file',
      shellQuote(safePathSegment(file.fileCode)),
      shellQuote(safePathSegment(file.fileName)),
      shellQuote(file.sha256),
      shellQuote(contentUrl),
    ].join(' ')
  })
  return [
    '#!/usr/bin/env bash',
    'set -euo pipefail',
    '',
    ': "${GENEDATA_TOKEN:?Please export GENEDATA_TOKEN first}"',
    'CACHE_DIR="${GENEDATA_CACHE_DIR:-$PWD/genedata_cache}"',
    'mkdir -p "$CACHE_DIR"',
    '',
    'download_file() {',
    '  local file_code="$1"',
    '  local file_name="$2"',
    '  local sha256="$3"',
    '  local content_url="$4"',
    '  local file_dir="$CACHE_DIR/$file_code"',
    '  local target="$file_dir/$file_name"',
    '  local partial="${target}.part"',
    '  mkdir -p "$file_dir"',
    '  if [ -f "$target" ] && printf \'%s  %s\\n\' "$sha256" "$target" | sha256sum -c - >/dev/null 2>&1; then',
    '    printf \'cached %s\\n\' "$target"',
    '    return',
    '  fi',
    '  curl -fL --retry 3 --continue-at - \\',
    '    -H "Authorization: Bearer $GENEDATA_TOKEN" \\',
    '    -o "$partial" "$content_url"',
    '  printf \'%s  %s\\n\' "$sha256" "$partial" | sha256sum -c -',
    '  mv -f "$partial" "$target"',
    '}',
    '',
    ...calls,
    '',
    'printf \'cache_ready %s\\n\' "$CACHE_DIR"',
  ].join('\n')
}

export const buildPublicFileBatchScript = (
  rows,
  { baseUrl, includeCompanions = true, name = 'public-catalog-selection' } = {},
) => {
  const files = expandDownloadFiles(rows, { includeCompanions })
  if (!files.length) return ''
  const origin = new URL(baseUrl).origin
  const payload = JSON.stringify({
    name: normalizedText(name).slice(0, 255),
    strict: true,
    file_codes: files.map(file => file.fileCode),
  })
  return [
    '#!/usr/bin/env bash',
    'set -euo pipefail',
    '',
    ': "${GENEDATA_TOKEN:?Please export GENEDATA_TOKEN with batch:create and batch:read scopes}"',
    `BASE_URL=${shellQuote(origin)}`,
    'OUTPUT_DIR="${GENEDATA_BATCH_OUTPUT_DIR:-$PWD/genedata_batch}"',
    'BATCH_JSON="$OUTPUT_DIR/batch.json"',
    'MANIFEST_TSV="$OUTPUT_DIR/manifest.tsv"',
    'mkdir -p "$OUTPUT_DIR"',
    '',
    'curl_args=(',
    '  --fail-with-body --silent --show-error',
    '  -X POST "$BASE_URL/gd/api/v1/file-batches/"',
    '  -H "Authorization: Bearer $GENEDATA_TOKEN"',
    '  -H "Content-Type: application/json"',
    `  --data ${shellQuote(payload)}`,
    '  -o "$BATCH_JSON"',
    ')',
    'if [ -n "${GENEDATA_IDEMPOTENCY_KEY:-}" ]; then',
    '  curl_args+=( -H "Idempotency-Key: $GENEDATA_IDEMPOTENCY_KEY" )',
    'fi',
    'if ! curl "${curl_args[@]}"; then',
    '  cat "$BATCH_JSON" >&2 || true',
    '  exit 1',
    'fi',
    '',
    'read -r BATCH_ID MANIFEST_URL SNAPSHOT_SHA256 < <(',
    '  python3 -c \'import json,sys; p=json.load(open(sys.argv[1], encoding="utf-8")); print(p["batch_id"], p["manifest_tsv_url"], p["snapshot_sha256"])\' "$BATCH_JSON"',
    ')',
    'curl --fail-with-body --silent --show-error \\',
    '  -H "Authorization: Bearer $GENEDATA_TOKEN" \\',
    '  "$BASE_URL$MANIFEST_URL" \\',
    '  -o "$MANIFEST_TSV"',
    'printf \'batch_id=%s\\nsnapshot_sha256=%s\\nmanifest=%s\\n\' \\',
    '  "$BATCH_ID" "$SNAPSHOT_SHA256" "$MANIFEST_TSV"',
  ].join('\n')
}

export const buildPublicFileArchiveScript = (
  rows,
  { baseUrl, includeCompanions = true, name = 'public-catalog-archive' } = {},
) => {
  const files = expandDownloadFiles(rows, { includeCompanions })
  if (!files.length) return ''
  const origin = new URL(baseUrl).origin
  const payload = JSON.stringify({
    name: normalizedText(name).slice(0, 255),
    strict: true,
    file_codes: files.map(file => file.fileCode),
  })
  return [
    '#!/usr/bin/env bash',
    'set -euo pipefail',
    '',
    ': "${GENEDATA_TOKEN:?Token requires batch:create, batch:read, batch:archive and batch:download scopes}"',
    `BASE_URL=${shellQuote(origin)}`,
    'OUTPUT_DIR="${GENEDATA_ARCHIVE_OUTPUT_DIR:-$PWD/genedata_archive}"',
    'ARCHIVE_FORMAT="${GENEDATA_ARCHIVE_FORMAT:-tar.gz}"',
    'POLL_SECONDS="${GENEDATA_ARCHIVE_POLL_SECONDS:-5}"',
    'MAX_POLLS="${GENEDATA_ARCHIVE_MAX_POLLS:-720}"',
    'BATCH_JSON="$OUTPUT_DIR/batch.json"',
    'ARCHIVE_JSON="$OUTPUT_DIR/archive.json"',
    'STATUS_JSON="$OUTPUT_DIR/archive-status.json"',
    'mkdir -p "$OUTPUT_DIR"',
    'case "$ARCHIVE_FORMAT" in zip|tar.gz) ;; *) echo "GENEDATA_ARCHIVE_FORMAT must be zip or tar.gz" >&2; exit 2 ;; esac',
    '',
    'batch_args=(',
    '  --fail-with-body --silent --show-error',
    '  -X POST "$BASE_URL/gd/api/v1/file-batches/"',
    '  -H "Authorization: Bearer $GENEDATA_TOKEN"',
    '  -H "Content-Type: application/json"',
    `  --data ${shellQuote(payload)}`,
    '  -o "$BATCH_JSON"',
    ')',
    'if [ -n "${GENEDATA_IDEMPOTENCY_KEY:-}" ]; then',
    '  batch_args+=( -H "Idempotency-Key: $GENEDATA_IDEMPOTENCY_KEY" )',
    'fi',
    'if ! curl "${batch_args[@]}"; then cat "$BATCH_JSON" >&2 || true; exit 1; fi',
    'BATCH_ID="$(python3 -c \'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["batch_id"])\' "$BATCH_JSON")"',
    '',
    'archive_args=(',
    '  --fail-with-body --silent --show-error',
    '  -X POST "$BASE_URL/gd/api/v1/file-batches/$BATCH_ID/archives/"',
    '  -H "Authorization: Bearer $GENEDATA_TOKEN"',
    '  -H "Content-Type: application/json"',
    '  --data "{\\"format\\":\\"$ARCHIVE_FORMAT\\"}"',
    '  -o "$ARCHIVE_JSON"',
    ')',
    'if [ -n "${GENEDATA_ARCHIVE_IDEMPOTENCY_KEY:-}" ]; then',
    '  archive_args+=( -H "Idempotency-Key: $GENEDATA_ARCHIVE_IDEMPOTENCY_KEY" )',
    'fi',
    'if ! curl "${archive_args[@]}"; then cat "$ARCHIVE_JSON" >&2 || true; exit 1; fi',
    'mapfile -t archive_fields < <(python3 -c \'import json,sys; p=json.load(open(sys.argv[1], encoding="utf-8")); print(p["archive_id"]); print(p["status_url"])\' "$ARCHIVE_JSON")',
    'ARCHIVE_ID="${archive_fields[0]}"',
    'STATUS_URL="${archive_fields[1]}"',
    '',
    'STATUS=""',
    'DOWNLOAD_URL=""',
    'ARCHIVE_SHA256=""',
    'for ((poll=1; poll<=MAX_POLLS; poll++)); do',
    '  curl --fail-with-body --silent --show-error \\',
    '    -H "Authorization: Bearer $GENEDATA_TOKEN" \\',
    '    "$BASE_URL$STATUS_URL" -o "$STATUS_JSON"',
    '  mapfile -t status_fields < <(python3 -c \'import json,sys; p=json.load(open(sys.argv[1], encoding="utf-8")); print(p.get("status", "")); print(p.get("download_url") or ""); print(p.get("archive_sha256") or "")\' "$STATUS_JSON")',
    '  STATUS="${status_fields[0]}"',
    '  DOWNLOAD_URL="${status_fields[1]}"',
    '  ARCHIVE_SHA256="${status_fields[2]}"',
    '  case "$STATUS" in',
    '    ready) break ;;',
    '    failed|expired) cat "$STATUS_JSON" >&2; exit 1 ;;',
    '    queued|running) sleep "$POLL_SECONDS" ;;',
    '    *) echo "Unexpected archive status: $STATUS" >&2; cat "$STATUS_JSON" >&2; exit 1 ;;',
    '  esac',
    'done',
    'if [ "$STATUS" != ready ] || [ -z "$DOWNLOAD_URL" ] || [ -z "$ARCHIVE_SHA256" ]; then',
    '  echo "Archive did not become ready after $MAX_POLLS polls" >&2',
    '  exit 1',
    'fi',
    '',
    'ARCHIVE_FILE="$OUTPUT_DIR/$ARCHIVE_ID.$ARCHIVE_FORMAT"',
    'ARCHIVE_PART="${ARCHIVE_FILE}.part"',
    'curl --fail-with-body --silent --show-error --location --continue-at - \\',
    '  -H "Authorization: Bearer $GENEDATA_TOKEN" \\',
    '  "$BASE_URL$DOWNLOAD_URL" -o "$ARCHIVE_PART"',
    'printf \'%s  %s\\n\' "$ARCHIVE_SHA256" "$ARCHIVE_PART" | sha256sum -c -',
    'mv -f "$ARCHIVE_PART" "$ARCHIVE_FILE"',
    'printf \'batch_id=%s\\narchive_id=%s\\narchive=%s\\nsha256=%s\\n\' \\',
    '  "$BATCH_ID" "$ARCHIVE_ID" "$ARCHIVE_FILE" "$ARCHIVE_SHA256"',
  ].join('\n')
}

export const buildFilteredManifestUrl = (manifestPath, filters, baseUrl) => {
  const url = new URL(manifestPath, baseUrl)
  for (const [key, value] of Object.entries(filters || {})) {
    const normalized = normalizedText(value)
    if (normalized) url.searchParams.set(key, normalized)
  }
  return `${url.pathname}${url.search}`
}
