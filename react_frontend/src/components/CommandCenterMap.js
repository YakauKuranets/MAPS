// ═══════════════════════════════════════════════════════════════════════════
// ПРОБЛЕМА №3 FIX: Консолидированные импорты из корневых пакетов
// ═══════════════════════════════════════════════════════════════════════════
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import DeckGL from '@deck.gl/react';
import { ColumnLayer, IconLayer, PathLayer, ScatterplotLayer, TextLayer } from '@deck.gl/layers';
import { FlyToInterpolator, WebMercatorViewport } from '@deck.gl/core';
import Map, { Marker } from 'react-map-gl/maplibre';
import { Loader2, Lock, Radar, Search } from 'lucide-react';
import 'maplibre-gl/dist/maplibre-gl.css';

import useMapStore from '../store/useMapStore';
import useMapClusters from '../hooks/useMapClusters';
import { initPmtiles } from '../vendor/pmtilesSetup';
import TacticalGridDashboard from './TacticalGridDashboard';
import { useNotify } from './NotificationProvider';

// ═══════════════════════════════════════════════════════════════════════════
// ПРОБЛЕМА №2 FIX: Все статические объекты ВЫНЕСЕНЫ за пределы компонента
// ═══════════════════════════════════════════════════════════════════════════

const INITIAL_VIEW_STATE = {
  longitude: 27.56, latitude: 53.9, zoom: 14, pitch: 60, bearing: -20, maxPitch: 85,
};
const INITIAL_VIEW_STATE_MOBILE = { ...INITIAL_VIEW_STATE, zoom: 12.5, pitch: 35 };
const MAP_STYLE_PRIMARY = '/map_style_cyberpunk.json';
const MAP_STYLE_FALLBACK = Object.freeze({
  version: 8,
  name: 'Fallback OSM Raster',
  sources: {
    osm: {
      type: 'raster',
      tiles: [
        'https://a.tile.openstreetmap.org/{z}/{x}/{y}.png',
        'https://b.tile.openstreetmap.org/{z}/{x}/{y}.png',
        'https://c.tile.openstreetmap.org/{z}/{x}/{y}.png',
      ],
      tileSize: 256,
      attribution: '© OpenStreetMap contributors',
    },
  },
  layers: [
    { id: 'osm', type: 'raster', source: 'osm' },
  ],
});
const DEFAULT_FILTERS = Object.freeze({
  showAgents: true, showCameras: true, showIncidents: true, showPending: true,
});
const PULSE_INTERVAL_MS = 66; // ~15fps — достаточно для пульсации, щадит Vega 7

const EMPTY_LIST = Object.freeze([]);

initPmtiles();

const toNumber = (v) => { const n = Number(v); return Number.isFinite(n) ? n : null; };
const isViolationAgent = (a) => Boolean(a?.isViolation || a?.violation || a?.in_violation || a?.zone_violation || a?.inside_polygon);
const svgIcon = (fill, stroke = '#ffffff') => `data:image/svg+xml;utf8,${encodeURIComponent(
  `<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64"><circle cx="32" cy="32" r="20" fill="${fill}" stroke="${stroke}" stroke-width="4"/></svg>`)}`;

const ICONS = Object.freeze({
  cluster: { url: svgIcon('#334155', '#e2e8f0'), width: 64, height: 64, anchorY: 32 },
  agent:   { url: svgIcon('#19d3ff', '#78ebff'), width: 64, height: 64, anchorY: 32 },
  danger:  { url: svgIcon('#ef4444', '#fecaca'), width: 64, height: 64, anchorY: 32 },
  incident:{ url: svgIcon('#f59e0b', '#fef3c7'), width: 64, height: 64, anchorY: 32 },
  pending: { url: svgIcon('#fde047', '#fef9c3'), width: 64, height: 64, anchorY: 32 },
  camera:  { url: svgIcon('#a78bfa', '#ddd6fe'), width: 64, height: 64, anchorY: 32 },
  unknown: { url: svgIcon('#64748b', '#cbd5e1'), width: 64, height: 64, anchorY: 32 },
});

// Статичные цвета — не создают массивы в render loop
const C_NEON = [0, 240, 255, 220];
const C_RED = [255, 0, 60, 255];
const C_CYAN = [0, 240, 255, 255];
const C_AMB = [255, 176, 0, 180];
const C_AMBL = [255, 176, 0, 255];
const C_WHITE = [255, 255, 255, 255];

const toActiveNodePayload = (s) => s ? {
  id: s.id ?? s.camera_id ?? s.agent_id ?? null,
  ip: s.ip ?? s.camera_ip ?? s.host ?? null,
  name: s.name ?? s.title ?? s.camera_name ?? s.label ?? null,
  raw: s,
} : null;

const DEVICE_PROPS = Object.freeze({
  powerPreference: 'high-performance',
});

// Стабильные getter-функции
const gPath = (d) => d.path;
const gPathC = () => C_NEON;
const gAPos = (d) => d.coordinates;
const gAFill = () => C_RED;
const gALine = () => C_CYAN;
const gCPos = (d) => d.geometry.coordinates;
const gTPos = (d) => [parseFloat(d.lon), parseFloat(d.lat)];
const gTFill = () => C_AMB;
const gTLine = () => C_AMBL;
const gTElev = () => 150;
const gCText = (d) => String(d.properties.point_count || '');

// ═══════════════════════════════════════════════════════════════════════════

export default function CommandCenterMap({ onUserClick, flyToTarget, filters, setActiveNode, isMobile = false }) {
  const effectiveFilters = filters || DEFAULT_FILTERS;
  const showAgents = effectiveFilters.showAgents;
  const showCameras = effectiveFilters.showCameras;
  const showIncidents = effectiveFilters.showIncidents;
  const showPending = effectiveFilters.showPending;

  const agentsMap = useMapStore((s) => s.agents);
  const trackPointsMap = useMapStore((s) => s.trackPoints);
  const threatsMap = useMapStore((s) => s.threatAlerts);
  const incidents = useMapStore((s) => s.incidents);
  const pendingMarkers = useMapStore((s) => s.pendingMarkers);
  const terminals = useMapStore((s) => s.terminals ?? s.markers ?? EMPTY_LIST);
  const setSelectedObject = useMapStore((s) => s.setSelectedObject);
  const draftMarker = useMapStore((s) => s.draftMarker);
  const addMarker = useMapStore((s) => s.addMarker);
  const clearDraftMarker = useMapStore((s) => s.clearDraftMarker);
  const { addNotify } = useNotify();

  // ═══ ПРОБЛЕМА №2 FIX: Throttled pulse — setInterval @15fps ═══
  const pulseRef = useRef(0);
  const [pulseTick, setPulseTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => {
      pulseRef.current = (pulseRef.current + 1) % 10000;
      setPulseTick(pulseRef.current);
    }, PULSE_INTERVAL_MS);
    return () => clearInterval(id);
  }, []);

  const [activeTerminalId, setActiveTerminal] = useState(null);
  const [isSavingObject, setIsSavingObject] = useState(false);
  const [isDiscovering, setIsDiscovering] = useState(false);
  const [discoveryResult, setDiscoveryResult] = useState(null);
  const [discoveryError, setDiscoveryError] = useState('');
  const [formValues, setFormValues] = useState({
    title: '', address: '', description: '', image: '', host: '', login: '', password: '',
  });
  const [viewState, setViewState] = useState(isMobile ? INITIAL_VIEW_STATE_MOBILE : INITIAL_VIEW_STATE);
  const [viewportSize, setViewportSize] = useState({ width: window.innerWidth, height: window.innerHeight });
  const [mapStyle, setMapStyle] = useState(MAP_STYLE_PRIMARY);
  const [mapStyleFallbackActive, setMapStyleFallbackActive] = useState(false);

  const agentsData = useMemo(() => Object.values(agentsMap || {}), [agentsMap]);
  const trackPointsData = useMemo(() => Object.values(trackPointsMap || {}), [trackPointsMap]);
  const threatsData = useMemo(() => Object.values(threatsMap || {}), [threatsMap]);

  // ═══ ПРОБЛЕМА №2 FIX: flyToTarget — ref предотвращает повторные fly ═══
  const lastFlyRef = useRef(null);
  useEffect(() => {
    if (!flyToTarget) return;
    const { lon, lat } = flyToTarget;
    const p = lastFlyRef.current;
    if (p && p.lon === lon && p.lat === lat) return;
    lastFlyRef.current = { lon, lat };
    setViewState((vs) => ({
      ...vs, longitude: lon, latitude: lat,
      zoom: Math.max(vs.zoom, 14.5),
      transitionInterpolator: new FlyToInterpolator({ speed: 1.2 }),
      transitionDuration: 900,
    }));
  }, [flyToTarget]);

  useEffect(() => {
    if (!draftMarker) return;
    setFormValues({
      title: draftMarker.title || draftMarker.name || '',
      address: draftMarker.address || '',
      description: draftMarker.description || '',
      image: draftMarker.image || '',
      host: draftMarker.ip || draftMarker.host || draftMarker.url || '',
      login: draftMarker.ftp_user || draftMarker.login || '',
      password: draftMarker.ftp_password || draftMarker.password || '',
    });
    setDiscoveryResult(null);
    setDiscoveryError('');
  }, [draftMarker]);

  useEffect(() => {
    const fn = () => setViewportSize({ width: window.innerWidth, height: window.innerHeight });
    window.addEventListener('resize', fn);
    return () => window.removeEventListener('resize', fn);
  }, []);

  // ═══ Normalized data — memo'd по данным, не по тику ═══
  const normalizedAgents = useMemo(() => Object.values(agentsMap || {}).map((a) => {
    const lon = toNumber(a.lon ?? a.longitude); const lat = toNumber(a.lat ?? a.latitude);
    return lon !== null && lat !== null ? { ...a, lon, lat, type: isViolationAgent(a) ? 'danger' : 'agent' } : null;
  }).filter(Boolean), [agentsMap]);

  const normalizedIncidents = useMemo(() => (incidents || []).map((i) => {
    const lon = toNumber(i.lon ?? i.longitude); const lat = toNumber(i.lat ?? i.latitude);
    return lon !== null && lat !== null ? { ...i, lon, lat, type: 'incident' } : null;
  }).filter(Boolean), [incidents]);

  const normalizedPending = useMemo(() => (pendingMarkers || []).map((p) => {
    const lon = toNumber(p.lon ?? p.longitude); const lat = toNumber(p.lat ?? p.latitude);
    return lon !== null && lat !== null ? { ...p, lon, lat, type: 'pending' } : null;
  }).filter(Boolean), [pendingMarkers]);

  const normalizedTerminals = useMemo(() => (terminals || []).map((t) => {
    const lon = toNumber(t.lon ?? t.longitude); const lat = toNumber(t.lat ?? t.latitude);
    return lon !== null && lat !== null ? { ...t, lon, lat, type: 'terminal', channels: Array.isArray(t.channels) ? t.channels : [] } : null;
  }).filter(Boolean), [terminals]);

  const activeTerminal = useMemo(
    () => normalizedTerminals.find((t) => String(t.id) === String(activeTerminalId)) || null,
    [normalizedTerminals, activeTerminalId],
  );

  // ═══ ПРОБЛЕМА №2 FIX: зависимости — примитивы, не объекты ═══
  const filteredData = useMemo(() => [
    ...(showAgents ? normalizedAgents : []),
    ...(showIncidents ? normalizedIncidents : []),
    ...(showPending ? normalizedPending : []),
  ], [showAgents, showIncidents, showPending, normalizedAgents, normalizedIncidents, normalizedPending]);

  const vsLon = viewState.longitude;
  const vsLat = viewState.latitude;
  const vsZoom = viewState.zoom;
  const vsPitch = viewState.pitch;
  const vsBearing = viewState.bearing;

  const bounds = useMemo(() => {
    try {
      return new WebMercatorViewport({
        longitude: vsLon, latitude: vsLat, zoom: vsZoom,
        pitch: vsPitch, bearing: vsBearing,
        width: viewportSize.width, height: viewportSize.height,
      }).getBounds();
    } catch (_) { return null; }
  }, [vsLon, vsLat, vsZoom, vsPitch, vsBearing, viewportSize.width, viewportSize.height]);

  const clusteredData = useMapClusters({ data: filteredData, zoom: vsZoom, bounds });
  const sosPulse = Math.sin(pulseTick * 0.15) * 0.5 + 0.5;

  // ═══ ПРОБЛЕМА №2 FIX: layers — строгий контроль deps ═══
  const layers = useMemo(() => [
    new PathLayer({
      id: 'agent-tracks-layer', data: trackPointsData, pickable: true,
      widthScale: 1, widthMinPixels: 2, widthMaxPixels: 6,
      getPath: gPath, getColor: gPathC,
      updateTriggers: { getPath: [trackPointsData.length] },
    }),
    new ScatterplotLayer({
      id: 'active-agents-layer', data: agentsData, pickable: true,
      opacity: 0.9, stroked: true, filled: true,
      radiusScale: 1, radiusMinPixels: 6, radiusMaxPixels: 14, lineWidthMinPixels: 2,
      getPosition: gAPos, getFillColor: gAFill, getLineColor: gALine,
      updateTriggers: { getPosition: [agentsData.length] },
      transitions: { getPosition: 300 },
    }),
    new IconLayer({
      id: 'clustered-icon-layer', data: clusteredData, pickable: true, sizeScale: 1,
      getPosition: gCPos,
      getIcon: (d) => d.properties.cluster ? ICONS.cluster : (ICONS[d.properties.entityType] || ICONS.unknown),
      getSize: (d) => {
        if (d.properties.cluster) return Math.min(36 + Math.log2(d.properties.point_count || 1) * 10, 76);
        if (d.properties.entityType === 'danger') return 42 + sosPulse * 8;
        return 30;
      },
      sizeUnits: 'pixels',
      updateTriggers: { getSize: [sosPulse, clusteredData.length] },
      transitions: { getPosition: 300 },
    }),
    new ColumnLayer({
      id: 'threat-pillar-layer', data: threatsData,
      diskResolution: 6, radius: 15, extruded: true, pickable: true, elevationScale: 1,
      getPosition: gTPos, getFillColor: gTFill, getLineColor: gTLine, getElevation: gTElev,
      updateTriggers: { getPosition: [threatsData.length] },
      transitions: { getElevation: { duration: 800, type: 'spring' } },
    }),
    new TextLayer({
      id: 'cluster-count-layer',
      data: clusteredData.filter((d) => d.properties.cluster),
      pickable: false, billboard: true,
      getPosition: gCPos, getText: gCText,
      getColor: C_WHITE, getSize: 16,
      getTextAnchor: 'middle', getAlignmentBaseline: 'center',
      characterSet: 'auto', sizeUnits: 'pixels',
      fontSettings: { fontWeight: 800 },
    }),
  ], [agentsData, clusteredData, sosPulse, trackPointsData, threatsData]);

  // ═══ Stable callbacks ═══
  const handleViewStateChange = useCallback(({ viewState: n }) => setViewState(n), []);

  const handleDeckClick = useCallback((info) => {
    if (info?.srcEvent?.stopPropagation) info.srcEvent.stopPropagation();
    if (!info?.object) return;
    const f = info.object;
    if (f?.properties?.cluster) {
      if (setActiveNode) setActiveNode(null);
      setActiveTerminal(null);
      const [lon, lat] = f.geometry.coordinates;
      setViewState((p) => ({
        ...p, longitude: lon, latitude: lat,
        zoom: Math.min((p.zoom || 0) + 2, 16),
        transitionInterpolator: new FlyToInterpolator({ speed: 1.3 }), transitionDuration: 500,
      }));
      return;
    }
    const sel = f.properties || f || null;
    if (setActiveNode) setActiveNode(toActiveNodePayload(sel));
    setSelectedObject(sel);
    if (sel?.agent_id && onUserClick) onUserClick(String(sel.agent_id));
  }, [setActiveNode, setSelectedObject, onUserClick]);

  const forwardGeocode = useCallback(async () => {
    const q = (formValues.address || '').trim();
    if (!q) return;
    try {
      const r = await fetch(`https://nominatim.openstreetmap.org/search?format=json&limit=1&q=${encodeURIComponent(q)}`, { headers: { Accept: 'application/json' } });
      const d = await r.json();
      if (!Array.isArray(d) || !d[0]) return;
      const lat = Number(d[0].lat); const lon = Number(d[0].lon);
      if (!Number.isFinite(lat) || !Number.isFinite(lon)) return;
      setViewState((p) => ({ ...p, longitude: lon, latitude: lat, zoom: Math.max(p.zoom || 0, 15), transitionInterpolator: new FlyToInterpolator({ speed: 1.2 }), transitionDuration: 1000 }));
    } catch (_) {}
  }, [formValues.address]);

  const onImageSelected = useCallback((e) => {
    const file = e.target.files?.[0]; if (!file) return;
    const reader = new FileReader();
    reader.onload = () => setFormValues((p) => ({ ...p, image: typeof reader.result === 'string' ? reader.result : '' }));
    reader.readAsDataURL(file);
  }, []);

  const handleAnalyzeNode = useCallback(async () => {
    if (!draftMarker || isDiscovering) return;
    setIsDiscovering(true); setDiscoveryResult(null); setDiscoveryError('');
    try {
      const resp = await fetch('/api/terminals/discover', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ip: formValues.host, username: formValues.login, password: formValues.password }),
      });
      const data = await resp.json().catch(() => ({}));
      if (resp.ok && data?.status === 'success') {
        setDiscoveryResult(data);
        addNotify(`Успешно: терминал ${data?.type || 'UNKNOWN'}, каналов: ${(data?.channels || []).length}`, 'success');
      } else {
        setDiscoveryError('❌ Не удалось определить тип устройства');
        addNotify('Не удалось определить тип устройства', 'error');
      }
    } catch (_) {
      setDiscoveryError('❌ Ошибка сети'); addNotify('Ошибка сети при анализе узла', 'error');
    } finally { setIsDiscovering(false); }
  }, [draftMarker, isDiscovering, formValues.host, formValues.login, formValues.password, addNotify]);

  const saveDraftObject = useCallback(async () => {
    if (!draftMarker || isSavingObject) return;
    setIsSavingObject(true);
    try {
      const channels = Array.isArray(discoveryResult?.channels) ? discoveryResult.channels : [];
      const resp = await fetch('/api/objects', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: formValues.title, name: formValues.title, address: formValues.address,
          description: formValues.description, image: formValues.image, ip: formValues.host,
          lat: draftMarker.lat, lon: draftMarker.lon,
          terminal_auth: { ftp_user: formValues.login, ftp_password: formValues.password }, channels,
        }),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const saved = await resp.json();
      addMarker({
        id: saved?.id, name: saved?.name || formValues.title, title: saved?.name || formValues.title,
        address: saved?.address || formValues.address, description: saved?.description || formValues.description,
        image: saved?.image || formValues.image, ip: saved?.ip || formValues.host,
        lat: saved?.lat ?? draftMarker.lat, lon: saved?.lon ?? draftMarker.lon, channels,
      });
      clearDraftMarker();
    } catch (_) {} finally { setIsSavingObject(false); }
  }, [draftMarker, isSavingObject, discoveryResult, formValues, addMarker, clearDraftMarker]);

  return (
    <div className="absolute inset-0">
      <DeckGL viewState={viewState} onViewStateChange={handleViewStateChange} controller layers={layers} deviceProps={DEVICE_PROPS} _useDevicePixels onClick={handleDeckClick}>
        <Map
          mapStyle={mapStyle}
          reuseMaps
          dragRotate={!isMobile}
          onError={() => {
            if (!mapStyleFallbackActive) {
              setMapStyle(MAP_STYLE_FALLBACK);
              setMapStyleFallbackActive(true);
            }
          }}
        >
          {showCameras && normalizedTerminals.map((t, i) => (
            <Marker key={t.id || `t-${i}`} longitude={t.lon} latitude={t.lat} anchor="center">
              <button type="button" onClick={(e) => {
                e.stopPropagation();
                setActiveTerminal(t.id ?? `t-${i}`); setSelectedObject(t);
                if (setActiveNode) setActiveNode(toActiveNodePayload({ ...t, camera_name: t.name, camera_ip: t.ip }));
              }} className="group relative">
                <span className="pointer-events-none absolute -top-6 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-rose-500/20 px-2 py-0.5 text-[10px] font-mono text-rose-400">
                  {(Array.isArray(t.channels) ? t.channels.length : 0)} CAMS
                </span>
                <span className="block h-4 w-4 animate-pulse rounded-[2px] border-2 border-rose-400 bg-slate-800 shadow-[0_0_18px_rgba(244,63,94,0.45)] transition group-hover:scale-110" />
              </button>
            </Marker>
          ))}
        </Map>
      </DeckGL>


      {mapStyleFallbackActive && (
        <div className="pointer-events-none absolute left-1/2 top-16 z-30 -translate-x-1/2 rounded border border-amber-400/40 bg-amber-950/60 px-3 py-1 text-xs text-amber-200">
          Карта переключена на fallback-стиль (OSM), т.к. офлайн PMTiles недоступен.
        </div>
      )}

      {activeTerminal && <TacticalGridDashboard terminal={activeTerminal} onClose={() => setActiveTerminal(null)} />}

      {draftMarker && (
        <div className="pointer-events-auto absolute left-1/2 top-1/2 z-40 w-[480px] -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-cyan-500/30 bg-slate-950/90 p-4 shadow-[0_0_40px_rgba(6,182,212,0.25)] backdrop-blur-md">
          <div className="mb-3 font-mono text-sm uppercase tracking-wide text-cyan-300">Регистрация объекта</div>
          <div className="space-y-4">
            <div className="rounded-lg border border-cyan-500/25 bg-slate-900/50 p-3">
              <div className="mb-2 font-mono text-xs uppercase tracking-wide text-cyan-300">Метаданные</div>
              <div className="space-y-2">
                <input value={formValues.title} onChange={(e) => setFormValues((p) => ({ ...p, title: e.target.value }))} placeholder="Название / ID" className="w-full rounded border border-cyan-700/40 bg-slate-900/70 px-3 py-2 text-sm text-slate-100 outline-none focus:border-cyan-400" />
                <div className="flex gap-2">
                  <input value={formValues.address} onChange={(e) => setFormValues((p) => ({ ...p, address: e.target.value }))} placeholder="Адрес" className="flex-1 rounded border border-cyan-700/40 bg-slate-900/70 px-3 py-2 text-sm text-slate-100 outline-none focus:border-cyan-400" />
                  <button type="button" onClick={forwardGeocode} className="inline-flex items-center justify-center rounded border border-cyan-400/60 bg-cyan-500/10 px-3 text-cyan-200 hover:bg-cyan-500/20" title="Найти адрес"><Search className="h-4 w-4" /></button>
                </div>
                <textarea value={formValues.description} onChange={(e) => setFormValues((p) => ({ ...p, description: e.target.value }))} placeholder="Текстовое описание" rows={3} className="w-full rounded border border-cyan-700/40 bg-slate-900/70 px-3 py-2 text-sm text-slate-100 outline-none focus:border-cyan-400" />
                <label className="block rounded border border-cyan-700/40 bg-slate-900/70 px-3 py-2 text-xs text-slate-300">Загрузка фото<input type="file" accept="image/*" onChange={onImageSelected} className="mt-1 block w-full text-xs text-slate-300" /></label>
              </div>
            </div>
            <div className="rounded-lg border border-rose-500/25 bg-rose-950/20 p-3">
              <div className="mb-2 font-mono text-xs uppercase tracking-wide text-rose-300">Подключение</div>
              <div className="space-y-2">
                <input value={formValues.host} onChange={(e) => setFormValues((p) => ({ ...p, host: e.target.value }))} placeholder="IP / Домен" className="w-full rounded border border-rose-500/30 bg-slate-900/70 px-3 py-2 text-sm text-slate-100 outline-none focus:border-rose-300" />
                <div className="grid grid-cols-2 gap-2">
                  <div className="relative"><Lock className="pointer-events-none absolute left-2 top-2.5 h-4 w-4 text-rose-400" /><input value={formValues.login} onChange={(e) => setFormValues((p) => ({ ...p, login: e.target.value }))} placeholder="Логин" className="w-full rounded border border-rose-500/30 bg-slate-900/70 px-8 py-2 text-sm text-slate-100 outline-none focus:border-rose-300" /></div>
                  <div className="relative"><Lock className="pointer-events-none absolute left-2 top-2.5 h-4 w-4 text-rose-400" /><input type="password" value={formValues.password} onChange={(e) => setFormValues((p) => ({ ...p, password: e.target.value }))} placeholder="Пароль" className="w-full rounded border border-rose-500/30 bg-slate-900/70 px-8 py-2 text-sm text-slate-100 outline-none focus:border-rose-300" /></div>
                </div>
              </div>
            </div>
            <div className="rounded-lg border border-fuchsia-500/25 bg-fuchsia-950/20 p-3">
              <div className="mb-2 font-mono text-xs uppercase tracking-wide text-fuchsia-300">Сканирование</div>
              <button type="button" onClick={handleAnalyzeNode} disabled={isDiscovering || !formValues.host || !formValues.login || !formValues.password} className="flex w-full items-center justify-center gap-2 rounded border border-fuchsia-400/60 bg-fuchsia-500/10 px-3 py-2 font-mono text-xs uppercase tracking-wide text-fuchsia-200 transition hover:bg-fuchsia-500/20 disabled:opacity-50">
                {isDiscovering ? <Loader2 className="h-4 w-4 animate-spin" /> : <Radar className="h-4 w-4" />}
                {isDiscovering ? 'Сканирование...' : '[ АНАЛИЗ УЗЛА ]'}
              </button>
            </div>
            {(discoveryResult || discoveryError) && (
              <div className={`rounded border p-2 text-xs font-mono ${discoveryResult ? 'border-emerald-500/30 bg-emerald-900/20 text-emerald-300' : 'border-red-500/30 bg-red-950/20 text-red-300'}`}>
                {discoveryResult ? `✅ Терминал ${discoveryResult?.type || 'UNKNOWN'} готов. Каналов: ${(discoveryResult?.channels || []).length}` : discoveryError}
              </div>
            )}
            <div className="flex justify-end gap-2">
              <button type="button" onClick={clearDraftMarker} className="rounded border border-slate-600 px-3 py-2 text-xs uppercase tracking-wide text-slate-300 hover:border-slate-400">Отмена</button>
              <button type="button" onClick={saveDraftObject} disabled={isSavingObject} className="rounded border border-cyan-400/60 bg-cyan-500/10 px-3 py-2 text-xs uppercase tracking-wide text-cyan-200 hover:bg-cyan-500/20 disabled:opacity-50">
                {isSavingObject ? 'Сохранение...' : '[ СОХРАНИТЬ ОБЪЕКТ ]'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
