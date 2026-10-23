export const RECENT_ACCESSIONS_KEY = 'recent_accessions_v2';
export const LEGACY_RECENT_ACCESSIONS_KEY = 'recent_accessions';
export const FAVORITE_ACCESSIONS_KEY = 'favorite_accessions_v1';
export const MAX_RECENT_ACCESSIONS = 20;

const getStorage = () => {
  try {
    return typeof localStorage === 'undefined' ? null : localStorage;
  } catch {
    return null;
  }
};

const normalizeAccession = (value) => (
  typeof value === 'string' ? value.trim() : ''
);

const parseArray = (rawValue) => {
  if (!rawValue) return [];
  try {
    const parsed = JSON.parse(rawValue);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
};

const readArray = (key) => {
  const storage = getStorage();
  if (!storage) return [];
  try {
    return parseArray(storage.getItem(key));
  } catch {
    return [];
  }
};

const writeArray = (key, items) => {
  const storage = getStorage();
  if (!storage) return false;
  try {
    storage.setItem(key, JSON.stringify(items));
    return true;
  } catch {
    return false;
  }
};

const normalizeTimestamp = (value) => {
  if (typeof value !== 'string' || !value.trim()) return null;
  const timestamp = new Date(value);
  return Number.isNaN(timestamp.getTime()) ? null : timestamp.toISOString();
};

const dedupeByAccession = (items) => {
  const seen = new Set();
  return items.filter((item) => {
    if (!item.accession || seen.has(item.accession)) return false;
    seen.add(item.accession);
    return true;
  });
};

const normalizeRecentItems = (items) => dedupeByAccession(
  items.map((item) => {
    if (typeof item === 'string') {
      return { accession: normalizeAccession(item), viewed_at: null };
    }
    if (!item || typeof item !== 'object') return { accession: '', viewed_at: null };
    return {
      accession: normalizeAccession(item.accession),
      viewed_at: normalizeTimestamp(item.viewed_at)
    };
  })
).slice(0, MAX_RECENT_ACCESSIONS);

const normalizeFavoriteItems = (items) => dedupeByAccession(
  items.map((item) => {
    if (!item || typeof item !== 'object') return { accession: '', created_at: null };
    return {
      accession: normalizeAccession(item.accession),
      created_at: normalizeTimestamp(item.created_at)
    };
  })
).filter((item) => item.created_at);

export const getRecentAccessions = () => {
  const storage = getStorage();
  if (!storage) return [];

  let currentRaw = null;
  try {
    currentRaw = storage.getItem(RECENT_ACCESSIONS_KEY);
  } catch {
    return [];
  }

  if (currentRaw !== null) {
    return normalizeRecentItems(parseArray(currentRaw));
  }

  const migrated = normalizeRecentItems(readArray(LEGACY_RECENT_ACCESSIONS_KEY));
  if (migrated.length) writeArray(RECENT_ACCESSIONS_KEY, migrated);
  return migrated;
};

export const recordRecentAccession = (accession) => {
  const normalized = normalizeAccession(accession);
  const current = getRecentAccessions();
  if (!normalized) return { items: current, persisted: false };

  const next = [
    { accession: normalized, viewed_at: new Date().toISOString() },
    ...current.filter((item) => item.accession !== normalized)
  ].slice(0, MAX_RECENT_ACCESSIONS);

  return {
    items: next,
    persisted: writeArray(RECENT_ACCESSIONS_KEY, next)
  };
};

export const removeRecentAccession = (accession) => {
  const normalized = normalizeAccession(accession);
  const current = getRecentAccessions();
  const next = current.filter((item) => item.accession !== normalized);
  const persisted = writeArray(RECENT_ACCESSIONS_KEY, next);
  return { items: persisted ? next : current, persisted };
};

export const clearRecentAccessions = () => {
  const current = getRecentAccessions();
  const persisted = writeArray(RECENT_ACCESSIONS_KEY, []);
  return { items: persisted ? [] : current, persisted };
};

export const getFavoriteAccessions = () => normalizeFavoriteItems(
  readArray(FAVORITE_ACCESSIONS_KEY)
);

export const isFavoriteAccession = (accession) => {
  const normalized = normalizeAccession(accession);
  return Boolean(normalized) && getFavoriteAccessions().some(
    (item) => item.accession === normalized
  );
};

export const toggleFavoriteAccession = (accession) => {
  const normalized = normalizeAccession(accession);
  const current = getFavoriteAccessions();
  if (!normalized) {
    return { items: current, isFavorite: false, persisted: false };
  }

  const alreadyFavorite = current.some((item) => item.accession === normalized);
  const next = alreadyFavorite
    ? current.filter((item) => item.accession !== normalized)
    : [
        { accession: normalized, created_at: new Date().toISOString() },
        ...current
      ];

  const persisted = writeArray(FAVORITE_ACCESSIONS_KEY, next);
  return {
    items: persisted ? next : current,
    isFavorite: persisted ? !alreadyFavorite : alreadyFavorite,
    persisted
  };
};

export const removeFavoriteAccession = (accession) => {
  const normalized = normalizeAccession(accession);
  const current = getFavoriteAccessions();
  const next = current.filter((item) => item.accession !== normalized);
  const persisted = writeArray(FAVORITE_ACCESSIONS_KEY, next);
  return { items: persisted ? next : current, persisted };
};
