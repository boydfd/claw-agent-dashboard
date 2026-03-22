/**
 * Compute the Longest Common Subsequence of two line arrays.
 * Returns array of { aIdx, bIdx } index pairs.
 */
export function computeLCS(a, b) {
  const m = a.length, n = b.length
  const dp = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0))
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      dp[i][j] = a[i - 1] === b[j - 1] ? dp[i - 1][j - 1] + 1 : Math.max(dp[i - 1][j], dp[i][j - 1])
    }
  }
  const result = []
  let i = m, j = n
  while (i > 0 && j > 0) {
    if (a[i - 1] === b[j - 1]) {
      result.unshift({ aIdx: i - 1, bIdx: j - 1 })
      i--; j--
    } else if (dp[i - 1][j] > dp[i][j - 1]) {
      i--
    } else {
      j--
    }
  }
  return result
}

/**
 * Compute a unified diff between two text strings.
 * Returns array of { type: 'add'|'del'|'context', prefix: '+'|'-'|' ', text, oldNum, newNum }.
 */
export function computeDiff(oldText, newText) {
  if (!oldText && !newText) return []
  const oldLines = (oldText || '').split('\n')
  const newLines = (newText || '').split('\n')

  if (!oldText) {
    return newLines.map((line, i) => ({
      type: 'add', prefix: '+', text: line, oldNum: null, newNum: i + 1
    }))
  }
  if (!newText) {
    return oldLines.map((line, i) => ({
      type: 'del', prefix: '-', text: line, oldNum: i + 1, newNum: null
    }))
  }

  const lcs = computeLCS(oldLines, newLines)
  const lines = []
  let oi = 0, ni = 0, li = 0

  while (oi < oldLines.length || ni < newLines.length) {
    if (li < lcs.length && oi === lcs[li].aIdx && ni === lcs[li].bIdx) {
      lines.push({ type: 'context', prefix: ' ', text: oldLines[oi], oldNum: oi + 1, newNum: ni + 1 })
      oi++; ni++; li++
    } else {
      if (oi < oldLines.length && (li >= lcs.length || oi < lcs[li].aIdx)) {
        lines.push({ type: 'del', prefix: '-', text: oldLines[oi], oldNum: oi + 1, newNum: null })
        oi++
      }
      if (ni < newLines.length && (li >= lcs.length || ni < lcs[li].bIdx)) {
        lines.push({ type: 'add', prefix: '+', text: newLines[ni], oldNum: null, newNum: ni + 1 })
        ni++
      }
    }
  }
  return lines
}
