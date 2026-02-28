import { create } from '../vendor/zustand';
import * as Y from 'yjs';
import { WebrtcProvider } from 'y-webrtc';

const ydoc = new Y.Doc();
const provider = new WebrtcProvider('playe-tactical-room', ydoc, {
  signaling: ['wss://signaling.yjs.dev'],
});

const sharedTacticalZones = ydoc.getArray('tacticalZones');
const sharedManualMarkers = ydoc.getArray('manualMarkers');

const initialState = {
  agents: {},
  trackPoints: {},
  incidents: [],
  threatAlerts: {},
  pendingMarkers: [],
  selectedObject: null,
  trackers: {},
  statuses: {},
  chatMessages: [],
  markers: sharedManualMarkers.toArray(),
  manualMarkers: sharedManualMarkers.toArray(),
  tacticalZones: sharedTacticalZones.toArray(),
  activeMarkerId: null,
  activePendingMarkerId: null,
  draftMarker: null,
  peerStatus: "disconnected",
  telemetry: {
    cpu_load: 0,
    ram_usage: 0,
    active_nodes: 0,
    net_traffic: '0 MB/s',
    hex_dump: '000000000000000000000000',
  },
};

const getEntityId = (item) => item?.id ?? item?.incident_id ?? item?.pending ?? item?.pending_id;
const getViolationFlag = (data, fallback) => {
  if (typeof data?.isViolation === 'boolean') return data.isViolation;
  if (typeof data?.violation === 'boolean') return data.violation;
  if (typeof data?.in_violation === 'boolean') return data.in_violation;
  if (typeof data?.zone_violation === 'boolean') return data.zone_violation;
  if (typeof data?.inside_polygon === 'boolean') return data.inside_polygon;
  if (typeof fallback === 'boolean') return fallback;
  return false;
};

const syncSharedState = (set) => {
  const manualMarkers = sharedManualMarkers.toArray();
  set({ manualMarkers, markers: manualMarkers });
};

let isObserverInitialized = false;

const useMapStore = create((set, get) => {
  if (!isObserverInitialized) {
    sharedTacticalZones.observe(() => {
      set({ tacticalZones: sharedTacticalZones.toArray() });
    });

    sharedManualMarkers.observe(() => {
      const manualMarkers = sharedManualMarkers.toArray();
      set({ manualMarkers, markers: manualMarkers });
    });

    isObserverInitialized = true;
  }

  return {
    ...initialState,

    updateAgentLocation: (payload) => set((state) => {
      const rawId = payload?.agent_id ?? payload?.id ?? payload?.user_id;
      const lat = Number(payload?.lat ?? payload?.latitude);
      const lon = Number(payload?.lon ?? payload?.longitude);

      if (rawId === undefined || rawId === null || !Number.isFinite(lat) || !Number.isFinite(lon)) {
        return state;
      }

      const agentId = String(rawId);
      const newCoord = [lon, lat];

      const currentAgent = state.agents[agentId] || { id: agentId, agent_id: agentId };
      const updatedAgents = {
        ...state.agents,
        [agentId]: {
          ...currentAgent,
          ...payload,
          id: currentAgent.id ?? agentId,
          agent_id: agentId,
          lon,
          lat,
          coordinates: newCoord,
          last_seen: Date.now(),
        },
      };

      const currentTrack = state.trackPoints[agentId]?.path || [];
      const updatedPath = [...currentTrack, newCoord].slice(-50);
      const updatedTracks = {
        ...state.trackPoints,
        [agentId]: { id: agentId, agent_id: agentId, path: updatedPath },
      };

      return {
        agents: updatedAgents,
        trackPoints: updatedTracks,
      };
    }),

    // МАССОВОЕ ОБНОВЛЕНИЕ (BATCHING)
    batchUpdateAgentLocations: (agentsArray) => set((state) => {
      const updatedAgents = { ...state.agents };
      const updatedTracks = { ...state.trackPoints };

      agentsArray.forEach((payload) => {
        const rawId = payload?.agent_id ?? payload?.id ?? payload?.user_id;
        const lat = Number(payload?.lat ?? payload?.latitude);
        const lon = Number(payload?.lon ?? payload?.longitude);

        if (rawId == null || !Number.isFinite(lat) || !Number.isFinite(lon)) return;

        const agentId = String(rawId);
        const newCoord = [lon, lat];

        const currentAgent = updatedAgents[agentId] || { id: agentId, agent_id: agentId };
        updatedAgents[agentId] = {
          ...currentAgent,
          ...payload,
          id: currentAgent.id ?? agentId,
          agent_id: agentId,
          lon,
          lat,
          coordinates: newCoord,
          last_seen: Date.now(),
        };

        const currentTrack = updatedTracks[agentId]?.path || [];
        const updatedPath = [...currentTrack, newCoord].slice(-50);
        updatedTracks[agentId] = { id: agentId, agent_id: agentId, path: updatedPath };
      });

      return { agents: updatedAgents, trackPoints: updatedTracks };
    }),

    updateAgent: (data) => set((state) => {
      const rawId = data?.agent_id ?? data?.id ?? data?.user_id;
      if (rawId === undefined || rawId === null) return state;

      const agentId = String(rawId);
      const mergedAgent = {
        ...(state.agents[agentId] || {}),
        ...data,
        agent_id: agentId,
        isViolation: getViolationFlag(data, state.agents[agentId]?.isViolation),
      };

      return {
        agents: {
          ...state.agents,
          [agentId]: mergedAgent,
        },
        trackers: {
          ...state.trackers,
          [agentId]: {
            ...(state.trackers[agentId] || {}),
            ...mergedAgent,
          },
        },
        statuses: {
          ...state.statuses,
          [agentId]: data?.status || state.statuses[agentId] || 'online',
        },
      };
    }),

    addIncident: (data) => set((state) => {
      if (!data) return state;

      const incidentId = data.id ?? data.incident_id;
      if (incidentId === undefined || incidentId === null) {
        return { incidents: [data, ...state.incidents] };
      }

      const normalizedId = String(incidentId);
      const existingIdx = state.incidents.findIndex((it) => String(it.id ?? it.incident_id) === normalizedId);
      if (existingIdx >= 0) {
        const next = [...state.incidents];
        next[existingIdx] = { ...next[existingIdx], ...data, id: incidentId };
        return { incidents: next };
      }

      return { incidents: [{ ...data, id: incidentId }, ...state.incidents] };
    }),

    removeIncident: (incidentId) => set((state) => ({
      incidents: state.incidents.filter((it) => String(it.id ?? it.incident_id) !== String(incidentId)),
    })),

    setPendingMarkers: (markers) => set({ pendingMarkers: Array.isArray(markers) ? markers : [] }),

    upsertPendingMarker: (pendingMarker) => set((state) => {
      if (!pendingMarker) return state;

      const rawId = getEntityId(pendingMarker);
      if (rawId === undefined || rawId === null) {
        return { pendingMarkers: [pendingMarker, ...state.pendingMarkers] };
      }

      const pendingId = String(rawId);
      const existingIdx = state.pendingMarkers.findIndex((it) => String(getEntityId(it)) === pendingId);
      if (existingIdx >= 0) {
        const next = [...state.pendingMarkers];
        next[existingIdx] = { ...next[existingIdx], ...pendingMarker, id: rawId };
        return { pendingMarkers: next };
      }

      return { pendingMarkers: [{ ...pendingMarker, id: rawId }, ...state.pendingMarkers] };
    }),

    removePendingMarker: (pendingId) => set((state) => ({
      pendingMarkers: state.pendingMarkers.filter((it) => String(getEntityId(it)) !== String(pendingId)),
      activePendingMarkerId: String(state.activePendingMarkerId) === String(pendingId) ? null : state.activePendingMarkerId,
    })),

    setActivePendingMarker: (pendingId) => set({ activePendingMarkerId: pendingId ? String(pendingId) : null }),

    addChatMessage: (message) => set((state) => {
      if (!message) return state;
      return { chatMessages: [...state.chatMessages, message] };
    }),

    setSelectedObject: (selectedObject) => set({ selectedObject }),

    setTelemetry: (data) => set((state) => ({
  peerStatus: "disconnected",
      telemetry: { ...state.telemetry, ...(data || {}) },
    })),

    addThreatAlert: (payload) => set((state) => {
      if (!payload) return state;

      const id = payload.id || `threat-${Date.now()}`;
      const threatPayload = { ...payload, id };

      setTimeout(() => {
        set((s) => {
          const newThreats = { ...s.threatAlerts };
          delete newThreats[id];
          return { threatAlerts: newThreats };
        });
      }, 30000);

      return {
        threatAlerts: { ...state.threatAlerts, [id]: threatPayload },
        incidents: [...state.incidents, {
          id,
          priority: payload.severity === 'CRITICAL' ? 'CRITICAL' : 'HIGH',
          timestamp: Date.now(),
          description: `[DARKNET_DUMP] Утечка: ${String(payload.secret_type || 'unknown').toUpperCase()} | Цель: OBJ_${payload.object_id ?? 'N/A'} | Дамп: ${payload.snippet || ''}`,
        }].slice(-50),
      };
    }),

    // compatibility with older components
    upsertTrackerPosition: (trackerId, payload) => set((state) => ({
      trackers: {
        ...state.trackers,
        [String(trackerId)]: {
          ...(state.trackers[String(trackerId)] || {}),
          ...payload,
        },
      },
    })),

    setTrackerStatus: (trackerId, status) => set((state) => ({
      statuses: {
        ...state.statuses,
        [String(trackerId)]: status,
      },
    })),

    addTacticalZone: (zoneData) => {
      if (!zoneData) return;
      sharedTacticalZones.push([{ id: zoneData?.id || `zone-${Date.now()}`, ...zoneData }]);
    },

    addManualMarker: (markerData) => {
      if (!markerData) return;
      sharedManualMarkers.push([{ id: markerData?.id || Date.now().toString(), ...markerData }]);
    },

    setDraftMarker: (data) => set({ draftMarker: data, activeMarkerId: null }),
    clearDraftMarker: () => set({ draftMarker: null }),

    // ═══ CRDT sync actions ═══
    _setTacticalZones: (zones) => set({ tacticalZones: zones }),
    _setManualMarkers: (markers) => set({ manualMarkers: markers, markers }),
    _setPeerStatus: (status) => set({ peerStatus: status }),

    // marker API kept for compatibility with existing UI
    addMarker: (markerData) => {
      if (!markerData) return;
      sharedManualMarkers.push([{ id: markerData?.id || Date.now().toString(), ...markerData }]);
    },

    updateMarker: (id, updatedData) => {
      const markers = sharedManualMarkers.toArray();
      const idx = markers.findIndex((m) => m.id === id);
      if (idx < 0) return;

      sharedManualMarkers.delete(idx, 1);
      sharedManualMarkers.insert(idx, [{ ...markers[idx], ...updatedData }]);
    },

    deleteMarker: (id) => {
      const markers = sharedManualMarkers.toArray();
      const idx = markers.findIndex((m) => m.id === id);
      if (idx >= 0) {
        sharedManualMarkers.delete(idx, 1);
      }

      set((state) => ({
        activeMarkerId: state.activeMarkerId === id ? null : state.activeMarkerId,
      }));
    },

    setActiveMarker: (id) => set({ activeMarkerId: id, draftMarker: null }),

    getAgentsArray: () => Object.values(get().agents),
    getTracksArray: () => Object.values(get().trackPoints),
    getThreatsArray: () => Object.values(get().threatAlerts),

    reset: () => {
      sharedTacticalZones.delete(0, sharedTacticalZones.length);
      sharedManualMarkers.delete(0, sharedManualMarkers.length);
      set({
        ...initialState,
        tacticalZones: [],
        manualMarkers: [],
        markers: [],
      });
      syncSharedState(set);
    },
  };
});

void provider;

export default useMapStore;

// ═══════════════════════════════════════════════════════
// CRDT P2P SYNC ENHANCEMENTS (Yjs + WebRTC)
// ═══════════════════════════════════════════════════════

// Offline queue for mutations made while disconnected
const _offlineQueue = [];
let _isOnline = typeof navigator !== 'undefined' ? navigator.onLine : true;

if (typeof window !== 'undefined') {
  window.addEventListener('online', () => {
    _isOnline = true;
    _flushOfflineQueue();
  });
  window.addEventListener('offline', () => {
    _isOnline = false;
  });
}

function _flushOfflineQueue() {
  while (_offlineQueue.length > 0) {
    const action = _offlineQueue.shift();
    try {
      action();
    } catch (e) {
      console.error('[CRDT] Offline queue flush error:', e);
    }
  }
}

// Enhanced CRDT-aware zone operations with conflict resolution
function addTacticalZoneCRDT(zone) {
  const enriched = {
    ...zone,
    _crdt_id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    _crdt_timestamp: Date.now(),
    _crdt_author: typeof window !== 'undefined' ? window.__AGENT_ID || 'unknown' : 'server',
  };

  const apply = () => {
    sharedTacticalZones.push([enriched]);
  };

  if (_isOnline) {
    apply();
  } else {
    _offlineQueue.push(apply);
  }
  return enriched;
}

function removeTacticalZoneCRDT(crdtId) {
  const arr = sharedTacticalZones.toArray();
  const idx = arr.findIndex((z) => z._crdt_id === crdtId);
  if (idx !== -1) {
    sharedTacticalZones.delete(idx, 1);
    return true;
  }
  return false;
}

// Observe remote CRDT changes from other peers
sharedTacticalZones.observe((event) => {
  const store = useMapStore.getState();
  store._setTacticalZones(sharedTacticalZones.toArray());
});

sharedManualMarkers.observe((event) => {
  const store = useMapStore.getState();
  store._setManualMarkers(sharedManualMarkers.toArray());
});

// P2P connection status
provider.on('status', (event) => {
  const store = useMapStore.getState();
  if (typeof store._setPeerStatus === 'function') {
    store._setPeerStatus(event.status); // 'connected' | 'disconnected'
  }
});

// Export CRDT helpers
export { addTacticalZoneCRDT, removeTacticalZoneCRDT, _isOnline, provider };
