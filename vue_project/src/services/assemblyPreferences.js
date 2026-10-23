export const RECENT_ASSEMBLIES_KEY = 'genedata_recent_assemblies_v1';
export const MAX_RECENT_ASSEMBLIES = 10;

const getStorage = () => {
  try {
    return typeof localStorage === 'undefined' ? null : localStorage;
  } catch {
    return null;
  }
};

const normalizeText = (value) => (
  value === null || value === undefined ? '' : String(value).trim()
);

const normalizeId = (value) => {
  const id = Number(value);
  return Number.isInteger(id) && id > 0 ? id : null;
};

const normalizeTimestamp = (value) => {
  const normalized = normalizeText(value);
  if (!normalized) return null;
  const timestamp = new Date(normalized);
  return Number.isNaN(timestamp.getTime()) ? null : timestamp.toISOString();
};

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

const normalizeRecentAssembly = (item) => {
  if (!item || typeof item !== 'object') return null;
  const id = normalizeId(item.id);
  if (!id) return null;
  return {
    id,
    accession: normalizeText(item.accession),
    assembly: normalizeText(item.assembly),
    assembly_accession: normalizeText(item.assembly_accession),
    species: normalizeText(item.species),
    viewed_at: normalizeTimestamp(item.viewed_at)
  };
};

const normalizeRecentAssemblies = (items) => {
  const seen = new Set();
  return items
    .map(normalizeRecentAssembly)
    .filter((item) => {
      if (!item || seen.has(item.id)) return false;
      seen.add(item.id);
      return true;
    })
    .slice(0, MAX_RECENT_ASSEMBLIES);
};

export const getRecentAssemblies = () => normalizeRecentAssemblies(
  readArray(RECENT_ASSEMBLIES_KEY)
);

export const recordRecentAssembly = (assembly) => {
  const current = getRecentAssemblies();
  const item = normalizeRecentAssembly({
    ...assembly,
    viewed_at: new Date().toISOString()
  });
  if (!item) return { items: current, persisted: false };

  const next = [
    item,
    ...current.filter((existing) => existing.id !== item.id)
  ].slice(0, MAX_RECENT_ASSEMBLIES);

  const persisted = writeArray(RECENT_ASSEMBLIES_KEY, next);
  return {
    items: persisted ? next : current,
    persisted
  };
};

export const removeRecentAssembly = (id) => {
  const normalizedId = normalizeId(id);
  const current = getRecentAssemblies();
  const next = current.filter((item) => item.id !== normalizedId);
  const persisted = writeArray(RECENT_ASSEMBLIES_KEY, next);
  return {
    items: persisted ? next : current,
    persisted
  };
};

export const clearRecentAssemblies = () => {
  const current = getRecentAssemblies();
  const persisted = writeArray(RECENT_ASSEMBLIES_KEY, []);
  return {
    items: persisted ? [] : current,
    persisted
  };
};
