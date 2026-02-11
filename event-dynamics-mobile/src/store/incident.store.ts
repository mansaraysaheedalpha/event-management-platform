// Incident management store for organizer dashboard
// Ported from ../globalconnect/src/store/incident.store.ts

import { create } from 'zustand';
import type {
  Incident,
  IncidentStatus,
  IncidentSeverity,
  IncidentType,
  IncidentFilters,
} from '@/types/incident';

interface IncidentState {
  incidents: Incident[];
  isLoading: boolean;
  isConnected: boolean;
  error: string | null;
  filters: IncidentFilters;
  selectedIncidentId: string | null;

  setIncidents: (incidents: Incident[]) => void;
  addIncident: (incident: Incident) => void;
  updateIncident: (incident: Incident) => void;
  removeIncident: (incidentId: string) => void;

  setIsLoading: (isLoading: boolean) => void;
  setIsConnected: (isConnected: boolean) => void;
  setError: (error: string | null) => void;

  setFilters: (filters: Partial<IncidentFilters>) => void;
  clearFilters: () => void;

  setSelectedIncidentId: (id: string | null) => void;

  getFilteredIncidents: () => Incident[];
  getIncidentById: (id: string) => Incident | undefined;
  getActiveIncidentsCount: () => number;
  getCriticalIncidentsCount: () => number;
}

export const useIncidentStore = create<IncidentState>((set, get) => ({
  incidents: [],
  isLoading: false,
  isConnected: false,
  error: null,
  filters: {},
  selectedIncidentId: null,

  setIncidents: (incidents) => set({ incidents }),

  addIncident: (incident) =>
    set((state) => ({
      incidents: [incident, ...state.incidents],
    })),

  updateIncident: (updatedIncident) =>
    set((state) => ({
      incidents: state.incidents.map((incident) =>
        incident.id === updatedIncident.id ? updatedIncident : incident,
      ),
    })),

  removeIncident: (incidentId) =>
    set((state) => ({
      incidents: state.incidents.filter((i) => i.id !== incidentId),
    })),

  setIsLoading: (isLoading) => set({ isLoading }),
  setIsConnected: (isConnected) => set({ isConnected }),
  setError: (error) => set({ error }),

  setFilters: (filters) =>
    set((state) => ({
      filters: { ...state.filters, ...filters },
    })),

  clearFilters: () => set({ filters: {} }),

  setSelectedIncidentId: (id) => set({ selectedIncidentId: id }),

  getFilteredIncidents: () => {
    const { incidents, filters } = get();

    return incidents.filter((incident) => {
      if (filters.status && filters.status.length > 0) {
        if (!filters.status.includes(incident.status)) return false;
      }
      if (filters.severity && filters.severity.length > 0) {
        if (!filters.severity.includes(incident.severity)) return false;
      }
      if (filters.type && filters.type.length > 0) {
        if (!filters.type.includes(incident.type)) return false;
      }
      if (filters.searchQuery?.trim()) {
        const query = filters.searchQuery.toLowerCase();
        const matchesDetails = incident.details.toLowerCase().includes(query);
        const matchesReporter =
          incident.reporter.firstName?.toLowerCase().includes(query) ||
          incident.reporter.lastName?.toLowerCase().includes(query);
        if (!matchesDetails && !matchesReporter) return false;
      }
      return true;
    });
  },

  getIncidentById: (id) => {
    return get().incidents.find((i) => i.id === id);
  },

  getActiveIncidentsCount: () => {
    return get().incidents.filter((i) => i.status !== 'RESOLVED').length;
  },

  getCriticalIncidentsCount: () => {
    return get().incidents.filter(
      (i) => i.severity === 'CRITICAL' && i.status !== 'RESOLVED',
    ).length;
  },
}));
