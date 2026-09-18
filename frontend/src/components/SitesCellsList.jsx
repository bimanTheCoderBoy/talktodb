import React, { useState, useCallback, useEffect, useMemo } from "react";
import { ChevronDown, ChevronRight, Search, Building2, Signal, Loader2, Copy, Check, X, Play, CheckSquare, Square, MinusSquare } from "lucide-react";
import { toast } from "react-toastify";
import { getSitesCells } from "../api";
import { useProjectContext } from "../context/ProjectContext";

const MAX_SELECTED_CELLS = 20000;

export default function SitesCellsList({ isLoading: externalLoading = false, onClose, onRunCoverage }) {
  const [expandedSites, setExpandedSites] = useState(new Set());
  const [searchQuery, setSearchQuery] = useState("");
  const [copiedItem, setCopiedItem] = useState(null);
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const { projectName } = useProjectContext();

  // Selection state
  const [selectedCells, setSelectedCells] = useState(new Set());
  const [selectedSites, setSelectedSites] = useState(new Set());

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const data = await getSitesCells(projectName, true, {});
        setData(data);
      } catch (error) {
        console.error("Error fetching sites/cells:", error);
        toast.error("Failed to load sites and cells");
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [projectName]);

  const handleCopyToClipboard = async (text, itemId) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedItem(itemId);
      toast.success('Copied to clipboard!');
      setTimeout(() => setCopiedItem(null), 2000);
    } catch (err) {
      toast.error('Failed to copy!');
    }
  };

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

  // Filter sites based on search query
  const filteredSites = useMemo(() => {
    if (!searchQuery.trim()) return data;
    const query = searchQuery.toLowerCase();
    
    return data.filter(site => {
      const siteIdMatch = site?.site_iid 
        ? String(site.site_iid).toLowerCase().includes(query)
        : false;
      
      const locationMatch = 
        (site?.state && String(site.state).toLowerCase().includes(query)) ||
        (site?.address1 && String(site.address1).toLowerCase().includes(query)) ||
        (site?.town && String(site.town).toLowerCase().includes(query));
      
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
      
      return siteIdMatch || locationMatch || cellMatch;
    });
  }, [data, searchQuery]);

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
  const toggleCellSelection = (cellId, siteId) => {
    setSelectedCells(prev => {
      const newSet = new Set(prev);
      if (newSet.has(cellId)) {
        newSet.delete(cellId);
      } else {
        if (newSet.size >= MAX_SELECTED_CELLS) {
          toast.warning(`Maximum ${MAX_SELECTED_CELLS} cells can be selected.`);
          return prev;
        }
        newSet.add(cellId);
      }
      return newSet;
    });

    // Update site selection state based on cells
    const site = data.find(s => s.site_iid === siteId);
    if (site) {
      const cellIds = getAllCellIdsForSite(site);
      const currentlySelected = selectedCells.has(cellId) 
        ? cellIds.filter(id => selectedCells.has(id) && id !== cellId)
        : [...cellIds.filter(id => selectedCells.has(id)), cellId];
      
      setSelectedSites(prev => {
        const newSet = new Set(prev);
        if (currentlySelected.length === cellIds.length) {
          newSet.add(siteId);
        } else {
          newSet.delete(siteId);
        }
        return newSet;
      });
    }
  };

  // Toggle site selection (selects/deselects all cells in site)
  const toggleSiteSelection = (site) => {
    const cellIds = getAllCellIdsForSite(site);
    const isFullySelected = isSiteFullySelected(site);

    if (!isFullySelected) {
      const additionalCount = cellIds.filter(id => !selectedCells.has(id)).length;
      if (selectedCells.size + additionalCount > MAX_SELECTED_CELLS) {
        toast.warning(`Selecting this site would exceed the ${MAX_SELECTED_CELLS} cell limit (current: ${selectedCells.size}, site adds: ${additionalCount}).`);
        return;
      }
    }

    setSelectedCells(prev => {
      const newSet = new Set(prev);
      if (isFullySelected) {
        cellIds.forEach(id => newSet.delete(id));
      } else {
        cellIds.forEach(id => newSet.add(id));
      }
      return newSet;
    });

    setSelectedSites(prev => {
      const newSet = new Set(prev);
      if (isFullySelected) {
        newSet.delete(site.site_iid);
      } else {
        newSet.add(site.site_iid);
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
      setSelectedCells(new Set());
      setSelectedSites(new Set());
    } else {
      const allCellIds = filteredSites.flatMap(site => getAllCellIdsForSite(site));
      if (allCellIds.length > MAX_SELECTED_CELLS) {
        toast.warning(`Cannot select all — ${allCellIds.length} cells exceeds the ${MAX_SELECTED_CELLS} limit. Use search to narrow down.`);
        return;
      }
      const allSiteIds = filteredSites.map(site => site.site_iid).filter(Boolean);
      setSelectedCells(new Set(allCellIds));
      setSelectedSites(new Set(allSiteIds));
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

  // Generate query string
  const generateQueryString = () => {
    const cellIds = Array.from(selectedCells);
    return `I want to run coverage for cells= [${cellIds.join(', ')}]`;
  };

  // Copy query to clipboard
  const handleCopyQuery = async () => {
    if (selectedCells.size === 0) {
      toast.warning('Please select at least one cell');
      return;
    }
    const query = generateQueryString();
    try {
      await navigator.clipboard.writeText(query);
      toast.success('Query copied to clipboard!');
    } catch (err) {
      toast.error('Failed to copy query!');
    }
  };

  // Run coverage
  const handleRunCoverage = () => {
    if (selectedCells.size === 0) {
      toast.warning('Please select at least one cell');
      return;
    }
    const cellIds = Array.from(selectedCells);
    onRunCoverage?.(cellIds);
  };

  const isActuallyLoading = loading || externalLoading;

  return (
    <div className="absolute top-0 left-0 right-0 bottom-0 min-h-screen z-[5000000] min-w-screen bg-white/20">
    <div className="fixed inset-0 z-50 flex items-center justify-center backdrop-blur-[2px] bg-black/40">
      <div className="w-[650px] max-h-[80vh] bg-card border border-border rounded-xl shadow-2xl shadow-black/50 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-border bg-secondary/50">
        <div className="flex items-center gap-2">
          <Building2 className="w-4 h-4 text-primary" />
          <h3 className="text-sm font-semibold text-foreground">Select Cells</h3>
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

      {/* Search & Selection Controls */}
      <div className="p-3 border-b border-border bg-card/50 space-y-3">
        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search sites, cells, state, town..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-4 py-2 text-sm border border-border rounded-lg bg-secondary text-foreground placeholder-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary/50"
          />
        </div>

        {/* Selection Controls */}
        <div className="flex items-center justify-between">
          {/* <button
            onClick={toggleSelectAll}
            className="flex items-center gap-2 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-accent rounded-lg transition-colors"
          >
            {isAllSelected ? (
              <CheckSquare className="w-4 h-4 text-teoco-real-blue" />
            ) : (
              <Square className="w-4 h-4" />
            )}
            <span>{isAllSelected ? 'Deselect All' : 'Select All'}</span>
          </button> */}
          
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
      <div className="flex-1 overflow-y-auto p-2 scrollbar-thin scrollbar-thumb-muted scrollbar-track-transparent">
        {isActuallyLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-6 h-6 text-primary animate-spin" />
            <span className="ml-2 text-muted-foreground text-sm">Loading sites and cells...</span>
          </div>
        ) : filteredSites.length === 0 ? (
          <div className="py-8 text-center">
            <p className="text-sm text-muted-foreground">
              {searchQuery ? "No sites or cells found matching your search" : "No sites found in the database."}
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
                      </div>
                      <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                        {site.state && (
                          <span className="text-xs text-muted-foreground">{site.state}</span>
                        )}
                        {site.town && (
                          <span className="text-xs text-muted-foreground">• {site.town}</span>
                        )}
                      </div>
                    </div>

                    {/* Copy Site ID */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleCopyToClipboard(site.site_iid, `site-${site.site_iid}`);
                      }}
                      className="p-1 hover:bg-accent rounded transition-colors"
                      title="Copy site ID"
                    >
                      {copiedItem === `site-${site.site_iid}` ? (
                        <Check className="w-3.5 h-3.5 text-green-400" />
                      ) : (
                        <Copy className="w-3.5 h-3.5 text-muted-foreground" />
                      )}
                    </button>
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
                          onClick={() => toggleCellSelection(cell.cell_iid, site.site_iid)}
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
                            <div className="flex items-center gap-2">
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
                            </div>
                          </div>

                          {/* Copy Cell ID */}
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleCopyToClipboard(cell.cell_iid, `cell-${cell.cell_iid}`);
                            }}
                            className="p-1 hover:bg-accent rounded transition-colors"
                            title="Copy cell ID"
                          >
                            {copiedItem === `cell-${cell.cell_iid}` ? (
                              <Check className="w-3 h-3 text-green-400" />
                            ) : (
                              <Copy className="w-3 h-3 text-muted-foreground" />
                            )}
                          </button>
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
              ? `${selectedCells.size} cell${selectedCells.size !== 1 ? 's' : ''} ready`
              : 'Select cells to continue'
            }
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-2">
            <button
              onClick={handleCopyQuery}
              disabled={selectedCells.size === 0}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
                selectedCells.size > 0
                  ? 'bg-secondary text-foreground hover:bg-accent border border-border'
                  : 'bg-muted text-muted-foreground cursor-not-allowed border border-border'
              }`}
            >
              <Copy className="w-4 h-4" />
              Copy Query
            </button>
            <button
              onClick={handleRunCoverage}
              disabled={selectedCells.size === 0}
              className={`flex items-center gap-2 px-4 py-1.5 rounded-lg text-sm font-medium transition-all ${
                selectedCells.size > 0
                  ? 'bg-primary text-primary-foreground hover:bg-primary/90 shadow-lg shadow-primary/20'
                  : 'bg-muted text-muted-foreground cursor-not-allowed'
              }`}
            >
              <Play className="w-4 h-4" />
              Run Coverage
            </button>
          </div>
        </div>
      </div>
      </div>
    </div>
    </div>
  );
}
