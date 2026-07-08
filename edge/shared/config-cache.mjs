export function makeConfigLoader(getRaw, ttlMs = 60_000) {
  let cached = null;
  let cachedAt = 0;
  return async function load(nowMs = Date.now()) {
    if (cached && nowMs - cachedAt < ttlMs) return cached;
    let raw = null;
    try {
      raw = await getRaw();
    } catch {
      return cached;
    }
    if (raw) {
      cached = raw;
      cachedAt = nowMs;
    }
    return cached;
  };
}
