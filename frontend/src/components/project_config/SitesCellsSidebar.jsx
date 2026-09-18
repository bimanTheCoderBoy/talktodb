import React, { useState, useMemo, useCallback, useRef, useEffect } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import {
  Search, Building2, ChevronDown, ChevronRight, Signal,
} from 'lucide-react';

const CellRow = React.memo(function CellRow({ cell, siteId, onToggleCell, disabled }) {
  const handleRowClick = useCallback(() => {
    if (!disabled) onToggleCell(siteId, cell.cell_iid);
  }, [disabled, onToggleCell, siteId, cell.cell_iid]);

  const handleCheckboxChange = useCallback(() => {
    onToggleCell(siteId, cell.cell_iid);
  }, [onToggleCell, siteId, cell.cell_iid]);

  const handleCheckboxClick = useCallback((e) => e.stopPropagation(), []);

  return (
    <div className="ml-7 mr-2 pl-2 border-l border-border">
      <div
        onClick={handleRowClick}
        className={`flex items-center gap-2 p-2 rounded-lg cursor-pointer transition-all ${
          cell.selected
            ? 'bg-primary/10 border border-primary/30'
            : 'hover:bg-accent/50 border border-transparent'
        }`}
      >
        <input
          type="checkbox"
          checked={!!cell.selected}
          onChange={handleCheckboxChange}
          disabled={disabled}
          onClick={handleCheckboxClick}
          className="w-3.5 h-3.5 text-primary bg-secondary border-border rounded accent-primary cursor-pointer disabled:opacity-50"
        />
        <Signal className={`w-3.5 h-3.5 ${cell.selected ? 'text-primary' : 'text-muted-foreground'}`} />
        <div className="flex-1 min-w-0">
          <div className={`text-xs font-medium truncate ${cell.selected ? 'text-foreground' : 'text-muted-foreground'}`}>
            {cell.cell_iid}
          </div>
          <div className="flex items-center gap-2 mt-0.5 flex-wrap">
            {cell.band && (
              <span className="px-1.5 py-0.5 text-[10px] bg-secondary text-muted-foreground rounded">{cell.band}</span>
            )}
            {cell.azimuth != null && (
              <span className="text-[10px] text-muted-foreground">Az: {cell.azimuth}°</span>
            )}
            {cell.technology && (
              <span className="text-[10px] text-muted-foreground">{cell.technology}</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
});

const SiteHeader = React.memo(function SiteHeader({ site, isExpanded, toggleExpand, onToggleSite, disabled }) {
  const cells = site.cells || [];

  const selectedCount = useMemo(() => {
    let count = 0;
    for (let i = 0; i < cells.length; i++) {
      if (cells[i].selected) count++;
    }
    return count;
  }, [cells]);

  const allSelected = cells.length > 0 && selectedCount === cells.length;
  const someSelected = selectedCount > 0 && !allSelected;
  const hasSelected = selectedCount > 0;

  const handleExpandClick = useCallback(() => {
    toggleExpand(site.site_iid);
  }, [toggleExpand, site.site_iid]);

  const handleSiteToggle = useCallback(() => {
    onToggleSite(site.site_iid);
  }, [onToggleSite, site.site_iid]);

  const setIndeterminate = useCallback((el) => {
    if (el) el.indeterminate = someSelected;
  }, [someSelected]);

  return (
    <div
      className={`border-b border-border transition-colors ${
        hasSelected ? 'bg-primary/10' : ''
      }`}
    >
      <div className={`p-2.5 hover:bg-accent/50 cursor-pointer ${
        isExpanded ? 'bg-accent/30' : ''
      }`}>
        <div className="flex items-center gap-2">
          <button
            onClick={handleExpandClick}
            className="p-1 hover:bg-accent rounded transition-colors"
          >
            {isExpanded
              ? <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" />
              : <ChevronRight className="w-3.5 h-3.5 text-muted-foreground" />
            }
          </button>
          <input
            type="checkbox"
            checked={allSelected}
            ref={setIndeterminate}
            onChange={handleSiteToggle}
            disabled={disabled}
            className="w-4 h-4 text-primary bg-secondary border-border rounded accent-primary cursor-pointer disabled:opacity-50"
          />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-foreground truncate">{site.site_iid}</span>
              {hasSelected && (
                <span className={`px-1.5 py-0.5 text-[10px] font-medium rounded-full ${
                  allSelected
                    ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                    : 'bg-primary/20 text-primary border border-primary/30'
                }`}>
                  {selectedCount}/{cells.length}
                </span>
              )}
            </div>
            <div className="text-[10px] text-muted-foreground mt-0.5">
              {cells.length} cell{cells.length !== 1 ? 's' : ''}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
});

/**
 * Pure-UI sidebar listing sites & cells with checkboxes.
 * Uses TanStack Virtual for large datasets — flattens sites + expanded cells
 * into a single virtualized list so only visible rows mount.
 *
 * Props:
 *  - allSites        : [{ site_iid, cells: [{ cell_iid, selected, band, azimuth, technology }], ... }]
 *  - onToggleCell     : (site_iid, cell_iid) => void
 *  - onToggleSite     : (site_iid) => void
 *  - disabled         : boolean
 */
function SitesCellsSidebar({ allSites = [], onToggleCell, onToggleSite, disabled = false }) {
  const [searchInput, setSearchInput] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [expandedSites, setExpandedSites] = useState(new Set());
  const parentRef = useRef(null);

  // Debounce search so filtering doesn't run on every keystroke
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(searchInput), 250);
    return () => clearTimeout(timer);
  }, [searchInput]);

  const toggleExpand = useCallback((siteId) => {
    setExpandedSites(prev => {
      const next = new Set(prev);
      next.has(siteId) ? next.delete(siteId) : next.add(siteId);
      return next;
    });
  }, []);

  const { totalCells, selectedCells, selectedSites } = useMemo(() => {
    let total = 0, sel = 0, sSites = 0;
    for (let i = 0; i < allSites.length; i++) {
      const cells = allSites[i].cells || [];
      total += cells.length;
      let siteHasSelected = false;
      for (let j = 0; j < cells.length; j++) {
        if (cells[j].selected) { sel++; siteHasSelected = true; }
      }
      if (siteHasSelected) sSites++;
    }
    return { totalCells: total, selectedCells: sel, selectedSites: sSites };
  }, [allSites]);

  const filteredSites = useMemo(() => {
    if (!debouncedSearch.trim()) return allSites;
    const q = debouncedSearch.toLowerCase();
    return allSites.filter(site => {
      if (String(site.site_iid).toLowerCase().includes(q)) return true;
      const cells = site.cells || [];
      for (let i = 0; i < cells.length; i++) {
        if (String(cells[i].cell_iid).toLowerCase().includes(q)) return true;
        if (cells[i].band && String(cells[i].band).toLowerCase().includes(q)) return true;
      }
      return false;
    });
  }, [allSites, debouncedSearch]);

  // Flatten sites + expanded cells into a single virtual list
  const flatRows = useMemo(() => {
    const rows = [];
    for (let i = 0; i < filteredSites.length; i++) {
      const site = filteredSites[i];
      if (!site || !site.site_iid) continue;
      rows.push({ type: 'site', site });
      if (expandedSites.has(site.site_iid)) {
        const cells = site.cells || [];
        for (let j = 0; j < cells.length; j++) {
          if (cells[j] && cells[j].cell_iid) {
            rows.push({ type: 'cell', cell: cells[j], siteId: site.site_iid });
          }
        }
      }
    }
    return rows;
  }, [filteredSites, expandedSites]);

  const rowVirtualizer = useVirtualizer({
    count: flatRows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: (index) => flatRows[index]?.type === 'site' ? 52 : 44,
    overscan: 12,
    getItemKey: (index) => {
      const row = flatRows[index];
      if (!row) return index;
      return row.type === 'site'
        ? `site:${row.site.site_iid}`
        : `cell:${row.siteId}:${row.cell.cell_iid}`;
    },
  });

  // Reset scroll when search changes
  useEffect(() => {
    if (parentRef.current) parentRef.current.scrollTop = 0;
  }, [debouncedSearch]);

  return (
    <div className="w-80 border-r border-border bg-card flex flex-col h-full">
      {/* Header */}
      <div className="p-3 border-b border-border bg-secondary/50">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-bold text-foreground flex items-center gap-2">
            <Building2 className="w-4 h-4 text-primary" />
            Sites &amp; Cells
          </h3>
          <div className="flex items-center gap-2 text-xs">
            <span className="px-2 py-0.5 bg-primary/20 text-primary rounded-full font-semibold">
              {selectedCells}/{totalCells}
            </span>
            <span className="text-muted-foreground">{selectedSites} sites</span>
          </div>
        </div>
        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search sites or cells..."
            value={searchInput}
            onChange={e => setSearchInput(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 text-sm border border-border rounded-lg bg-secondary text-foreground placeholder-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary/50"
          />
        </div>
      </div>

      {/* List (virtualized) */}
      <div
        ref={parentRef}
        className="flex-1 overflow-y-auto scrollbar-thin scrollbar-thumb-muted scrollbar-track-transparent"
      >
        {flatRows.length === 0 ? (
          <div className="p-8 text-center text-sm text-muted-foreground">No sites found</div>
        ) : (
          <div
            style={{
              height: `${rowVirtualizer.getTotalSize()}px`,
              width: '100%',
              position: 'relative',
            }}
          >
            {rowVirtualizer.getVirtualItems().map(virtualRow => {
              const row = flatRows[virtualRow.index];
              return (
                <div
                  key={virtualRow.key}
                  data-index={virtualRow.index}
                  ref={rowVirtualizer.measureElement}
                  style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    width: '100%',
                    transform: `translateY(${virtualRow.start}px)`,
                  }}
                >
                  {row.type === 'site' ? (
                    <SiteHeader
                      site={row.site}
                      isExpanded={expandedSites.has(row.site.site_iid)}
                      toggleExpand={toggleExpand}
                      onToggleSite={onToggleSite}
                      disabled={disabled}
                    />
                  ) : (
                    <CellRow
                      cell={row.cell}
                      siteId={row.siteId}
                      onToggleCell={onToggleCell}
                      disabled={disabled}
                    />
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

export default React.memo(SitesCellsSidebar);
