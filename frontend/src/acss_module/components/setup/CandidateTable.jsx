import React, { useCallback, useState } from 'react';
import { Trash2, Download, Sparkles } from 'lucide-react';
import { useACSSContext } from '../../context/ACSSContext';
import { setupApi } from '../../api/acssApi';

function CandidateTable({ candidates = [], isLocked = false }) {
  const { deleteAutoGenCandidate, acssSessionId, projectName } = useACSSContext();
  const [downloading, setDownloading] = useState(false);

  const handleDelete = useCallback(async (siteIid) => {
    try {
      await deleteAutoGenCandidate(siteIid);
    } catch (err) {
      console.error('Failed to delete candidate:', err);
    }
  }, [deleteAutoGenCandidate]);

  const handleDownload = useCallback(async () => {
    if (!acssSessionId || downloading) return;
    setDownloading(true);
    try {
      const data = await setupApi.downloadGdlCsv(acssSessionId, projectName);
      const { columns, rows } = data;
      const csvLines = [columns.join(',')];
      for (const row of rows) {
        csvLines.push(row.map((v) => (typeof v === 'string' && v.includes(',') ? `"${v}"` : v)).join(','));
      }
      const csv = csvLines.join('\n');
      const blob = new Blob([csv], { type: 'text/csv' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `candidates_gdl_${Date.now()}.csv`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Failed to download GDL CSV:', err);
    } finally {
      setDownloading(false);
    }
  }, [acssSessionId, projectName, downloading]);

  if (!candidates.length) return null;

  return (
    <div className="mt-3 p-3 rounded-lg bg-card/40 border border-border">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-foreground">Candidate sites ({candidates.length})</span>
        <button
          onClick={handleDownload}
          disabled={downloading}
          className="flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground disabled:opacity-50"
          title="Download candidate GDL CSV"
        >
          <Download className="w-3 h-3" />
          {downloading ? 'Downloading…' : 'GDL CSV'}
        </button>
      </div>
      <div className="space-y-1.5 max-h-60 overflow-y-auto">
        {candidates.map(site => (
          <div key={site.site_iid} className="flex items-center justify-between gap-2 px-2 py-1 rounded bg-background/40">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1.5">
                {site.auto_generated && <Sparkles className="w-3 h-3 text-muted-foreground dark:text-amber-400 flex-shrink-0" />}
                <span className="text-[11px] text-foreground truncate" title={site.site_iid}>{site.site_iid}</span>
              </div>
              <div className="text-[10px] text-muted-foreground">
                {Number(site.latitude).toFixed(4)}, {Number(site.longitude).toFixed(4)}
                {site.auto_generated && (
                  <>
                    <span className="ml-2">• {site.covers_poor_bins} poor bins</span>
                    {site.population_weighted && site.covers_population != null && (
                      <span className="ml-2 text-emerald-400">
                        • ≈{Number(site.covers_population).toLocaleString()} people
                      </span>
                    )}
                    {site.median_uplift_dB != null && (
                      <span className="ml-2">• +{Number(site.median_uplift_dB).toFixed(1)} dB</span>
                    )}
                  </>
                )}
              </div>
              {site.auto_generated && (site.azimuths || site.electrical_tilt_deg != null || site.height_m != null) && (
                <div className="text-[10px] text-muted-foreground mt-0.5">
                  {site.azimuths && (
                    <span>azimuths: [{site.azimuths.map(a => Math.round(Number(a))).join(', ')}]°</span>
                  )}
                  {site.electrical_tilt_deg != null && (
                    <span className="ml-2">tilt: {Number(site.electrical_tilt_deg).toFixed(1)}°</span>
                  )}
                  {site.height_m != null && (
                    <span className="ml-2">height: {Number(site.height_m).toFixed(1)}m</span>
                  )}
                  {site.max_tx_dbm != null && (
                    <span className="ml-2">P<sub>TX</sub>: {Number(site.max_tx_dbm).toFixed(1)} dBm</span>
                  )}
                  {site.ppre_dbm != null && (
                    <span className="ml-2 text-muted-foreground">PPRE: {Number(site.ppre_dbm).toFixed(1)} dBm</span>
                  )}
                  {/* Show the per-site resolved beam-pattern UID when it
                      differs from the session default (auto-gen snapped
                      tilt → different pattern in the same band). Helpful
                      for engineers verifying the EDS payload integrity. */}
                  {site.resolved_template_name && site.resolved_template_name !== site.template_name ? (
                    <span className="ml-2 truncate text-muted-foreground dark:text-amber-300" title={`session: ${site.template_name}\nresolved: ${site.resolved_template_name}`}>
                      • {site.resolved_template_name.split('\\').pop()}
                    </span>
                  ) : site.template_name ? (
                    <span className="ml-2 truncate" title={site.template_name}>
                      • {site.template_name.split('\\').pop()}
                    </span>
                  ) : null}
                </div>
              )}
            </div>
            {site.auto_generated && !isLocked && (
              <button
                onClick={() => handleDelete(site.site_iid)}
                className="p-1 rounded hover:bg-red-500/20"
                title="Remove candidate"
              >
                <Trash2 className="w-3 h-3 text-red-400" />
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export default CandidateTable;
