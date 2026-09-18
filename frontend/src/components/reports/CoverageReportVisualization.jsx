import React, { useMemo, useState } from "react";
// Legacy chart imports (used by commented-out charts below)
// import {
//   BarChart,
//   Bar,
//   PieChart,
//   Pie,
//   Cell,
//   XAxis,
//   YAxis,
//   CartesianGrid,
//   Tooltip,
//   Legend,
//   ResponsiveContainer,
//   LineChart,
//   Line,
// } from "recharts";
import { ChevronDown, ChevronUp, Maximize2, Minimize2 } from "lucide-react";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";

const RSRP_CATEGORY_ORDER = [
  "> -45 dBm",
  "-60 to -45 dBm",
  "-80 to -60 dBm",
  "-90 to -80 dBm",
  "-100 to -90 dBm",
  "-115 to -100 dBm",
  "-120 to -115 dBm",
];

const RSRP_COLORS = [
  "#00ff00",
  "#7fff00",
  "#ffff00",
  "#ffaa00",
  "#ff7f00",
  "#ff5500",
  "#ff0000",
];

const UNCOVERED_COLOR = "#4b5563";
const UNCOVERED_LABEL = "Uncovered (<-120 dBm)";
const UNCOVERED_TABLE_CATEGORY = "< -120 dBm";
const THRESHOLD_OPTIONS = [-80, -90, -100, -110];

function isUncoveredCategory(category) {
  if (!category) return false;
  const normalized = String(category).replace(/\s+/g, "").toLowerCase();
  return normalized.includes("<-120") || normalized.includes("uncovered");
}

function parseReportFilename(filename) {
  if (!filename) return { tech: "Unknown", arrayType: "", timestamp: "" };

  const base = filename.replace(/\.csv$/i, "");
  const tsMatch = base.match(/_(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})$/);
  const timestamp = tsMatch ? tsMatch[1].replace("_", " ") : "";
  const withoutTs = tsMatch ? base.slice(0, -tsMatch[0].length) : base;

  let tech = "Unknown";
  let rest = withoutTs;
  if (withoutTs.startsWith("LTE_")) {
    tech = "LTE";
    rest = withoutTs.slice(4);
  } else if (withoutTs.startsWith("FiveG_")) {
    tech = "5G NR";
    rest = withoutTs.slice(6);
  }

  const arrayType = rest
    .replace(/_user_defined_polygon\.kml$/, "")
    .replace(/\.kml$/, "");

  return { tech, arrayType, timestamp };
}

function categoryMeetsThreshold(category, thresholdDbm) {
  if (category.startsWith(">")) {
    const match = category.match(/>\s*(-?\d+)/);
    return match ? parseFloat(match[1]) > thresholdDbm : false;
  }
  const rangeMatch = category.match(/(-?\d+)\s+to\s+(-?\d+)/);
  if (rangeMatch) {
    const lower = parseFloat(rangeMatch[2]);
    return lower > thresholdDbm;
  }
  return false;
}

function buildInsight(overallCoveragePct, goodSignalPct) {
  if (overallCoveragePct < 20) {
    return `Poor coverage: only ${overallCoveragePct.toFixed(1)}% of the polygon is served.`;
  }
  if (goodSignalPct < 30) {
    return `Moderate coverage (${overallCoveragePct.toFixed(1)}%), but only ${goodSignalPct.toFixed(1)}% meets the signal threshold.`;
  }
  if (overallCoveragePct >= 70 && goodSignalPct >= 50) {
    return `Strong coverage: ${overallCoveragePct.toFixed(1)}% served with ${goodSignalPct.toFixed(1)}% at or above the threshold.`;
  }
  return `Moderate coverage: ${overallCoveragePct.toFixed(1)}% of polygon served; ${goodSignalPct.toFixed(1)}% meets the signal threshold.`;
}

/**
 * Coverage Report Visualization Component
 * Displays coverage report data with interactive charts and tables
 */
export function CoverageReportVisualization({ reportData }) {
  const [selectedPolygon, setSelectedPolygon] = useState(null);
  const [tableOpen, setTableOpen] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [rsrpThreshold, setRsrpThreshold] = useState(-90);

  const data = reportData?.data;
  const columns = reportData?.columns;
  const filename = reportData?.filename;

  const filteredData = useMemo(() => {
    if (!data || !Array.isArray(data)) return [];
    if (selectedPolygon) {
      return data.filter((row) => row["Polygon Name"] === selectedPolygon);
    }
    return data;
  }, [data, selectedPolygon]);

  const uniquePolygons = useMemo(() => {
    if (!data || !Array.isArray(data)) return [];
    const polygons = new Set();
    data.forEach((row) => {
      if (row["Polygon Name"]) polygons.add(row["Polygon Name"]);
    });
    return Array.from(polygons);
  }, [data]);

  const rsrpData = useMemo(() => {
    const grouped = {};
    filteredData.forEach((row) => {
      const category = row["RSRP Category"] || "Unknown";
      const area = parseFloat(row["COVERED AREA [SQKM]"]) || 0;
      const percentage = parseFloat(row["COVERED AREA [%]"]) || 0;

      if (!grouped[category]) {
        grouped[category] = {
          category,
          totalArea: 0,
          totalPercentage: 0,
          count: 0,
        };
      }

      grouped[category].totalArea += area;
      grouped[category].totalPercentage += percentage;
      grouped[category].count += 1;
    });

    return Object.values(grouped)
      .filter((item) => item.totalArea > 0)
      .sort((a, b) => {
        const aIdx = RSRP_CATEGORY_ORDER.indexOf(a.category);
        const bIdx = RSRP_CATEGORY_ORDER.indexOf(b.category);
        if (aIdx === -1 && bIdx === -1) return 0;
        if (aIdx === -1) return 1;
        if (bIdx === -1) return -1;
        return aIdx - bIdx;
      });
  }, [filteredData]);

  const polygonData = useMemo(() => {
    const grouped = {};
    filteredData.forEach((row) => {
      const polygon = row["Polygon Name"] || "Unknown";
      const area = parseFloat(row["COVERED AREA [SQKM]"]) || 0;
      const percentage = parseFloat(row["COVERED AREA [%]"]) || 0;

      if (!grouped[polygon]) {
        grouped[polygon] = {
          polygon,
          totalArea: 0,
          polygonArea: parseFloat(row["Polygon Area [SQKM]"]) || 0,
          rows: [],
        };
      }

      grouped[polygon].totalArea += area;
      grouped[polygon].rows.push(row);
    });

    return Object.values(grouped).map((p) => ({
      ...p,
      coveragePct:
        p.polygonArea > 0 ? (p.totalArea / p.polygonArea) * 100 : 0,
    }));
  }, [filteredData]);

  const metrics = useMemo(() => {
    const polygonArea =
      polygonData.length === 1
        ? polygonData[0].polygonArea
        : polygonData.reduce((sum, p) => sum + p.polygonArea, 0);

    const totalCoveredArea = rsrpData.reduce((sum, item) => sum + item.totalArea, 0);
    const overallCoveragePct =
      polygonArea > 0 ? (totalCoveredArea / polygonArea) * 100 : 0;
    const uncoveredArea = Math.max(0, polygonArea - totalCoveredArea);
    const uncoveredPct = polygonArea > 0 ? (uncoveredArea / polygonArea) * 100 : 0;

    const thresholdArea = rsrpData
      .filter((item) => categoryMeetsThreshold(item.category, rsrpThreshold))
      .reduce((sum, item) => sum + item.totalArea, 0);
    const thresholdPct = polygonArea > 0 ? (thresholdArea / polygonArea) * 100 : 0;

    return {
      polygonArea,
      totalCoveredArea,
      overallCoveragePct,
      uncoveredArea,
      uncoveredPct,
      thresholdArea,
      thresholdPct,
      insight: buildInsight(overallCoveragePct, thresholdPct),
    };
  }, [polygonData, rsrpData, rsrpThreshold]);

  const stackedSegments = useMemo(() => {
    const segments = rsrpData.map((item, idx) => ({
      category: item.category,
      area: item.totalArea,
      pct: metrics.polygonArea > 0 ? (item.totalArea / metrics.polygonArea) * 100 : 0,
      color: RSRP_COLORS[RSRP_CATEGORY_ORDER.indexOf(item.category)] ?? RSRP_COLORS[idx % RSRP_COLORS.length],
    }));

    if (metrics.uncoveredPct > 0.01) {
      segments.push({
        category: UNCOVERED_LABEL,
        area: metrics.uncoveredArea,
        pct: metrics.uncoveredPct,
        color: UNCOVERED_COLOR,
      });
    }

    return segments;
  }, [rsrpData, metrics]);

  // Legacy chartData — used by commented-out bar/pie charts below
  // const chartData = useMemo(() => {
  //   return rsrpData.map((item) => ({
  //     name: item.category,
  //     area: item.totalArea,
  //     percentage: item.count > 0 ? item.totalPercentage / item.count : 0,
  //     count: item.count,
  //   }));
  // }, [rsrpData]);

  const reportMeta = useMemo(() => parseReportFilename(filename), [filename]);

  const tableData = useMemo(() => {
    if (!filteredData.length) return [];

    const rowsByPolygon = {};
    filteredData.forEach((row) => {
      const polygon = row["Polygon Name"] || "Unknown";
      if (!rowsByPolygon[polygon]) {
        rowsByPolygon[polygon] = {
          polygonArea: parseFloat(row["Polygon Area [SQKM]"]) || 0,
          rows: [],
          hasUncovered: false,
        };
      }
      const category = row["RSRP Category"];
      if (isUncoveredCategory(category)) {
        rowsByPolygon[polygon].hasUncovered = true;
        rowsByPolygon[polygon].rows.push({
          ...row,
          "RSRP Category": UNCOVERED_TABLE_CATEGORY,
        });
      } else {
        rowsByPolygon[polygon].rows.push(row);
      }
    });

    const result = [];
    Object.values(rowsByPolygon).forEach(({ polygonArea, rows, hasUncovered }) => {
      result.push(...rows);
      if (!hasUncovered && polygonArea > 0) {
        const coveredSum = rows.reduce(
          (sum, row) => sum + (parseFloat(row["COVERED AREA [SQKM]"]) || 0),
          0
        );
        const uncoveredArea = Math.max(0, polygonArea - coveredSum);
        if (uncoveredArea > 0) {
          const sampleRow = rows[0];
          result.push({
            "Polygon Name": sampleRow["Polygon Name"],
            "Polygon Area [SQKM]": polygonArea,
            "RSRP Category": UNCOVERED_TABLE_CATEGORY,
            "COVERED AREA [SQKM]": uncoveredArea,
            "COVERED AREA [%]": (uncoveredArea / polygonArea) * 100,
          });
        }
      }
    });

    return result;
  }, [filteredData]);

  const handleDownloadCsv = () => {
    if (!tableData.length || !columns?.length) return;
    const header = columns.join(",");
    const rows = tableData.map((row) =>
      columns
        .map((col) => {
          const val = row[col];
          const str = val === undefined || val === null ? "" : String(val);
          return str.includes(",") ? `"${str}"` : str;
        })
        .join(",")
    );
    const blob = new Blob([[header, ...rows].join("\n")], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename || "coverage_report.csv";
    link.click();
    URL.revokeObjectURL(url);
  };

  if (!reportData) {
    return <div className="text-muted-foreground">No report data available</div>;
  }

  if (reportData.error) {
    return <div className="text-red-600 dark:text-red-400">Error: {reportData.error}</div>;
  }

  if (!data || !Array.isArray(data) || data.length === 0) {
    return <div className="text-muted-foreground">No data in report</div>;
  }

  return (
    <div className="w-full space-y-4 p-4 bg-card rounded-xl border border-border">
      {/* Report header */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center rounded-md bg-black dark:bg-blue-600/80 px-2 py-0.5 text-xs font-semibold text-white">
              {reportMeta.tech}
            </span>
            {reportMeta.timestamp && (
              <span className="text-xs text-muted-foreground">{reportMeta.timestamp}</span>
            )}
          </div>
          <h3 className="text-lg font-bold text-foreground mt-1 truncate">
            {reportMeta.arrayType || filename || "Coverage Report"}
          </h3>
          {uniquePolygons.length === 1 && (
            <p className="text-sm text-muted-foreground mt-0.5">
              {uniquePolygons[0]} · {metrics.polygonArea.toFixed(2)} sq km
            </p>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={handleDownloadCsv}
            className="text-xs px-3 py-1.5 rounded-lg bg-secondary text-foreground hover:bg-accent border border-border transition-colors"
          >
            Download CSV
          </button>
          <button
            type="button"
            onClick={() => setIsExpanded((v) => !v)}
            className="text-xs px-3 py-1.5 rounded-lg bg-secondary text-foreground hover:bg-accent border border-border transition-colors flex items-center gap-1"
          >
            {isExpanded ? (
              <>
                <Minimize2 className="w-3 h-3" /> Compact
              </>
            ) : (
              <>
                <Maximize2 className="w-3 h-3" /> Expand
              </>
            )}
          </button>
        </div>
      </div>

      {/* Polygon filter (multi-polygon only) */}
      {uniquePolygons.length > 1 && (
        <div className="bg-secondary rounded-lg p-3">
          <label className="block text-xs font-semibold text-foreground mb-1.5">
            Filter by Polygon
          </label>
          <select
            value={selectedPolygon || ""}
            onChange={(e) => setSelectedPolygon(e.target.value || null)}
            className="w-full md:w-64 px-3 py-1.5 text-sm bg-background text-foreground rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All Polygons</option>
            {uniquePolygons.map((polygon) => (
              <option key={polygon} value={polygon}>
                {polygon}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* KPI cards — corrected metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="bg-secondary rounded-lg p-3 border border-border">
          <div className="text-xs text-muted-foreground uppercase tracking-wide">Overall Coverage</div>
          <div className="text-2xl font-bold text-foreground mt-0.5">
            {metrics.overallCoveragePct.toFixed(1)}%
          </div>
          <div className="text-xs text-muted-foreground mt-0.5">
            {metrics.totalCoveredArea.toFixed(2)} sq km
          </div>
        </div>
        <div className="bg-secondary rounded-lg p-3 border border-border">
          <div className="text-xs text-muted-foreground uppercase tracking-wide">{UNCOVERED_LABEL}</div>
          <div className="text-2xl font-bold text-muted-foreground mt-0.5">
            {metrics.uncoveredPct.toFixed(1)}%
          </div>
          <div className="text-xs text-muted-foreground mt-0.5">
            {metrics.uncoveredArea.toFixed(2)} sq km
          </div>
        </div>
        <div className="bg-secondary rounded-lg p-3 border border-border">
          <div className="text-xs text-muted-foreground uppercase tracking-wide">
            ≥ {rsrpThreshold} dBm
          </div>
          <div className="text-2xl font-bold text-green-600 dark:text-green-400 mt-0.5">
            {metrics.thresholdPct.toFixed(1)}%
          </div>
          <div className="text-xs text-muted-foreground mt-0.5">
            {metrics.thresholdArea.toFixed(2)} sq km
          </div>
        </div>
        <div className="bg-secondary rounded-lg p-3 border border-border">
          <div className="text-xs text-muted-foreground uppercase tracking-wide">Polygon Area</div>
          <div className="text-2xl font-bold text-foreground mt-0.5">
            {metrics.polygonArea.toFixed(2)}
          </div>
          <div className="text-xs text-muted-foreground mt-0.5">sq km</div>
        </div>
      </div>

      {/* Plain-language insight */}
      <p className="text-sm text-white dark:text-blue-200 bg-black dark:bg-blue-900/30 border border-black dark:border-blue-300 dark:border-blue-800/50 rounded-lg px-3 py-2">
        {metrics.insight}
      </p>

      {/* Threshold selector (expanded mode) */}
      {isExpanded && (
        <div className="bg-secondary rounded-lg p-3 flex flex-wrap items-center gap-2">
          <span className="text-xs font-semibold text-foreground">Signal threshold:</span>
          {THRESHOLD_OPTIONS.map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setRsrpThreshold(t)}
              className={`text-xs px-2.5 py-1 rounded-md border transition-colors ${
                rsrpThreshold === t
                  ? "bg-black dark:bg-blue-500 border-black dark:border-blue-500 text-white"
                  : "bg-secondary border-border text-muted-foreground hover:bg-accent"
              }`}
            >
              {t} dBm
            </button>
          ))}
        </div>
      )}

      {/* Primary viz: stacked signal-quality bar */}
      {stackedSegments.length > 0 && (
        <div className="bg-secondary rounded-xl p-4 border border-border">
          <h4 className="text-sm font-semibold text-foreground mb-3">
            Signal Quality Distribution
          </h4>
          <div className="h-10 w-full rounded-lg overflow-hidden flex bg-muted">
            {stackedSegments.map((seg) => (
              <div
                key={seg.category}
                title={`${seg.category}: ${seg.area.toFixed(2)} sq km (${seg.pct.toFixed(1)}%)`}
                className="h-full transition-all duration-300 hover:opacity-80 cursor-default"
                style={{
                  width: `${Math.max(seg.pct, seg.pct > 0 ? 0.5 : 0)}%`,
                  backgroundColor: seg.color,
                  minWidth: seg.pct > 0 ? "2px" : 0,
                }}
              />
            ))}
          </div>
          <div className="mt-3 flex flex-wrap gap-x-3 gap-y-1">
            {stackedSegments.map((seg) => (
              <div key={seg.category} className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <span
                  className="w-2.5 h-2.5 rounded-sm shrink-0"
                  style={{ backgroundColor: seg.color }}
                />
                <span className="truncate max-w-[180px]">{seg.category}</span>
                <span className="text-muted-foreground">{seg.pct.toFixed(1)}%</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Polygon summary — only when multiple polygons */}
      {isExpanded && polygonData.length > 1 && (
        <div className="bg-secondary rounded-xl p-4 border border-border">
          <h4 className="text-sm font-semibold text-foreground mb-3">Coverage by Polygon</h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {polygonData.map((polygon) => (
              <button
                key={polygon.polygon}
                type="button"
                onClick={() => setSelectedPolygon(polygon.polygon)}
                className="text-left bg-muted rounded-lg p-3 border border-border hover:border-blue-500 transition-all"
              >
                <div className="flex justify-between items-center mb-2">
                  <span className="font-semibold text-foreground text-sm">{polygon.polygon}</span>
                  <span className="text-xs text-muted-foreground">{polygon.polygonArea.toFixed(2)} sq km</span>
                </div>
                <div className="flex justify-between text-xs mb-1.5">
                  <span className="text-muted-foreground">Covered</span>
                  <span className="text-foreground font-medium">
                    {polygon.coveragePct.toFixed(1)}% ({polygon.totalArea.toFixed(2)} sq km)
                  </span>
                </div>
                <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-blue-500 to-purple-500"
                    style={{ width: `${Math.min(100, polygon.coveragePct)}%` }}
                  />
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Collapsible data table */}
      <Collapsible open={tableOpen} onOpenChange={setTableOpen}>
        <CollapsibleTrigger className="flex w-full items-center justify-between rounded-lg bg-secondary border border-border px-4 py-2.5 text-sm font-semibold text-foreground hover:bg-accent transition-colors">
          <span>Detailed Data Table ({tableData.length} rows)</span>
          {tableOpen ? (
            <ChevronUp className="w-4 h-4 text-muted-foreground" />
          ) : (
            <ChevronDown className="w-4 h-4 text-muted-foreground" />
          )}
        </CollapsibleTrigger>
        <CollapsibleContent className="mt-2">
          <div className="bg-secondary rounded-lg border border-border overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-muted border-b border-border">
                    {columns?.map((col, idx) => (
                      <th
                        key={idx}
                        className="text-left py-2 px-3 text-foreground font-semibold uppercase tracking-wide text-xs whitespace-nowrap"
                      >
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {tableData.slice(0, 50).map((row, idx) => (
                    <tr
                      key={idx}
                      className="border-b border-border hover:bg-accent/50 transition-colors"
                    >
                      {columns?.map((col, colIdx) => {
                        const value = row[col];
                        const isCoveredAreaCol =
                          col === "COVERED AREA [SQKM]" || col === "COVERED AREA [%]";
                        const isNumeric =
                          isCoveredAreaCol ||
                          col.includes("%") ||
                          col.includes("SQKM") ||
                          col.includes("sq km");
                        const formatNumeric = (raw) => {
                          const num = typeof raw === "number" ? raw : parseFloat(raw);
                          if (Number.isNaN(num)) return String(raw);
                          return num.toFixed(isCoveredAreaCol ? 4 : 2);
                        };
                        return (
                          <td key={colIdx} className="py-2 px-3 text-muted-foreground whitespace-nowrap">
                            {value !== undefined && value !== null && value !== "" ? (
                              isNumeric ? (
                                <span className="font-medium text-black dark:text-blue-300">
                                  {formatNumeric(value)}
                                </span>
                              ) : (
                                String(value)
                              )
                            ) : (
                              <span className="text-muted-foreground">-</span>
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {tableData.length > 50 && (
              <div className="text-center text-muted-foreground text-xs py-2 bg-muted">
                Showing 50 of {tableData.length} rows
              </div>
            )}
          </div>
        </CollapsibleContent>
      </Collapsible>

      {/*
      =============================================================================
      LEGACY CHARTS (retained for reference — superseded by stacked signal bar above)
      =============================================================================

      const COLORS = RSRP_COLORS;

      {summary && (
        <div className="bg-gradient-to-r from-blue-800 to-purple-800 rounded-xl p-6 shadow-lg">
          <h3 className="text-2xl font-bold text-white mb-4 flex items-center gap-2">
            <span>📊</span> Report Summary
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {summary.total_rows && (
              <div className="bg-white/10 backdrop-blur-sm rounded-lg p-4 border border-white/20">
                <div className="text-xs text-blue-200 uppercase tracking-wide">Total Rows</div>
                <div className="text-3xl font-bold text-white mt-1">{summary.total_rows}</div>
              </div>
            )}
            {summary.total_polygons && (
              <div className="bg-white/10 backdrop-blur-sm rounded-lg p-4 border border-white/20">
                <div className="text-xs text-blue-200 uppercase tracking-wide">Total Polygons</div>
                <div className="text-3xl font-bold text-white mt-1">{summary.total_polygons}</div>
              </div>
            )}
            {summary.total_covered_area_sqkm !== undefined && (
              <div className="bg-white/10 backdrop-blur-sm rounded-lg p-4 border border-white/20">
                <div className="text-xs text-blue-200 uppercase tracking-wide">Total Covered Area</div>
                <div className="text-3xl font-bold text-white mt-1">
                  {summary.total_covered_area_sqkm.toFixed(2)}
                </div>
                <div className="text-xs text-blue-200 mt-1">sq km</div>
              </div>
            )}
            {summary.average_covered_percentage !== undefined && (
              <div className="bg-white/10 backdrop-blur-sm rounded-lg p-4 border border-white/20">
                <div className="text-xs text-blue-200 uppercase tracking-wide">Avg Coverage</div>
                <div className="text-3xl font-bold text-white mt-1">
                  {summary.average_covered_percentage.toFixed(2)}%
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {chartData.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-gray-800 rounded-xl p-6 shadow-lg">
            <h3 className="text-xl font-bold text-white mb-4">Coverage Area by RSRP Category</h3>
            <div className="bg-gray-700 rounded-lg p-4">
              <ResponsiveContainer width="100%" height={400}>
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#4a5568" />
                  <XAxis
                    dataKey="name"
                    angle={-45}
                    textAnchor="end"
                    height={100}
                    stroke="#e2e8f0"
                    style={{ fontSize: "12px" }}
                  />
                  <YAxis stroke="#e2e8f0" style={{ fontSize: "12px" }} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#1a202c",
                      border: "1px solid #4a5568",
                      borderRadius: "8px",
                      color: "#e2e8f0",
                    }}
                  />
                  <Legend wrapperStyle={{ color: "#e2e8f0" }} />
                  <Bar
                    dataKey="area"
                    name="Covered Area (sq km)"
                    fill="#3b82f6"
                    radius={[8, 8, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="bg-gray-800 rounded-xl p-6 shadow-lg">
            <h3 className="text-xl font-bold text-white mb-4">Coverage Distribution</h3>
            <div className="bg-gray-700 rounded-lg p-4">
              <ResponsiveContainer width="100%" height={400}>
                <PieChart>
                  <Pie
                    data={chartData}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    label={({ name, percentage }) =>
                      `${name}: ${percentage.toFixed(1)}%`
                    }
                    outerRadius={120}
                    fill="#8884d8"
                    dataKey="percentage"
                  >
                    {chartData.map((entry, index) => (
                      <Cell
                        key={`cell-${index}`}
                        fill={COLORS[index % COLORS.length]}
                      />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#1a202c",
                      border: "1px solid #4a5568",
                      borderRadius: "8px",
                      color: "#e2e8f0",
                    }}
                  />
                  <Legend wrapperStyle={{ color: "#e2e8f0" }} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}

      {rsrpData.length > 0 && (
        <div className="bg-gray-800 rounded-xl p-6 shadow-lg">
          <h3 className="text-xl font-bold text-white mb-4">Coverage by RSRP Category</h3>
          <div className="space-y-4">
            {rsrpData.map((item, idx) => {
              const maxArea = Math.max(...rsrpData.map((d) => d.totalArea), 1);
              const widthPercent = maxArea > 0 ? Math.min(100, (item.totalArea / maxArea) * 100) : 0;
              const color = COLORS[idx % COLORS.length];

              return (
                <div key={idx} className="space-y-2">
                  <div className="flex justify-between items-center">
                    <div className="text-sm font-semibold text-gray-300 w-48 truncate">
                      {item.category}
                    </div>
                    <div className="text-sm font-bold text-white w-32 text-right">
                      {item.totalArea.toFixed(2)} sq km
                    </div>
                    <div className="text-sm text-gray-400 w-24 text-right">
                      {item.totalPercentage.toFixed(2)}% avg
                    </div>
                  </div>
                  <div className="h-8 bg-gray-700 rounded-full overflow-hidden shadow-inner">
                    <div
                      className="h-full transition-all duration-500 ease-out rounded-full flex items-center justify-end pr-2"
                      style={{
                        width: `${widthPercent}%`,
                        backgroundColor: color,
                        boxShadow: `0 0 10px ${color}40`,
                      }}
                    >
                      <span className="text-xs font-bold text-white">
                        {widthPercent.toFixed(1)}%
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {polygonData.length > 0 && (
        <div className="bg-gray-800 rounded-xl p-6 shadow-lg">
          <h3 className="text-xl font-bold text-white mb-4">Coverage by Polygon</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {polygonData.map((polygon, idx) => (
              <div
                key={idx}
                className="bg-gray-700 rounded-lg p-4 border border-gray-600 hover:border-blue-500 transition-all cursor-pointer"
                onClick={() => setSelectedPolygon(polygon.polygon)}
              >
                <div className="flex justify-between items-center mb-3">
                  <div className="font-bold text-white text-lg">{polygon.polygon}</div>
                  <div className="text-xs text-gray-400 bg-gray-600 px-2 py-1 rounded">
                    {polygon.polygonArea.toFixed(2)} sq km
                  </div>
                </div>
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span className="text-gray-400 text-sm">Covered Area:</span>
                    <span className="text-white font-semibold">{polygon.totalArea.toFixed(2)} sq km</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400 text-sm">Coverage:</span>
                    <span className="text-blue-400 font-bold">{polygon.totalPercentage.toFixed(2)}%</span>
                  </div>
                  <div className="mt-2 h-2 bg-gray-600 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-blue-500 to-purple-500 transition-all"
                      style={{ width: `${Math.min(100, polygon.totalPercentage)}%` }}
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      Unused legacy imports kept for reference:
      LineChart, Line from recharts
      =============================================================================
      */}
    </div>
  );
}
