import { useState, useCallback, useMemo, useRef } from 'react';
import {
  getSitesCells,
  getProjectCords,
  getUserProjectConfig,
  upsertUserProjectConfig,
  getCellsInPolygon,
} from '../../api';
import { ensureClosedRing } from './projectConfigTransform';

export const MAX_SELECTED_CELLS = 20000;
export const MAX_POLYGON_AREA = 500000; // km^2

/**
 * Custom hook encapsulating all state + logic for the Project Config modal.
 *
 * Returns:
 *  - allSites, projectCords, polygonCoords, loading, saving, error
 *  - selectedForMap (derived, identity-stable per site)
 *  - selectedCellIids (derived)
 *  - init(projectName)
 *  - applyPolygon(ring)
 *  - syncPolygonSelection()
 *  - clearPolygon()
 *  - clearSelections()
 *  - toggleCell(site_iid, cell_iid)
 *  - toggleSite(site_iid)
 *  - replaceSelectionFromCsv(cellIidStrings) → { matched, ignored, total }
 *  - save()
 */
export function useProjectConfigState() {
  const [allSites, setAllSites] = useState([]);
  const [projectCords, setProjectCords] = useState(null);
  const [polygonCoords, setPolygonCoords] = useState(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [configEmail, setConfigEmail] = useState('');
  const [error, setErrorRaw] = useState(null);
  const projectNameRef = useRef('');
  const errorTimerRef = useRef(null);

  const setError = useCallback((msg) => {
    if (errorTimerRef.current) clearTimeout(errorTimerRef.current);
    setErrorRaw(msg);
    if (msg) {
      errorTimerRef.current = setTimeout(() => setErrorRaw(null), 5000);
    }
  }, []);

  // O(1) selected-count tracking — avoids full scans on each toggle
  const selectedCountRef = useRef(0);

  // Cache for selectedForMap to preserve identity for unchanged sites
  const selectedForMapCacheRef = useRef(new Map());

  // ---------- derived ----------

  const selectedForMap = useMemo(() => {
    const cache = selectedForMapCacheRef.current;
    const nextCache = new Map();
    const result = [];

    for (let i = 0; i < allSites.length; i++) {
      const site = allSites[i];
      const cells = site.cells || [];
      let hasSelected = false;
      for (let j = 0; j < cells.length; j++) {
        if (cells[j].selected) { hasSelected = true; break; }
      }
      if (!hasSelected) continue;

      const cached = cache.get(site.site_iid);
      if (cached && cached.siteRef === site) {
        nextCache.set(site.site_iid, cached);
        result.push(cached.entry);
      } else {
        const selectedCells = [];
        for (let j = 0; j < cells.length; j++) {
          if (cells[j].selected) selectedCells.push(cells[j]);
        }
        const entry = { ...site, cells: selectedCells };
        nextCache.set(site.site_iid, { siteRef: site, entry });
        result.push(entry);
      }
    }

    selectedForMapCacheRef.current = nextCache;
    return result;
  }, [allSites]);

  const selectedCellIids = useMemo(() => {
    const iids = [];
    for (let i = 0; i < allSites.length; i++) {
      const cells = allSites[i].cells || [];
      for (let j = 0; j < cells.length; j++) {
        if (cells[j].selected) iids.push(cells[j].cell_iid);
      }
    }
    return iids;
  }, [allSites]);

  // ---------- helpers ----------

  /** Mark a set of cell_iids as selected in allSites (unselect rest).
   *  Preserves object identity for sites/cells whose selected flag doesn't change. */
  const applySelection = useCallback((cellIidsSet) => {
    setAllSites(prev => {
      let changed = false;
      let newCount = 0;
      const next = prev.map(site => {
        const cells = site.cells || [];
        let siteChanged = false;
        const nextCells = cells.map(cell => {
          const shouldSelect = cellIidsSet.has(cell.cell_iid) || cellIidsSet.has(String(cell.cell_iid));
          if (shouldSelect) newCount++;
          if (cell.selected === shouldSelect) return cell;
          siteChanged = true;
          return { ...cell, selected: shouldSelect };
        });
        if (!siteChanged) return site;
        changed = true;
        return { ...site, cells: nextCells };
      });
      selectedCountRef.current = newCount;
      return changed ? next : prev;
    });
  }, []);

  const configEmailRef = useRef('');

  // ---------- init: load project data (sites + cords) and saved config ----------
  // When email is provided (admin flow) the GET uses that email as a query param.
  // When omitted (normal/readOnly flow) the backend falls back to the auth token email.
  const init = useCallback(async (projectName, email) => {
    projectNameRef.current = projectName;
    configEmailRef.current = email || '';
    setLoading(true);
    setError(null);
    setPolygonCoords(null);

    try {
      const [allSitesData, cordsData, savedConfig] = await Promise.all([
        getSitesCells(projectName).catch(err => { console.error('getSitesCells', err); return []; }),
        getProjectCords(projectName).catch(err => { console.error('getProjectCords', err); return []; }),
        getUserProjectConfig(projectName, email || undefined).catch(() => null),
      ]);

      const normalised = (allSitesData || []).map(site => ({
        ...site,
        cells: (site.cells || []).map(cell => ({
          ...cell,
          selected: false,
        })),
      }));
      selectedCountRef.current = 0;

      setAllSites(normalised);
      setProjectCords(cordsData && cordsData.length >= 3 ? cordsData : null);

      if (savedConfig) {
        if (savedConfig.cords && savedConfig.cords.length >= 3) {
          const ring = ensureClosedRing(savedConfig.cords);
          setPolygonCoords(ring);
        }
        if (savedConfig.cell_iids && savedConfig.cell_iids.length > 0) {
          const cellIidsSet = new Set(savedConfig.cell_iids.map(String));
          const next = normalised.map(site => {
            const cells = site.cells || [];
            let siteChanged = false;
            const nextCells = cells.map(cell => {
              const shouldSelect = cellIidsSet.has(String(cell.cell_iid));
              if (!shouldSelect) return cell;
              siteChanged = true;
              return { ...cell, selected: true };
            });
            return siteChanged ? { ...site, cells: nextCells } : site;
          });
          let cnt = 0;
          next.forEach(s => (s.cells || []).forEach(c => { if (c.selected) cnt++; }));
          selectedCountRef.current = cnt;
          setAllSites(next);
        }
        setConfigEmail(savedConfig.email || email || '');
      } else {
        setConfigEmail(email || '');
      }
    } catch (e) {
      console.error('ProjectConfig init error:', e);
      setError(e.message || 'Failed to load project config');
    } finally {
      setLoading(false);
    }
  }, []);

  // ---------- polygon from user draw ----------
  const applyPolygon = useCallback((ring) => {
    if (!ring || ring.length < 3) return;
    const closed = ensureClosedRing(ring);
    setPolygonCoords(closed);
    setError(null);
  }, []);

  // ---------- sync selection with polygon (via backend spatial query) ----------
  const syncPolygonSelection = useCallback(async () => {
    if (!polygonCoords || polygonCoords.length < 3) return { applied: false, matched: 0 };
    setSyncing(true);
    try {
      const cellIids = await getCellsInPolygon(polygonCoords, projectNameRef.current);
      const cellIidsSet = new Set((cellIids || []).map(String));

      if (cellIidsSet.size > MAX_SELECTED_CELLS) {
        setError(`Polygon selects ${cellIidsSet.size} cells — maximum is ${MAX_SELECTED_CELLS}. Draw a smaller polygon.`);
        return { applied: false, matched: cellIidsSet.size };
      }
      setError(null);
      applySelection(cellIidsSet);
      return { applied: true, matched: cellIidsSet.size };
    } catch (e) {
      console.error('syncPolygonSelection error:', e);
      setError('Failed to sync cells by polygon');
      return { applied: false, matched: 0 };
    } finally {
      setSyncing(false);
    }
  }, [polygonCoords, applySelection]);

  // ---------- clear polygon ----------
  const clearPolygon = useCallback(() => {
    setPolygonCoords(null);
    setError(null);
  }, []);

  // ---------- clear cell selections ----------
  const clearSelections = useCallback(() => {
    setAllSites(prev => {
      let changed = false;
      const next = prev.map(site => {
        const cells = site.cells || [];
        let anySelected = false;
        for (let j = 0; j < cells.length; j++) {
          if (cells[j].selected) { anySelected = true; break; }
        }
        if (!anySelected) return site;
        changed = true;
        return {
          ...site,
          cells: cells.map(cell => cell.selected ? { ...cell, selected: false } : cell),
        };
      });
      if (changed) selectedCountRef.current = 0;
      return changed ? next : prev;
    });
    setError(null);
  }, []);

  // ---------- toggle cell ----------
  const toggleCell = useCallback((siteIid, cellIid) => {
    const currentCount = selectedCountRef.current;
    setAllSites(prev => {
      const target = prev.find(s => s.site_iid === siteIid);
      const targetCell = target && (target.cells || []).find(c => c.cell_iid === cellIid);
      const isSelecting = targetCell && !targetCell.selected;
      if (isSelecting && currentCount >= MAX_SELECTED_CELLS) {
        setError(`Maximum ${MAX_SELECTED_CELLS} cells can be selected.`);
        return prev;
      }
      setError(null);
      selectedCountRef.current = currentCount + (isSelecting ? 1 : -1);
      return prev.map(site => {
        if (site.site_iid !== siteIid) return site;
        return {
          ...site,
          cells: (site.cells || []).map(cell =>
            cell.cell_iid === cellIid ? { ...cell, selected: !cell.selected } : cell,
          ),
        };
      });
    });
  }, []);

  // ---------- toggle site ----------
  const toggleSite = useCallback((siteIid) => {
    const currentCount = selectedCountRef.current;
    setAllSites(prev => {
      const target = prev.find(s => s.site_iid === siteIid);
      if (!target) return prev;
      const cells = target.cells || [];
      const allSelected = cells.length > 0 && cells.every(c => c.selected);
      if (!allSelected) {
        let additionalCount = 0;
        for (let i = 0; i < cells.length; i++) {
          if (!cells[i].selected) additionalCount++;
        }
        if (currentCount + additionalCount > MAX_SELECTED_CELLS) {
          setError(`Selecting this site would exceed the ${MAX_SELECTED_CELLS} cell limit (current: ${currentCount}, site adds: ${additionalCount}).`);
          return prev;
        }
      }
      setError(null);
      const newVal = !allSelected;
      let delta = 0;
      for (let i = 0; i < cells.length; i++) {
        if (cells[i].selected !== newVal) delta += newVal ? 1 : -1;
      }
      selectedCountRef.current = currentCount + delta;
      return prev.map(site => {
        if (site.site_iid !== siteIid) return site;
        return {
          ...site,
          cells: cells.map(cell => cell.selected === newVal ? cell : { ...cell, selected: newVal }),
        };
      });
    });
  }, []);

  // ---------- replace selection from CSV ----------
  const replaceSelectionFromCsv = useCallback((cellIidStrings) => {
    const csvSet = new Set(cellIidStrings.map(String));

    const availableIids = new Set();
    allSites.forEach(s =>
      (s.cells || []).forEach(c => availableIids.add(String(c.cell_iid))),
    );

    const matchedIids = new Set();
    csvSet.forEach(id => {
      if (availableIids.has(id)) matchedIids.add(id);
    });

    const ignored = csvSet.size - matchedIids.size;

    if (matchedIids.size > MAX_SELECTED_CELLS) {
      setError(
        `CSV matches ${matchedIids.size} cells — maximum is ${MAX_SELECTED_CELLS}. Reduce the CSV and try again.`,
      );
      return { matched: matchedIids.size, ignored, total: csvSet.size, applied: false };
    }

    setError(null);
    applySelection(matchedIids);
    return { matched: matchedIids.size, ignored, total: csvSet.size, applied: true };
  }, [allSites, applySelection]);

  // ---------- save ----------
  const save = useCallback(async (emailOverride) => {
    setSaving(true);
    setError(null);
    try {
      await upsertUserProjectConfig({
        projectName: projectNameRef.current,
        email: emailOverride || configEmailRef.current || undefined,
        cords: polygonCoords || [],
        cellIids: selectedCellIids,
      });
    } catch (e) {
      console.error('save error:', e);
      setError('Failed to save project config');
      throw e;
    } finally {
      setSaving(false);
    }
  }, [polygonCoords, selectedCellIids]);


  return {
    allSites,
    projectCords,
    polygonCoords,
    loading,
    saving,
    syncing,
    error,
    configEmail,
    setConfigEmail,
    selectedForMap,
    selectedCellIids,
    setError,
    init,
    applyPolygon,
    syncPolygonSelection,
    clearPolygon,
    clearSelections,
    toggleCell,
    toggleSite,
    replaceSelectionFromCsv,
    save,
  };
}
export function getPolygonCentroid(coords) {
  if (!coords || coords.length < 3) return null;
  
  let centroidLon = 0, centroidLat = 0;
  coords.forEach(([lon, lat]) => {
    centroidLon += lon;
    centroidLat += lat;
  });
  
  return [
    centroidLon / coords.length,
    centroidLat / coords.length
  ];
}
export function getPolygonAreaKm2(coords) {
  if (!coords || coords.length < 3) return 0;
  
  // Get centroid for latitude correction
  const centroid = getPolygonCentroid(coords);
  const latRad = centroid[1] * Math.PI / 180;
  
  // Convert to approximate km coordinates
  const kmPerDegreeLat = 111;
  const kmPerDegreeLon = 111 * Math.cos(latRad);
  
  // Calculate signed area in km²
  let area = 0;
  const n = coords.length;
  
  for (let i = 0; i < n; i++) {
    const j = (i + 1) % n;
    const xi = coords[i][0] * kmPerDegreeLon;
    const yi = coords[i][1] * kmPerDegreeLat;
    const xj = coords[j][0] * kmPerDegreeLon;
    const yj = coords[j][1] * kmPerDegreeLat;
    
    area += xi * yj;
    area -= xj * yi;
  }
  
  return Math.abs(area / 2);
}
