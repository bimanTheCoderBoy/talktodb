import React, { useState, useCallback, useEffect, useMemo } from "react";
import { 
  ChevronDown, 
  ChevronRight, 
  Search, 
  Building2, 
  Signal, 
  Loader2, 
  X, 
  CheckSquare, 
  Square, 
  MinusSquare,
  Filter,
  Check
} from "lucide-react";
import { setupApi } from "../../api/acssApi";

// Array type options for baseline coverage, keyed by technology
const ARRAY_TYPE_OPTIONS = [
  { value: "LTE_Best_RSRP", label: "RSRP Best Server LTE", tech: "LTE" },
  // { value: "LTE_DL_Loss", label: "Downlink Path Loss LTE", tech: "LTE" },
  { value: "FiveG_Best_RSRP", label: "SS-RSRP Best Server 5G", tech: "FiveG" },
  // { value: "FiveG_DL_Loss_Ctrl", label: "DL Loss Control 5G", tech: "FiveG" },
  // { value: "FiveG_DL_Loss_Traffic", label: "DL Loss Traffic 5G", tech: "FiveG" },
  // { value: "FiveG_SSB_Index", label: "SSB Beam Index 5G", tech: "FiveG" },
  // { value: "FiveG_DL_BeamIndex_Traffic", label: "DL Beam Index 5G", tech: "FiveG" },
];

// Map raw technology strings from the DB to the tech key used in ARRAY_TYPE_OPTIONS
const normalizeTech = (rawTech) => {
  if (!rawTech) return null;
  const t = rawTech.toLowerCase();
  if (t.includes("nr") || t.includes("5g") || t.includes("fiveg")) return "FiveG";
  if (t.includes("lte")) return "LTE";
  return null;
};

export default function BaselineCellSelectionModal({ 
  isOpen, 
  onClose, 
  onConfirm, 
  boundaryCoords,
  boundaryRadiusKm,
  onBoundaryRadiusChange,
  projectName,
  acssSessionId 
}) {
  const [expandedSites, setExpandedSites] = useState(new Set());
  const [searchQuery, setSearchQuery] = useState("");
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Selection state
  const [selectedCells, setSelectedCells] = useState(new Set());
  
  // Filter state
  const [bandFilter, setBandFilter] = useState("");
  const [arrayType, setArrayType] = useState("");

  // Local boundary radius input (only used when onBoundaryRadiusChange is provided)
  const [localRadius, setLocalRadius] = useState(boundaryRadiusKm ?? 5);
  const canChangeRadius = typeof onBoundaryRadiusChange === 'function';

  // Sync local radius when parent prop changes (e.g. after Apply recalculates)
  useEffect(() => {
    if (boundaryRadiusKm != null) {
      setLocalRadius(boundaryRadiusKm);
    }
  }, [boundaryRadiusKm]);

  // Fetch cells in bounds on mount
  useEffect(() => {
    const fetchCells = async () => {
      if (!boundaryCoords || !acssSessionId || !projectName) {
        setError("Missing required parameters");
        setLoading(false);
        return;
      }

      setLoading(true);
      setError(null);
      
      try {
        const response = await setupApi.getCellsInBounds(acssSessionId, boundaryCoords, projectName);
        const sites = response.sites || [];
        setData(sites);
        
        // Determine the first band and only select cells matching it
        const bands = new Set();
        sites.forEach(site => {
          (site.cells || []).forEach(cell => {
            if (cell.band) bands.add(cell.band);
          });
        });
        const sortedBands = Array.from(bands).sort();
        const firstBand = sortedBands[0] || "";

        const matchingCellIds = new Set();
        sites.forEach(site => {
          (site.cells || []).forEach(cell => {
            if (cell.cell_iid && cell.band === firstBand) {
              matchingCellIds.add(cell.cell_iid);
            }
          });
        });
        setSelectedCells(matchingCellIds);
      } catch (err) {
        console.error("Error fetching cells:", err);
        setError(err.message || "Failed to load cells");
      } finally {
        setLoading(false);
      }
    };

    if (isOpen) {
      fetchCells();
    }
  }, [isOpen, boundaryCoords, acssSessionId, projectName]);

  // Extract unique bands from data
  const uniqueBands = useMemo(() => {
    const bands = new Set();
    data.forEach(site => {
      (site.cells || []).forEach(cell => {
        if (cell.band) {
          bands.add(cell.band);
        }
      });
    });
    return Array.from(bands).sort();
  }, [data]);

  // Auto-select first band when bands are loaded
  useEffect(() => {
    if (uniqueBands.length > 0 && !uniqueBands.includes(bandFilter)) {
      setBandFilter(uniqueBands[0]);
    }
  }, [uniqueBands]);

  // Build a map: band -> normalized technology (LTE | FiveG)
  const bandTechMap = useMemo(() => {
    const map = {};
    data.forEach(site => {
      (site.cells || []).forEach(cell => {
        if (cell.band && cell.technology && !map[cell.band]) {
          map[cell.band] = normalizeTech(cell.technology);
        }
      });
    });
    return map;
  }, [data]);

  // Determine the technology for the currently selected band
  const selectedBandTech = bandFilter ? bandTechMap[bandFilter] : null;

  // Filter array type options to only show matching technology
  const filteredArrayTypeOptions = useMemo(() => {
    if (!selectedBandTech) return [];
    return ARRAY_TYPE_OPTIONS.filter(o => o.tech === selectedBandTech);
  }, [selectedBandTech]);

  // When band filter changes: auto-select matching cells AND set the correct array type
  useEffect(() => {
    if (!bandFilter || data.length === 0) return;

    // Select only cells matching the new band
    const bandCellIds = new Set();
    data.forEach(site => {
      (site.cells || []).forEach(cell => {
        if (cell.cell_iid && cell.band === bandFilter) {
          bandCellIds.add(cell.cell_iid);
        }
      });
    });
    setSelectedCells(bandCellIds);

    // Auto-select the first compatible array type for this band's technology
    const tech = bandTechMap[bandFilter];
    if (tech) {
      const compatible = ARRAY_TYPE_OPTIONS.filter(o => o.tech === tech);
      if (compatible.length > 0) {
        setArrayType(prev => {
          const current = ARRAY_TYPE_OPTIONS.find(o => o.value === prev);
          if (current && current.tech === tech) return prev;
          return compatible[0].value;
        });
      }
    }
  }, [bandFilter, data, bandTechMap]);

  // Toggle site expansion
  const toggleSiteExpansion = useCallback((site_iid) => {
    setExpandedSites(prev => {
      const newSet = new Set(prev);
      if (newSet.has(site_iid)) {
        newSet.delete(site_iid);
      } else {
        newSet.add(site_iid);
      }
      return newSet;
    });
  }, []);

  // Filter sites based on search query and band filter
  const filteredSites = useMemo(() => {
    let result = data;
    
    // Apply band filter
    if (bandFilter) {
      result = result.map(site => ({
        ...site,
        cells: (site.cells || []).filter(cell => cell.band === bandFilter)
      })).filter(site => site.cells.length > 0);
    }
    
    // Apply search query
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      result = result.filter(site => {
        const siteIdMatch = site?.site_iid 
          ? String(site.site_iid).toLowerCase().includes(query)
          : false;
        
        const cellMatch = site?.cells && Array.isArray(site.cells)
          ? site.cells.some(cell => {
              const cellIdMatch = cell?.cell_iid 
                ? String(cell.cell_iid).toLowerCase().includes(query)
                : false;
              const bandMatch = cell?.band 
                ? String(cell.band).toLowerCase().includes(query)
                : false;
              return cellIdMatch || bandMatch;
            })
          : false;
        
        return siteIdMatch || cellMatch;
      });
    }
    
    return result;
  }, [data, searchQuery, bandFilter]);

  const totalCells = data.reduce((sum, site) => sum + (site.cells?.length || 0), 0);
  const totalFilteredCells = filteredSites.reduce((sum, site) => sum + (site.cells?.length || 0), 0);

  // Selection helpers
  const getAllCellIdsForSite = (site) => {
    return (site.cells || []).map(cell => cell.cell_iid).filter(Boolean);
  };

  const isSiteFullySelected = (site) => {
    const cellIds = getAllCellIdsForSite(site);
    return cellIds.length > 0 && cellIds.every(id => selectedCells.has(id));
  };

  const isSitePartiallySelected = (site) => {
    const cellIds = getAllCellIdsForSite(site);
    const selectedCount = cellIds.filter(id => selectedCells.has(id)).length;
    return selectedCount > 0 && selectedCount < cellIds.length;
  };

  // Toggle cell selection
  const toggleCellSelection = (cellId) => {
    setSelectedCells(prev => {
      const newSet = new Set(prev);
      if (newSet.has(cellId)) {
        newSet.delete(cellId);
      } else {
        newSet.add(cellId);
      }
      return newSet;
    });
  };

  // Toggle site selection (selects/deselects all cells in site)
  const toggleSiteSelection = (site) => {
    const cellIds = getAllCellIdsForSite(site);
    const isFullySelected = isSiteFullySelected(site);

    setSelectedCells(prev => {
      const newSet = new Set(prev);
      if (isFullySelected) {
        cellIds.forEach(id => newSet.delete(id));
      } else {
        cellIds.forEach(id => newSet.add(id));
      }
      return newSet;
    });
  };

  // Select all / Deselect all
  const isAllSelected = useMemo(() => {
    const allCellIds = filteredSites.flatMap(site => getAllCellIdsForSite(site));
    return allCellIds.length > 0 && allCellIds.every(id => selectedCells.has(id));
  }, [filteredSites, selectedCells]);

  const toggleSelectAll = () => {
    if (isAllSelected) {
      // Deselect all visible cells
      const visibleCellIds = filteredSites.flatMap(site => getAllCellIdsForSite(site));
      setSelectedCells(prev => {
        const newSet = new Set(prev);
        visibleCellIds.forEach(id => newSet.delete(id));
        return newSet;
      });
    } else {
      // Select all visible cells
      const visibleCellIds = filteredSites.flatMap(site => getAllCellIdsForSite(site));
      setSelectedCells(prev => {
        const newSet = new Set(prev);
        visibleCellIds.forEach(id => newSet.add(id));
        return newSet;
      });
    }
  };

  // Count selected sites (sites with at least one cell selected)
  const selectedSitesCount = useMemo(() => {
    let count = 0;
    data.forEach(site => {
      const cellIds = getAllCellIdsForSite(site);
      if (cellIds.some(id => selectedCells.has(id))) {
        count++;
      }
    });
    return count;
  }, [data, selectedCells]);

  // Build full site objects with only selected cells
  const buildSelectedSitesData = useCallback(() => {
    const selectedSites = [];
    
    data.forEach(site => {
      // Filter cells that are selected
      const selectedSiteCells = (site.cells || []).filter(cell => 
        selectedCells.has(cell.cell_iid)
      );
      
      // Only include site if it has selected cells
      if (selectedSiteCells.length > 0) {
        selectedSites.push({
          site_iid: site.site_iid,
          latitude: site.latitude,
          longitude: site.longitude,
          technology: site.technology || [],
          cells: selectedSiteCells.map(cell => ({
            cell_iid: cell.cell_iid,
            azimuth: cell.azimuth,
            band: cell.band,
            pci: cell.pci,
            technology: cell.technology,
            selected: true
          }))
        });
      }
    });
    
    return selectedSites;
  }, [data, selectedCells]);

  const canConfirm = selectedCells.size > 0 && !!arrayType;

  // Handle confirm
  const handleConfirm = () => {
    if (!canConfirm) return;
    const selectedSitesData = buildSelectedSitesData();
    const selectedOption = ARRAY_TYPE_OPTIONS.find(o => o.value === arrayType);
    onConfirm(selectedSitesData, arrayType, selectedOption?.tech || "LTE", bandFilter);
  };

  if (!isOpen) return null;

  return (
    <div className="absolute top-0 left-0 right-0 bottom-0 min-h-screen z-[5000000] min-w-screen bg-white/20">
      <div className="fixed inset-0 z-50 flex items-center justify-center backdrop-blur-[2px] bg-black/40">
        <div className="w-[700px] max-h-[85vh] bg-card border border-primary/30 rounded-xl shadow-2xl shadow-black/50 flex flex-col overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between p-3 border-b border-border bg-secondary/50">
            <div className="flex items-center gap-2">
              <Building2 className="w-4 h-4 text-primary" />
              <h3 className="text-sm font-semibold text-foreground">Select Baseline Cells</h3>
              <span className="px-2 py-0.5 bg-primary/20 text-primary text-xs font-medium rounded-full">
                {data.length} sites, {totalCells} cells
              </span>
            </div>
            <button
              onClick={onClose}
              className="p-1.5 hover:bg-accent rounded-lg transition-colors"
              title="Close"
            >
              <X className="w-4 h-4 text-muted-foreground hover:text-foreground" />
            </button>
          </div>

          {/* Filters Section */}
          <div className="p-3 border-b border-border bg-card/50 space-y-3">
            {/* Search */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search sites, cells, bands..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-4 py-2 text-sm border border-border rounded-lg bg-secondary text-foreground placeholder-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary/50"
              />
            </div>

            {/* Filter Row */}
            <div className="flex items-center gap-3">
              {/* Band Filter */}
              <div className="flex items-center gap-2">
                <Filter className="w-4 h-4 text-muted-foreground" />
                <select
                  value={bandFilter}
                  onChange={(e) => setBandFilter(e.target.value)}
                  className="appearance-none px-3 py-1.5 text-sm border border-border rounded-lg bg-secondary text-foreground cursor-pointer outline-none transition-colors hover:border-primary/50 focus:ring-2 focus:ring-primary/50"
                >
                  {uniqueBands.map(band => (
                    <option key={band} value={band} className="bg-popover text-popover-foreground">{band}</option>
                  ))}
                </select>
              </div>

              {/* Array Type Dropdown — locked to the selected band's technology */}
              <div className="flex items-center gap-2 ml-auto">
                <span className="text-xs text-muted-foreground">Array Type:</span>
                <select
                  value={arrayType}
                  onChange={(e) => setArrayType(e.target.value)}
                  disabled={filteredArrayTypeOptions.length === 0}
                  className={`appearance-none px-3 py-1.5 text-sm border rounded-lg outline-none transition-colors focus:ring-2 focus:ring-primary/50 ${
                    filteredArrayTypeOptions.length === 0
                      ? 'border-border bg-muted text-muted-foreground cursor-not-allowed'
                      : 'border-border bg-secondary text-foreground cursor-pointer hover:border-primary/50'
                  }`}
                >
                  {filteredArrayTypeOptions.length === 0 ? (
                    <option value="" className="bg-popover text-popover-foreground">Select a band first</option>
                  ) : (
                    filteredArrayTypeOptions.map(option => (
                      <option key={option.value} value={option.value} className="bg-popover text-popover-foreground">{option.label}</option>
                    ))
                  )}
                </select>
                {selectedBandTech && (
                  <span className={`px-1.5 py-0.5 text-xs rounded font-medium ${
                    selectedBandTech === 'FiveG' 
                      ? 'bg-purple-500/20 text-purple-400' 
                      : 'bg-blue-500/20 text-blue-400'
                  }`}>
                    {selectedBandTech === 'FiveG' ? '5G' : 'LTE'}
                  </span>
                )}
              </div>
            </div>

            {/* Boundary Radius Control (when available) */}
            {canChangeRadius && (
              <div className="flex items-center gap-3 p-2 bg-secondary/30 rounded-lg border border-border/50">
                <span className="text-xs text-muted-foreground whitespace-nowrap">Boundary Radius:</span>
                <input
                  type="range"
                  min={1}
                  max={50}
                  step={1}
                  value={localRadius}
                  onChange={(e) => setLocalRadius(Number(e.target.value))}
                  className="flex-1 h-1.5 accent-primary cursor-pointer"
                />
                <input
                  type="number"
                  min={1}
                  max={50}
                  value={localRadius}
                  onChange={(e) => {
                    const val = Number(e.target.value);
                    if (val >= 1 && val <= 50) setLocalRadius(val);
                  }}
                  className="w-14 px-2 py-1 text-sm text-center border border-border rounded bg-secondary text-foreground focus:outline-none focus:ring-1 focus:ring-primary/50"
                />
                <span className="text-xs text-muted-foreground">km</span>
                <button
                  onClick={() => onBoundaryRadiusChange(localRadius)}
                  disabled={localRadius === boundaryRadiusKm}
                  className={`px-3 py-1 text-xs font-medium rounded-lg transition-all ${
                    localRadius !== boundaryRadiusKm
                      ? 'bg-primary text-primary-foreground hover:bg-primary/90 cursor-pointer'
                      : 'bg-muted text-muted-foreground cursor-not-allowed'
                  }`}
                >
                  Apply
                </button>
              </div>
            )}

            {/* Selection Controls */}
            <div className="flex items-center justify-between">
              <button
                onClick={toggleSelectAll}
                className="flex items-center gap-2 px-3 py-1.5 text-sm text-foreground hover:text-foreground hover:bg-accent rounded-lg transition-colors"
              >
                {isAllSelected ? (
                  <CheckSquare className="w-4 h-4 text-primary" />
                ) : (
                  <Square className="w-4 h-4" />
                )}
                <span>{isAllSelected ? 'Deselect All' : 'Select All'}</span>
              </button>
              
              {/* Selection Counter */}
              <div className="flex items-center gap-2">
                {selectedCells.size > 0 && (
                  <span className="px-2.5 py-1 bg-primary/20 border border-primary/40 text-primary text-xs font-medium rounded-full">
                    {selectedSitesCount} {selectedSitesCount === 1 ? 'site' : 'sites'}, {selectedCells.size} {selectedCells.size === 1 ? 'cell' : 'cells'} selected
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Sites List */}
          <div className="flex-1 overflow-y-auto p-2 scrollbar-thin scrollbar-thumb-secondary scrollbar-track-transparent">
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="w-6 h-6 text-primary animate-spin" />
                <span className="ml-2 text-muted-foreground text-sm">Loading cells in boundary...</span>
              </div>
            ) : error ? (
              <div className="py-8 text-center">
                <p className="text-sm text-red-400">{error}</p>
              </div>
            ) : filteredSites.length === 0 ? (
              <div className="py-8 text-center">
                <p className="text-sm text-muted-foreground">
                  {searchQuery
                    ? "No sites or cells found matching your filters" 
                    : "No cells found within the boundary area"}
                </p>
              </div>
            ) : (
              filteredSites.map((site) => {
                if (!site || !site.site_iid) return null;
                
                const isExpanded = expandedSites.has(site.site_iid);
                const cells = site.cells || [];
                const isFullySelected = isSiteFullySelected(site);
                const isPartiallySelected = isSitePartiallySelected(site);
                
                return (
                  <div 
                    key={site.site_iid} 
                    className="mb-1 last:mb-0"
                  >
                    {/* Site Header */}
                    <div className="p-2 hover:bg-accent/50 transition-colors rounded-lg">
                      <div className="flex items-center gap-2">
                        {/* Site Checkbox */}
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            toggleSiteSelection(site);
                          }}
                          className="p-0.5 hover:bg-accent rounded transition-colors"
                          title={isFullySelected ? "Deselect all cells" : "Select all cells"}
                        >
                          {isFullySelected ? (
                            <CheckSquare className="w-4 h-4 text-primary" />
                          ) : isPartiallySelected ? (
                            <MinusSquare className="w-4 h-4 text-primary/60" />
                          ) : (
                            <Square className="w-4 h-4 text-muted-foreground" />
                          )}
                        </button>

                        {/* Expand/Collapse */}
                        <button
                          onClick={() => toggleSiteExpansion(site.site_iid)}
                          className="p-1 hover:bg-accent rounded transition-colors"
                        >
                          {isExpanded ? (
                            <ChevronDown className="w-4 h-4 text-muted-foreground" />
                          ) : (
                            <ChevronRight className="w-4 h-4 text-muted-foreground" />
                          )}
                        </button>

                        {/* Site Info */}
                        <div className="flex-1 min-w-0 cursor-pointer" onClick={() => toggleSiteExpansion(site.site_iid)}>
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium text-foreground truncate">
                              {site.site_iid}
                            </span>
                            <span className="px-1.5 py-0.5 text-xs bg-secondary text-muted-foreground rounded">
                              {cells.length} {cells.length === 1 ? 'cell' : 'cells'}
                            </span>
                            {site.technology && site.technology.length > 0 && (
                              <span className="text-xs text-muted-foreground">
                                {site.technology.join(', ')}
                              </span>
                            )}
                          </div>
                          {site.latitude && site.longitude && (
                            <div className="text-xs text-muted-foreground mt-0.5">
                              {site.latitude.toFixed(4)}, {site.longitude.toFixed(4)}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                    
                    {/* Cells List */}
                    {isExpanded && (
                      <div className="ml-8 mr-2 mb-2 space-y-0.5 border-l border-border pl-2">
                        {cells.map((cell) => {
                          if (!cell || !cell.cell_iid) return null;
                          const isCellSelected = selectedCells.has(cell.cell_iid);
                          
                          return (
                            <div
                              key={cell.cell_iid}
                              className={`flex items-center gap-2 p-2 rounded-lg transition-all cursor-pointer ${
                                isCellSelected 
                                  ? 'bg-primary/10 border border-primary/30' 
                                  : 'hover:bg-accent/50 border border-transparent'
                              }`}
                              onClick={() => toggleCellSelection(cell.cell_iid)}
                            >
                              {/* Cell Checkbox */}
                              <div className="p-0.5">
                                {isCellSelected ? (
                                  <CheckSquare className="w-4 h-4 text-primary" />
                                ) : (
                                  <Square className="w-4 h-4 text-muted-foreground" />
                                )}
                              </div>

                              <Signal className="w-3.5 h-3.5 text-primary/70" />
                              
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 flex-wrap">
                                  <span className="text-xs font-medium text-foreground truncate">
                                    {cell.cell_iid}
                                  </span>
                                  {cell.band && (
                                    <span className="px-1.5 py-0.5 text-xs bg-secondary text-muted-foreground rounded">
                                      {cell.band}
                                    </span>
                                  )}
                                  {cell.technology && (
                                    <span className="text-xs text-muted-foreground">{cell.technology}</span>
                                  )}
                                  {cell.azimuth !== null && cell.azimuth !== undefined && (
                                    <span className="text-xs text-muted-foreground">Az: {cell.azimuth}°</span>
                                  )}
                                  {cell.pci !== null && cell.pci !== undefined && (
                                    <span className="text-xs text-muted-foreground">PCI: {cell.pci}</span>
                                  )}
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>

          {/* Footer - Action Buttons */}
          <div className="p-3 border-t border-border bg-secondary/50">
            <div className="flex items-center justify-between gap-3">
              {/* Selection Summary */}
              <div className="text-xs text-muted-foreground">
                {selectedCells.size > 0 
                  ? `${selectedCells.size} cell${selectedCells.size !== 1 ? 's' : ''} selected for baseline`
                  : 'Select a band and cells to continue'
                }
              </div>

              {/* Action Buttons */}
              <div className="flex items-center gap-2">
                <button
                  onClick={onClose}
                  className="flex items-center gap-2 px-4 py-1.5 rounded-lg text-sm font-medium transition-all bg-secondary text-foreground hover:bg-accent border border-border"
                >
                  Cancel
                </button>
                <button
                  onClick={handleConfirm}
                  disabled={!canConfirm}
                  className={`flex items-center gap-2 px-4 py-1.5 rounded-lg text-sm font-medium transition-all ${
                    canConfirm
                      ? 'bg-primary text-primary-foreground hover:bg-primary/90 shadow-lg shadow-primary/20'
                      : 'bg-muted text-muted-foreground cursor-not-allowed'
                  }`}
                >
                  <Check className="w-4 h-4" />
                  Confirm Selection
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
