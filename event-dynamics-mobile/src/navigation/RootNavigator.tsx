import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { useAuthStore } from '@/store/auth.store';
import { ErrorBoundary } from '@/components/ui/ErrorBoundary';
import { ThemeProvider } from '@/theme/ThemeProvider';
import { useScreenTracking } from '@/hooks/useScreenTracking';
import { AuthStack } from './AuthStack';
import { MainTabs, SponsorNavigator } from './MainTabs';
import { OrganizerNavigator } from './OrganizerStack';
import { RootStackParamList } from './types';

const Stack = createNativeStackNavigator<RootStackParamList>();

const linking = {
  prefixes: ['eventdynamics://', 'https://eventdynamics.app'],
  config: {
    screens: {
      Auth: {
        path: 'auth',
        screens: {
          Login: 'login',
          Register: 'register',
          ForgotPassword: 'forgot-password',
          ResetPassword: 'reset-password/:token',
          TwoFactor: 'two-factor/:userId',
        },
      },
      Main: {
        path: '',
        screens: {
          HomeTab: {
            path: 'home',
            screens: {
              AttendeeHome: '',
              EventHub: 'events/:eventId',
              SessionDetail: 'events/:eventId/sessions/:sessionId',
              SessionLive: 'events/:eventId/sessions/:sessionId/live',
              BreakoutRoom: 'events/:eventId/sessions/:sessionId/breakout/:roomId',
              AttendeeList: 'events/:eventId/attendees',
              AttendeeProfile: 'events/:eventId/attendees/:userId',
              GamificationHub: 'events/:eventId/gamification',
              Leaderboard: 'events/:eventId/leaderboard',
              Achievements: 'events/:eventId/achievements',
              Teams: 'events/:eventId/teams',
              ExpoHall: 'events/:eventId/expo',
              BoothDetail: 'events/:eventId/booths/:boothId',
            },
          },
          ExploreTab: {
            path: 'explore',
            screens: {
              EventBrowse: '',
              PublicEventDetail: ':eventId',
              TicketSelection: ':eventId/tickets',
              Checkout: ':eventId/checkout',
              CheckoutConfirmation: ':eventId/confirmation',
            },
          },
          NetworkingTab: {
            path: 'network',
            screens: {
              ConnectionsList: '',
              DirectMessages: 'messages',
              Conversation: 'messages/:userId',
              UserProfile: 'users/:userId',
            },
          },
          NotificationsTab: {
            path: 'notifications',
            screens: {
              NotificationsList: '',
              NotificationPreferences: 'preferences',
            },
          },
          ProfileTab: {
            path: 'profile',
            screens: {
              ProfileHome: '',
              EditProfile: 'edit',
              MyTickets: 'tickets',
              Settings: 'settings',
            },
          },
        },
      },
      SponsorPortal: {
        path: 'sponsor/:sponsorId/:eventId',
        screens: {
          SponsorDashboard: '',
          LeadCapture: 'leads/capture',
          LeadList: 'leads',
          LeadDetail: 'leads/:leadId',
          LeadExport: 'leads/export',
          SponsorAnalytics: 'analytics',
          SponsorMessages: 'messages',
          BoothManagement: 'booth',
        },
      },
      OrganizerPortal: {
        path: 'organizer',
        screens: {
          OrganizerDashboard: '',
          OrganizerEventDetail: ':eventId',
          LiveMonitor: ':eventId/live',
          SessionControl: ':eventId/sessions/:sessionId',
          CheckInScanner: ':eventId/checkin',
          IncidentList: ':eventId/incidents',
          AnalyticsSnapshot: ':eventId/analytics',
        },
      },
    },
  },
};

function SafeMainTabs() {
  return (
    <ErrorBoundary>
      <MainTabs />
    </ErrorBoundary>
  );
}

function SafeSponsorNavigator(props: { route?: { params?: { sponsorId?: string; eventId?: string; sponsorName?: string } } }) {
  return (
    <ErrorBoundary>
      <SponsorNavigator {...props} />
    </ErrorBoundary>
  );
}

function SafeOrganizerNavigator() {
  return (
    <ErrorBoundary>
      <OrganizerNavigator />
    </ErrorBoundary>
  );
}

function SafeAuthStack() {
  return (
    <ErrorBoundary>
      <AuthStack />
    </ErrorBoundary>
  );
}

export function RootNavigator() {
  const token = useAuthStore((state) => state.token);
  const isLoggedIn = !!token;
  const { onReady, onStateChange } = useScreenTracking();

  return (
    <ThemeProvider>
      <NavigationContainer
        linking={linking}
        onReady={onReady}
        onStateChange={onStateChange}
      >
        <Stack.Navigator screenOptions={{ headerShown: false }}>
          {isLoggedIn ? (
            <>
              <Stack.Screen name="Main" component={SafeMainTabs} />
              <Stack.Screen
                name="SponsorPortal"
                component={SafeSponsorNavigator}
                options={{ animation: 'slide_from_bottom' }}
              />
              <Stack.Screen
                name="OrganizerPortal"
                component={SafeOrganizerNavigator}
                options={{ animation: 'slide_from_bottom' }}
              />
            </>
          ) : (
            <Stack.Screen name="Auth" component={SafeAuthStack} />
          )}
        </Stack.Navigator>
      </NavigationContainer>
    </ThemeProvider>
  );
}
