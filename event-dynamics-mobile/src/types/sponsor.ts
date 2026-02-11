// Types for Sponsor management — ported from web
// ../globalconnect/src/hooks/use-sponsor-management.ts

export interface Sponsor {
  id: string;
  organizationId: string;
  eventId: string;
  tierId: string | null;
  companyName: string;
  companyDescription: string | null;
  companyWebsite: string | null;
  companyLogoUrl: string | null;
  contactName: string | null;
  contactEmail: string | null;
  contactPhone: string | null;
  boothNumber: string | null;
  boothDescription: string | null;
  customBoothUrl: string | null;
  socialLinks: Record<string, string>;
  marketingAssets: MarketingAsset[];
  leadCaptureEnabled: boolean;
  leadNotificationEmail: string | null;
  customFields: Record<string, unknown>;
  isActive: boolean;
  isFeatured: boolean;
  isArchived: boolean;
  createdAt: string;
  updatedAt: string;
  tier?: SponsorTier;
}

export interface SponsorTier {
  id: string;
  name: string;
  displayOrder: number;
  color: string | null;
  benefits: string[];
  boothSize: string | null;
  logoPlacement: string | null;
  maxRepresentatives: number;
  canCaptureLeads: boolean;
  canExportLeads: boolean;
  canSendMessages: boolean;
  priceCents: number | null;
  currency: string | null;
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface MarketingAsset {
  type: string;
  url: string;
  name: string;
}

export interface SponsorUser {
  id: string;
  sponsorId: string;
  userId: string;
  role: string;
  canViewLeads: boolean;
  canExportLeads: boolean;
  canMessageAttendees: boolean;
  canManageBooth: boolean;
  canInviteOthers: boolean;
  isActive: boolean;
  joinedAt: string;
  lastActiveAt: string | null;
}
