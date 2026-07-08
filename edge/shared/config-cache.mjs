export function makeConfigLoader(getRaw, ttlMs = 60_000) {
  let cached = null;
  let cachedAt = 0;
  return async function load(nowMs = Date.now()) {
    if (cached && nowMs - cachedAt < ttlMs) return cached;
    const raw = await getRaw();
    if (raw) {
      cached = raw;
      cachedAt = nowMs;
    }
    return cached;
  };
}
