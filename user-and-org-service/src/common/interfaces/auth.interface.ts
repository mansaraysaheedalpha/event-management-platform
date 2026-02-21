//src/common/interfaces/auth.interface.ts
export interface JwtPayload {
  sub: string; // User ID
  email: string;
  orgId: string; // Active organization context
  role: string;
  permissions: string[];
  tier?: 'default' | 'vip';
  preferredLanguage?: string;
  sponsorId?: string;
  orgRequires2FA: boolean;
  is2FAEnabled: boolean;
  isPlatformAdmin?: boolean; // Platform admin access flag
  userType?: string; // For attendee JWTs
}
