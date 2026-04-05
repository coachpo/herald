/**
 * Rule filter evaluation — port of backend/core/rules.py
 * Evaluates forwarding rule filters against an ingest message.
 */

export function ruleMatchesMessage(filterJson, message) {
  const f = filterJson || {};

  const ingestIds = f.ingest_endpoint_ids;
  if (ingestIds != null) {
    const allowed = new Set(ingestIds.map(String));
    if (!allowed.has(String(message.ingest_endpoint_id || ""))) {
      return false;
    }
  }

  const bodyFilter = f.body || {};

  const contains = bodyFilter.contains;
  if (contains != null) {
    const hay = (message.body || "").toLowerCase();
    const needles = (Array.isArray(contains) ? contains : [])
      .map((s) => String(s).toLowerCase())
      .filter((s) => s.trim());
    if (needles.length > 0 && !needles.some((n) => hay.includes(n))) {
      return false;
    }
  }

  const regex = bodyFilter.regex;
  if (regex != null && String(regex).trim()) {
    try {
      const pat = new RegExp(String(regex), "i");
      if (!pat.test(message.body || "")) {
        return false;
      }
    } catch {
      return false;
    }
  }

  const priorityFilter = f.priority || {};
  const pmin = priorityFilter.min;
  if (pmin != null) {
    const minVal = parseInt(String(pmin), 10);
    if (!isNaN(minVal) && (message.priority || 3) < minVal) {
      return false;
    }
  }
  const pmax = priorityFilter.max;
  if (pmax != null) {
    const maxVal = parseInt(String(pmax), 10);
    if (!isNaN(maxVal) && (message.priority || 3) > maxVal) {
      return false;
    }
  }

  const tagsFilter = f.tags;
  if (tagsFilter != null && Array.isArray(tagsFilter) && tagsFilter.length > 0) {
    const msgTags = new Set(
      (Array.isArray(message.tags) ? message.tags : []).map((t) =>
        String(t).toLowerCase(),
      ),
    );
    const filterTags = tagsFilter.map((t) => String(t).toLowerCase());
    if (!filterTags.some((t) => msgTags.has(t))) {
      return false;
    }
  }

  const groupFilter = f.group;
  if (groupFilter != null) {
    if ((message.group || "") !== String(groupFilter)) {
      return false;
    }
  }

  return true;
}
