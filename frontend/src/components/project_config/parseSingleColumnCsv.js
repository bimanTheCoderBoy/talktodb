/**
 * Parse a single-column CSV string into an array of trimmed, non-empty values.
 *
 * Expectations:
 *  - First non-empty row is treated as a header and skipped.
 *  - One value per row (if extra comma-separated fields exist, only the first is used).
 *  - Handles BOM, mixed line-endings, quoted values, and blank rows.
 */
export function parseSingleColumnCsv(rawText) {
  if (!rawText || typeof rawText !== 'string') return [];

  // Strip UTF-8 BOM
  const text = rawText.replace(/^\uFEFF/, '');

  const lines = text.split(/\r\n|\r|\n/);

  const values = [];
  let headerSkipped = false;

  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed === '') continue;

    if (!headerSkipped) {
      headerSkipped = true;
      continue;
    }

    // Take first field only (handles accidental extra columns)
    let value = trimmed.split(',')[0].trim();

    // Strip surrounding quotes (single or double)
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1).trim();
    }

    if (value !== '') {
      values.push(value);
    }
  }

  return values;
}
