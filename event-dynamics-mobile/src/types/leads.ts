// Types for Lead management — ported from web
// ../globalconnect/src/types/leads.ts

export interface LeadInteraction {
  type: string;
  timestamp: string;
  duration_seconds?: number;
  content_name?: string;
  notes?: string;
  metadata?: Record<string, unknown>;
}

export interface Lead {
  id: string;
  sponsor_id: string;
  event_id: string;
  user_id: string;
  user_name: string | null;
  user_email: string | null;
  user_company: string | null;
  user_title: string | null;
  intent_score: number;
  intent_level: 'hot' | 'warm' | 'cold';
  first_interaction_at: string;
  last_interaction_at: string;
  interaction_count: number;
  interactions: LeadInteraction[];
  contact_requested: boolean;
  contact_notes: string | null;
  preferred_contact_method: string | null;
  follow_up_status: 'new' | 'contacted' | 'qualified' | 'not_interested' | 'converted';
  follow_up_notes: string | null;
  followed_up_at: string | null;
  followed_up_by_user_id: string | null;
  tags: string[];
  is_starred: boolean;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
}

export interface LeadStats {
  total_leads: number;
  hot_leads: number;
  warm_leads: number;
  cold_leads: number;
  leads_contacted: number;
  leads_converted: number;
  conversion_rate: number;
  avg_intent_score: number;
}

export interface LeadUpdate {
  follow_up_status?: 'new' | 'contacted' | 'qualified' | 'not_interested' | 'converted';
  follow_up_notes?: string;
  tags?: string[];
  is_starred?: boolean;
  contact_notes?: string;
}

// WebSocket event payloads
export interface LeadCapturedEvent {
  id: string;
  user_id: string;
  user_name: string | null;
  user_email: string | null;
  user_company: string | null;
  user_title: string | null;
  intent_score: number;
  intent_level: 'hot' | 'warm' | 'cold';
  interaction_type: string;
  created_at: string;
}

export interface LeadIntentUpdatedEvent {
  lead_id: string;
  intent_score: number;
  intent_level: 'hot' | 'warm' | 'cold';
  interaction_count: number;
}

// Offline lead capture (mobile-specific)
export interface OfflineLead {
  localId: string;
  sponsorId: string;
  eventId: string;
  name: string;
  email: string;
  company?: string;
  title?: string;
  phone?: string;
  notes?: string;
  scannedAt: string;
  synced: boolean;
  syncError?: string;
}
