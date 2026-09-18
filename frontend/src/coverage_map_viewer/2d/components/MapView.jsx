/**
 * MapView Component
 *
 * Renders a single OpenLayers map instance.
 * In single mode: one MapView shows all raster layers.
 * In split mode: each MapView shows one assigned raster layer.
 *
 * All MapView instances share the same ol/View for synchronized pan/zoom.
 * Cells and polygon overlays use shared VectorSources.
 */

import React, { useEffect, useRef, useState } from 'react';
import Map from 'ol/Map';
import TileLayer from 'ol/layer/Tile';
import OSM from 'ol/source/OSM';
import VectorLayer from 'ol/layer/Vector';
import WebGLVectorLayer from 'ol/layer/WebGLVector';
import ImageLayer from 'ol/layer/Image';
import { Style, Stroke, Fill } from 'ol/style';
import { useMapContext } from '../context/MapContext';
import { getCellIndexInAzimuthGroup } from '../cells/cellGeometry';
import { useRasterCursor } from '../hooks/useRasterCursor';

function MapView({ mapId = 'single', assignedLayerIds = null, title = null }) {
  const containerRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const cellsLayerLocalRef = useRef(null);
  const polygonLayerLocalRef = useRef(null);
  const [mapReady, setMapReady] = useState(false);

  const {
    sharedViewRef,
    registerMap,
    unregisterMap,
    mapsByIdRef,
    viewMode,
    setActiveMapId,
    setCoordinates,
    setCursorValues,
    rasterDataRef,
    rasterLayers,
    cellsVectorSourceRef,
    cellsLayerVisible,
    cellsSourceReady,
    setSelectedCellInfo,
    polygonSourceRef,
    activePolygonId,
  } = useMapContext();

  const rasterLayersRef = useRef(rasterLayers);
  useEffect(() => {
    rasterLayersRef.current = rasterLayers;
  }, [rasterLayers]);

  const { handlePointerMove, handlePointerOut } = useRasterCursor({
    rasterDataRef,
    rasterLayersRef,
    setCoordinates,
    setCursorValues,
    setActiveMapId,
    mapId,
  });

  // ─── Create map on mount ───
  useEffect(() => {
    if (!containerRef.current || mapInstanceRef.current) return;

    const osmLayer = new TileLayer({ source: new OSM(), zIndex: 0 });

    const map = new Map({
      target: containerRef.current,
      layers: [osmLayer],
      view: sharedViewRef.current,
      controls: [],
    });

    mapInstanceRef.current = map;
    registerMap(mapId, map);
    setMapReady(true);

    map.on('pointermove', (evt) => {
      handlePointerMove(evt);

      // // Cells cursor change
      // if (!evt.dragging && cellsLayerLocalRef.current) {
      //   const feature = map.forEachFeatureAtPixel(
      //     evt.pixel,
      //     (f) => f,
      //     { layerFilter: (l) => l === cellsLayerLocalRef.current }
      //   );
      //   map.getTargetElement().style.cursor = feature ? 'pointer' : '';
      // }
    });

    map.on('pointerout', handlePointerOut);

    // ── Cell click handler ──
    // Collect all features at pixel and prefer the smallest (innermost) cell
    // so stacked ring-sectors don't make inner bands un-clickable.
    map.on('click', (evt) => {
      if (!cellsLayerLocalRef.current) return;

      const hits = [];
      map.forEachFeatureAtPixel(
        evt.pixel,
        (f) => { hits.push(f); },
        { layerFilter: (l) => l === cellsLayerLocalRef.current }
      );
      if (hits.length === 0) return;

      const siteHit = hits.find((f) => f.get('featureType') === 'site');
      const cellHits = hits.filter((f) => f.get('featureType') === 'cell');

      let feature;
      if (cellHits.length > 0) {
        feature = cellHits.reduce((smallest, f) => {
          const areaA = smallest.getGeometry().getArea();
          const areaB = f.getGeometry().getArea();
          return areaB < areaA ? f : smallest;
        });
      } else {
        feature = siteHit || hits[0];
      }

      const featureType = feature.get('featureType');
      if (featureType === 'cell') {
        const cellData = feature.get('cellData');
        const siteData = feature.get('siteData');
        const cellsByAzimuth = feature.get('cellsByAzimuth');
        const { index, total } = getCellIndexInAzimuthGroup(cellData, cellsByAzimuth);
        setSelectedCellInfo({
          type: 'cell',
          cell: cellData,
          site: siteData,
          layerIndex: index + 1,
          layerTotal: total,
        });
      } else if (featureType === 'azimuthSummary') {
        setSelectedCellInfo({
          type: 'site',
          site: feature.get('siteData'),
        });
      } else if (featureType === 'site') {
        setSelectedCellInfo({
          type: 'site',
          site: feature.get('siteData'),
        });
      }
    });

    return () => {
      const layers = [...map.getLayers().getArray()];
      layers.forEach((l) => {
        if (!(l instanceof TileLayer)) {
          map.removeLayer(l);
        }
      });

      unregisterMap(mapId);
      map.setTarget(null);
      mapInstanceRef.current = null;
      cellsLayerLocalRef.current = null;
      polygonLayerLocalRef.current = null;
      setMapReady(false);
    };
  }, [mapId]);

  // ─── Attach/detach raster layers ───
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !mapReady) return;

    const layersForThisMap = assignedLayerIds
      ? rasterLayers.filter((l) => assignedLayerIds.includes(l.id))
      : rasterLayers;

    const currentImageLayers = map
      .getLayers()
      .getArray()
      .filter((l) => l instanceof ImageLayer);

    currentImageLayers.forEach((olLayer) => {
      const isNeeded = layersForThisMap.some((l) => l.layer === olLayer);
      if (!isNeeded) map.removeLayer(olLayer);
    });

    layersForThisMap.forEach((layerData) => {
      if (!map.getLayers().getArray().includes(layerData.layer)) {
        mapsByIdRef.current.forEach((otherMap, otherId) => {
          if (otherId !== mapId && otherMap.getLayers().getArray().includes(layerData.layer)) {
            otherMap.removeLayer(layerData.layer);
          }
        });
        map.addLayer(layerData.layer);
      }
    });
  }, [rasterLayers, assignedLayerIds, mapId, viewMode, mapReady]);

  // ─── Cells VectorLayer ───
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !cellsVectorSourceRef.current) return;

    if (cellsLayerLocalRef.current) {
      map.removeLayer(cellsLayerLocalRef.current);
    }

    const layer = new WebGLVectorLayer({
      source: cellsVectorSourceRef.current,
      zIndex: 100,
      visible: cellsLayerVisible,
      style: [
        {
          filter: ['==', ['get', 'featureType'], 'cell'],
          style: {
            'fill-color': ['get', 'renderFillColor'],
            'stroke-color': ['get', 'renderStrokeColor'],
            'stroke-width': ['get', 'renderStrokeWidth'],
          },
        },
        {
          filter: ['==', ['get', 'featureType'], 'azimuthSummary'],
          style: {
            'fill-color': ['get', 'renderFillColor'],
            'stroke-color': ['get', 'renderStrokeColor'],
            'stroke-width': ['get', 'renderStrokeWidth'],
          },
        },
        {
          filter: ['==', ['get', 'featureType'], 'site'],
          style: {
            'circle-radius': ['get', 'renderPointRadius'],
            'circle-fill-color': ['get', 'renderFillColor'],
            'circle-stroke-color': ['get', 'renderStrokeColor'],
            'circle-stroke-width': ['get', 'renderStrokeWidth'],
          },
        },
      ],
    });

    cellsLayerLocalRef.current = layer;
    map.addLayer(layer);

    return () => {
      if (mapInstanceRef.current && cellsLayerLocalRef.current) {
        mapInstanceRef.current.removeLayer(cellsLayerLocalRef.current);
        cellsLayerLocalRef.current = null;
      }
    };
  }, [cellsSourceReady]);

  useEffect(() => {
    if (cellsLayerLocalRef.current) {
      cellsLayerLocalRef.current.setVisible(cellsLayerVisible);
    }
  }, [cellsLayerVisible]);

  // ─── Polygon VectorLayer ───
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !polygonSourceRef.current) return;

    const layer = new VectorLayer({
      source: polygonSourceRef.current,
      zIndex: 101,
    });

    polygonLayerLocalRef.current = layer;
    map.addLayer(layer);

    return () => {
      if (mapInstanceRef.current && polygonLayerLocalRef.current) {
        mapInstanceRef.current.removeLayer(polygonLayerLocalRef.current);
        polygonLayerLocalRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    if (!polygonLayerLocalRef.current) return;
    polygonLayerLocalRef.current.setStyle((feature) => {
      const isActive = feature.get('id') === activePolygonId;
      if (!isActive) {
        return new Style({
          stroke: new Stroke({ color: 'transparent', width: 0 }),
          fill: new Fill({ color: 'transparent' }),
        });
      }
      return new Style({
        stroke: new Stroke({ color: '#6B7280', width: 2 }),
        fill: new Fill({ color: 'rgba(156, 163, 175, 0.5)' }),
      });
    });
  }, [activePolygonId]);

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      {title && (
        <div
          style={{
            position: 'absolute',
            top: 8,
            left: '50%',
            transform: 'translateX(-50%)',
            zIndex: 10,
            background: 'rgba(0, 0, 0, 0.7)',
            color: 'white',
            padding: '4px 12px',
            borderRadius: '6px',
            fontSize: '12px',
            fontWeight: 500,
            whiteSpace: 'nowrap',
            pointerEvents: 'none',
          }}
        >
          {title}
        </div>
      )}
      <div
        className="map-container"
        ref={containerRef}
        style={{ width: '100%', height: '100%' }}
      />
    </div>
  );
}

export default MapView;
