// Ported from ../globalconnect/src/store/leads.store.ts
// Zustand store for lead management with optimistic updates

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import AsyncStorage from '@react-native-async-storage/async-storage';
import type {
  Lead,
  LeadStats,
  LeadCapturedEvent,
  LeadIntentUpdatedEvent,
  OfflineLead,
} from '@/types/leads';

interface PendingUpdate {
  originalLead: Lead;
  update: Partial<Lead>;
}

interface LeadsState {
  leads: Lead[];
  stats: LeadStats | null;
  sponsorId: string | null;
  isLoading: boolean;
  isLoadingStats: boolean;
  offlineLeads: OfflineLead[];
  pendingUpdates: Record<string, PendingUpdate>;

  // Data management
  setLeads: (leads: Lead[]) => void;
  setStats: (stats: LeadStats) => void;
  setSponsorId: (sponsorId: string) => void;
  setLoading: (isLoading: boolean) => void;
  setLoadingStats: (isLoadingStats: boolean) => void;
  clearStore: () => void;

  // Optimistic updates
  optimisticUpdateLead: (leadId: string, update: Partial<Lead>) => void;
  commitUpdate: (leadId: string) => void;
  rollbackUpdate: (leadId: string) => void;

  // Real-time event handlers
  handleLeadCaptured: (event: LeadCapturedEvent) => void;
  handleIntentUpdated: (event: LeadIntentUpdatedEvent) => void;
  handleStatsUpdated: (stats: LeadStats) => void;

  // Offline lead capture
  addOfflineLead: (lead: OfflineLead) => void;
  markOfflineLeadSynced: (localId: string) => void;
  removeOfflineLead: (localId: string) => void;
  getUnsyncedLeads: () => OfflineLead[];
}

export const useLeadsStore = create<LeadsState>()(
  persist(
    (set, get) => ({
      leads: [],
      stats: null,
      sponsorId: null,
      isLoading: true,
      isLoadingStats: true,
      offlineLeads: [],
      pendingUpdates: {},

      setLeads: (leads) => set({ leads, isLoading: false }),

      setStats: (stats) => {
        if (stats && stats.total_leads !== undefined) {
          set({ stats, isLoadingStats: false });
        } else {
          set({ isLoadingStats: false });
        }
      },

      setSponsorId: (sponsorId) => {
        const state = get();
        if (state.sponsorId !== null && state.sponsorId !== sponsorId) {
          set({ leads: [], stats: null, isLoading: true, isLoadingStats: true, sponsorId });
        } else {
          set({ sponsorId });
        }
      },

      setLoading: (isLoading) => set({ isLoading }),
      setLoadingStats: (isLoadingStats) => set({ isLoadingStats }),

      clearStore: () =>
        set({
          leads: [],
          stats: null,
          sponsorId: null,
          isLoading: true,
          isLoadingStats: true,
          pendingUpdates: {},
        }),

      optimisticUpdateLead: (leadId, update) => {
        const state = get();
        const lead = state.leads.find((l) => l.id === leadId);
        if (!lead) return;

        set({
          pendingUpdates: {
            ...state.pendingUpdates,
            [leadId]: { originalLead: { ...lead }, update },
          },
          leads: state.leads.map((l) =>
            l.id === leadId ? { ...l, ...update } : l,
          ),
        });
      },

      commitUpdate: (leadId) => {
        const { pendingUpdates, ...rest } = get();
        const { [leadId]: _removed, ...remaining } = pendingUpdates;
        set({ ...rest, pendingUpdates: remaining });
      },

      rollbackUpdate: (leadId) => {
        const state = get();
        const pending = state.pendingUpdates[leadId];
        if (!pending) return;

        const { [leadId]: _removed, ...remaining } = state.pendingUpdates;
        set({
          leads: state.leads.map((l) =>
            l.id === leadId ? pending.originalLead : l,
          ),
          pendingUpdates: remaining,
        });
      },

      handleLeadCaptured: (event) => {
        const state = get();
        const existingIndex = state.leads.findIndex((l) => l.id === event.id);

        if (existingIndex !== -1) return; // Already have this lead

        const newLead: Lead = {
          id: event.id,
          sponsor_id: state.sponsorId || '',
          event_id: '',
          user_id: event.user_id,
          user_name: event.user_name,
          user_email: event.user_email,
          user_company: event.user_company,
          user_title: event.user_title,
          intent_score: event.intent_score,
          intent_level: event.intent_level,
          first_interaction_at: event.created_at,
          last_interaction_at: event.created_at,
          interaction_count: 1,
          interactions: [{ type: event.interaction_type, timestamp: event.created_at }],
          contact_requested: false,
          contact_notes: null,
          preferred_contact_method: null,
          follow_up_status: 'new',
          follow_up_notes: null,
          followed_up_at: null,
          followed_up_by_user_id: null,
          tags: [],
          is_starred: false,
          is_archived: false,
          created_at: event.created_at,
          updated_at: event.created_at,
        };

        const newStats = state.stats
          ? {
              ...state.stats,
              total_leads: state.stats.total_leads + 1,
              [`${event.intent_level}_leads`]:
                (state.stats[`${event.intent_level}_leads` as keyof LeadStats] as number) + 1,
            }
          : null;

        set({
          leads: [newLead, ...state.leads],
          stats: newStats as LeadStats | null,
        });
      },

      handleIntentUpdated: (event) => {
        const state = get();
        const lead = state.leads.find((l) => l.id === event.lead_id);
        if (!lead) return;

        set({
          leads: state.leads.map((l) =>
            l.id === event.lead_id
              ? {
                  ...l,
                  intent_score: event.intent_score,
                  intent_level: event.intent_level,
                  interaction_count: event.interaction_count,
                  last_interaction_at: new Date().toISOString(),
                }
              : l,
          ),
        });
      },

      handleStatsUpdated: (stats) => {
        if (stats && stats.total_leads !== undefined) {
          set({ stats, isLoadingStats: false });
        }
      },

      // Offline lead capture for expo floors with poor WiFi
      addOfflineLead: (lead) => {
        set({ offlineLeads: [...get().offlineLeads, lead] });
      },

      markOfflineLeadSynced: (localId) => {
        set({
          offlineLeads: get().offlineLeads.map((l) =>
            l.localId === localId ? { ...l, synced: true } : l,
          ),
        });
      },

      removeOfflineLead: (localId) => {
        set({
          offlineLeads: get().offlineLeads.filter((l) => l.localId !== localId),
        });
      },

      getUnsyncedLeads: () => {
        return get().offlineLeads.filter((l) => !l.synced);
      },
    }),
    {
      name: 'leads-storage',
      storage: createJSONStorage(() => AsyncStorage),
      partialize: (state) => ({
        offlineLeads: state.offlineLeads,
        sponsorId: state.sponsorId,
      }),
    },
  ),
);
