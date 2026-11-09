/** Row-major 3x3 nodes. Skipped, unvisited midpoints join a straight jump. */
export function appendPatternNode(pattern: readonly number[], node: number): number[] {
  if (!Number.isInteger(node) || node < 0 || node > 8 || pattern.includes(node)) {
    return [...pattern];
  }
  const next = [...pattern];
  const last = next[next.length - 1];
  if (last !== undefined) {
    const row = Math.floor(last / 3);
    const column = last % 3;
    const nextRow = Math.floor(node / 3);
    const nextColumn = node % 3;
    if ((Math.abs(row - nextRow) === 2 || Math.abs(column - nextColumn) === 2) &&
        (row + nextRow) % 2 === 0 && (column + nextColumn) % 2 === 0) {
      const midpoint = ((row + nextRow) / 2) * 3 + (column + nextColumn) / 2;
      if (!next.includes(midpoint)) next.push(midpoint);
    }
  }
  next.push(node);
  return next;
}

/** Reject noncanonical paths instead of hashing several forms of one pattern. */
export function isValidLockPattern(pattern: readonly number[]): boolean {
  if (!Array.isArray(pattern) || pattern.length < 4 || pattern.length > 9) return false;
  let path: number[] = [];
  for (const node of pattern) {
    const next = appendPatternNode(path, node);
    if (next.length !== path.length + 1 || next[next.length - 1] !== node) return false;
    path = next;
  }
  return true;
}
