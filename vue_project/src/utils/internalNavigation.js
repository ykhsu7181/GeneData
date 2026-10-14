const ALLOWED_PATHS = [
  /^\/annotation(?:-card)?$/,
  /^\/assembly\/[1-9]\d*$/
]

const firstValue = value => (Array.isArray(value) ? value[0] : value)
const containsControlCharacter = value => Array.from(value).some((character) => {
  const code = character.charCodeAt(0)
  return code <= 31 || code === 127
})

const isUnsafeValue = (value) => (
  !value.startsWith('/')
  || value.startsWith('//')
  || value.includes('\\')
  || containsControlCharacter(value)
)

export const normalizeInternalAppPath = (value) => {
  const raw = String(firstValue(value) || '').trim()
  if (!raw || isUnsafeValue(raw)) return ''

  let decoded = raw
  for (let index = 0; index < 3; index += 1) {
    let nextValue
    try {
      nextValue = decodeURIComponent(decoded)
    } catch (error) {
      return ''
    }
    if (isUnsafeValue(nextValue)) return ''
    if (nextValue === decoded) break
    decoded = nextValue
  }

  let parsed
  try {
    parsed = new URL(raw, 'https://genedata.internal')
  } catch (error) {
    return ''
  }
  if (
    parsed.origin !== 'https://genedata.internal'
    || parsed.username
    || parsed.password
    || parsed.hash
    || !ALLOWED_PATHS.some(pattern => pattern.test(parsed.pathname))
  ) {
    return ''
  }
  return `${parsed.pathname}${parsed.search}`
}

export const normalizeAssemblyReturnPath = (value) => {
  const path = normalizeInternalAppPath(value)
  return /^\/assembly\/[1-9]\d*(?:\?|$)/.test(path) ? path : ''
}
