const API_BASE_URL = import.meta.env.VITE_DOWNLOAD_SERVICE_API_URL || 'http://localhost:8000/api';

const POLL_INTERVAL_MS = 1000;
const MAX_POLL_DURATION_MS = 10 * 60 * 1000;

const FILETYPE_DEFAULTS = {
  pdf: { ext: 'pdf', label: 'PDF' },
  md:  { ext: 'md',  label: 'Markdown' },
  csv: { ext: 'csv', label: 'CSV' },
};


const submitConversionJob = async (markdown, filetype = 'pdf') => {
  const response = await fetch(`${API_BASE_URL}/convert`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ markdown, filetype }),
  });

  if (!response.ok) {
    let errorMessage = 'Job submission failed';
    try {
      const error = await response.json();
      errorMessage = error.detail || errorMessage;
    } catch {
      errorMessage = response.statusText || errorMessage;
    }
    throw new Error(errorMessage);
  }

  return await response.json();
};


const checkJobStatus = async (jobId) => {
  const response = await fetch(`${API_BASE_URL}/status/${jobId}`);

  if (!response.ok) {
    throw new Error(`Status check failed: ${response.statusText}`);
  }

  return await response.json();
};


const pollForCompletion = async (jobId, onStatusUpdate, filetype = 'pdf') => {
  const startTime = Date.now();
  const label = FILETYPE_DEFAULTS[filetype]?.label || filetype.toUpperCase();

  while (true) {
    if (Date.now() - startTime > MAX_POLL_DURATION_MS) {
      throw new Error(`${label} conversion timed out after 2 minutes`);
    }

    const { status, error } = await checkJobStatus(jobId);
    onStatusUpdate?.(status);

    if (status === 'SUCCESS') return;
    if (status === 'FAILURE') throw new Error(error || `${label} conversion failed`);

    await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
  }
};


const triggerBrowserDownload = async (jobId, filetype = 'pdf') => {
  const downloadUrl = `${API_BASE_URL}/download/${jobId}`;
  const ext = FILETYPE_DEFAULTS[filetype]?.ext || filetype;

  const a = document.createElement('a');
  a.href = downloadUrl;
  a.download = `report_${Date.now()}.${ext}`;
  a.style.display = 'none';
  document.body.appendChild(a);
  a.click();

  setTimeout(() => document.body.removeChild(a), 100);
};


export const downloadToolResult = async (content, { filetype = 'pdf', onStatusUpdate } = {}) => {
  try {
    const { job_id } = await submitConversionJob(content, filetype);
    await pollForCompletion(job_id, onStatusUpdate, filetype);
    await triggerBrowserDownload(job_id, filetype);
    return { success: true };
  } catch (error) {
    console.error('Download error:', error);
    return { success: false, error: error.message };
  }
};

// Helping funtion to truncate the markdown text if it is too long
export const trimLargeTables = (mdData, maxRows = 5000) => {
  const lines = mdData.split(/\r?\n/);
  const newLines = [];
  let i = 0;
  let inFencedCode = false;
  let fenceDelimiter = null;

  function isSeparatorRow(line) {
      return /^\s*\|?[\s:-]+(\|[\s:-]+)*\|?\s*$/.test(line) && line.includes('-');
  }

  function isTableRow(line) {
      return line.includes("|") && line.trim() !== "";
  }

  while (i < lines.length) {
      const line = lines[i];

      const fenceMatch = line.match(/^(\s*)(```|~~~)/);
      if (fenceMatch) {
          const delimiter = fenceMatch[2];

          if (!inFencedCode) {
              inFencedCode = true;
              fenceDelimiter = delimiter;
          } else if (fenceDelimiter === delimiter) {
              inFencedCode = false;
              fenceDelimiter = null;
          }

          newLines.push(line);
          i++;
          continue;
      }

      // If inside fenced code → copy as-is
      if (inFencedCode) {
          newLines.push(line);
          i++;
          continue;
      }

      // ---- Detect valid markdown table ----
      if (
          isTableRow(line) &&
          i + 1 < lines.length &&
          isSeparatorRow(lines[i + 1])
      ) {
          const tableBlock = [line, lines[i + 1]];
          i += 2;

          while (i < lines.length && isTableRow(lines[i])) {
              tableBlock.push(lines[i]);
              i++;
          }

          const header = tableBlock.slice(0, 2);
          const dataRows = tableBlock.slice(2);

          if (dataRows.length > maxRows) {
             

              newLines.push(...header);
              newLines.push(...dataRows.slice(0, maxRows));
              newLines.push("truncated due to large size download to see all");
          } else {
              newLines.push(...tableBlock);
          }

          continue;
      }

      // ---- Normal markdown line ----
      newLines.push(line);
      i++;
  }

  return newLines.join("\n");

};

