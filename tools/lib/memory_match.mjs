// Structured, exact-value matching for the Fashion E2E proof's memory gate.
//
// The gate must confirm that the domain's operational memory captured for a
// completed workflow references THAT workflow's exact id — not merely that
// the domain has some memory. A JSON.stringify(...).includes(id) substring
// check is unsound: it produces false positives whenever one workflow id is
// a substring of another (e.g. "wf-10" inside "wf-100"), or whenever the
// target id happens to appear inside unrelated free text. This module
// instead walks the memory entry's structure and requires an exact (===)
// value match on some field, recursively, so nested metadata (however deep)
// is checked without ever treating a substring as a match.

/**
 * @param {unknown} value
 * @param {string} workflowId
 * @returns {boolean}
 */
export function memoryEntryMatchesWorkflowId(value, workflowId) {
  if (value === workflowId) return true;
  if (value === null || value === undefined) return false;
  if (Array.isArray(value)) {
    return value.some((item) => memoryEntryMatchesWorkflowId(item, workflowId));
  }
  if (typeof value === "object") {
    return Object.values(value).some((item) =>
      memoryEntryMatchesWorkflowId(item, workflowId),
    );
  }
  // Primitives other than an exact string match (numbers, booleans, other
  // strings) never match — no substring fallback.
  return false;
}

/**
 * @param {unknown[]} memoryList
 * @param {string} workflowId
 * @returns {boolean}
 */
export function workflowMemoryIdMatched(memoryList, workflowId) {
  if (!Array.isArray(memoryList) || memoryList.length === 0) return false;
  return memoryList.some((entry) => memoryEntryMatchesWorkflowId(entry, workflowId));
}
