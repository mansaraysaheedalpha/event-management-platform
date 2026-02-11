// Type-safe navigation param types for every route in the app

export type RootStackParamList = {
  Auth: undefined;
  Main: undefined;
  Onboarding: undefined;
  SponsorPortal: { sponsorId: string; eventId: string; sponsorName: string };
  OrganizerPortal: undefined;
};

export type AuthStackParamList = {
  Login: undefined;
  Register: undefined;
  ForgotPassword: undefined;
  ResetPassword: { token: string };
  TwoFactor: { userId: string; email?: string };
};

export type MainTabParamList = {
  HomeTab: undefined;
  ExploreTab: undefined;
  NetworkingTab: undefined;
  NotificationsTab: undefined;
  ProfileTab: undefined;
};

export type HomeStackParamList = {
  AttendeeHome: undefined;
  EventHub: { eventId: string };
  SessionDetail: { eventId: string; sessionId: string };
  SessionLive: {
    eventId: string;
    sessionId: string;
    sessionTitle: string;
    chatOpen: boolean;
    qaOpen: boolean;
    pollsOpen: boolean;
    reactionsOpen: boolean;
  };
  BreakoutRoom: { eventId: string; sessionId: string; roomId: string };
  AttendeeList: { eventId: string };
  AttendeeProfile: { eventId: string; userId: string };
  ExpoHall: { eventId: string };
  BoothDetail: { eventId: string; boothId: string };
  GamificationHub: { eventId: string; sessionId: string };
  Leaderboard: { eventId: string; sessionId: string };
  Achievements: { eventId: string; sessionId: string };
  Teams: { eventId: string; sessionId: string };
};

export type ExploreStackParamList = {
  EventBrowse: undefined;
  PublicEventDetail: { eventId: string };
  TicketSelection: { eventId: string };
  Checkout: { eventId: string; orderId: string; clientSecret: string };
  CheckoutConfirmation: { orderNumber: string; eventId: string };
};

export type NetworkingStackParamList = {
  ConnectionsList: undefined;
  DirectMessages: undefined;
  Conversation: { userId: string; userName: string };
  UserProfile: { userId: string };
};

export type NotificationsStackParamList = {
  NotificationsList: undefined;
  NotificationPreferences: undefined;
};

export type ProfileStackParamList = {
  ProfileHome: undefined;
  EditProfile: undefined;
  MyTickets: undefined;
  MyOffers: undefined;
  Settings: undefined;
  ChangePassword: undefined;
};

// Organizer stack (accessible via profile or separate flow)
export type OrganizerStackParamList = {
  OrganizerDashboard: undefined;
  OrganizerEventDetail: { eventId: string };
  LiveMonitor: { eventId: string };
  SessionControl: { eventId: string; sessionId: string };
  CheckInScanner: { eventId: string };
  IncidentList: { eventId: string };
  AnalyticsSnapshot: { eventId: string };
};

// Sponsor portal stack (accessible via profile or deep link)
export type SponsorStackParamList = {
  SponsorDashboard: { sponsorId: string; eventId: string; sponsorName: string };
  LeadCapture: { sponsorId: string; eventId: string };
  LeadList: { sponsorId: string; eventId: string };
  LeadDetail: { sponsorId: string; eventId: string; leadId: string };
  LeadExport: { sponsorId: string; eventId: string };
  SponsorAnalytics: { sponsorId: string; eventId: string };
  SponsorMessages: { sponsorId: string; eventId: string };
  BoothManagement: { sponsorId: string; eventId: string };
};
