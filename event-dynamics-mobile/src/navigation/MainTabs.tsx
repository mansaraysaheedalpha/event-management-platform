import React, { useCallback } from 'react';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { MainTabParamList, HomeStackParamList, ExploreStackParamList, NetworkingStackParamList, NotificationsStackParamList, ProfileStackParamList, SponsorStackParamList } from './types';
import { colors, useTheme } from '@/theme';

// Screen imports
import { AttendeeHomeScreen } from '@/screens/attendee/AttendeeHomeScreen';
import { EventHubScreen } from '@/screens/attendee/EventHubScreen';
import { SessionDetailScreen } from '@/screens/attendee/SessionDetailScreen';
import { EventBrowseScreen } from '@/screens/explore/EventBrowseScreen';
import { PublicEventDetailScreen } from '@/screens/explore/PublicEventDetailScreen';
import { TicketSelectionScreen } from '@/screens/explore/TicketSelectionScreen';
import { CheckoutScreen } from '@/screens/explore/CheckoutScreen';
import { CheckoutConfirmationScreen } from '@/screens/explore/CheckoutConfirmationScreen';
import { ConnectionsListScreen } from '@/screens/networking/ConnectionsListScreen';
import { DirectMessagesScreen } from '@/screens/networking/DirectMessagesScreen';
import { ConversationScreen } from '@/screens/networking/ConversationScreen';
import { UserProfileScreen } from '@/screens/networking/UserProfileScreen';
import { NotificationsListScreen } from '@/screens/notifications/NotificationsListScreen';
import { NotificationPreferencesScreen } from '@/screens/notifications/NotificationPreferencesScreen';
import { useNotificationStore } from '@/store/notification.store';
import { ProfileHomeScreen } from '@/screens/profile/ProfileHomeScreen';
import { EditProfileScreen } from '@/screens/profile/EditProfileScreen';
import { MyTicketsScreen } from '@/screens/profile/MyTicketsScreen';
import { SettingsScreen } from '@/screens/profile/SettingsScreen';
import { AttendeeListScreen } from '@/screens/attendee/AttendeeListScreen';
import { AttendeeProfileScreen } from '@/screens/attendee/AttendeeProfileScreen';
import { SessionLiveScreen } from '@/screens/session/SessionLiveScreen';
import { BreakoutRoomScreen } from '@/screens/breakout/BreakoutRoomScreen';
import { GamificationHubScreen } from '@/screens/gamification/GamificationHubScreen';
import { LeaderboardScreen } from '@/screens/gamification/LeaderboardScreen';
import { AchievementsScreen } from '@/screens/gamification/AchievementsScreen';
import { TeamScreen } from '@/screens/gamification/TeamScreen';
import { ExpoHallScreen } from '@/screens/expo/ExpoHallScreen';
import { BoothDetailScreen } from '@/screens/expo/BoothDetailScreen';
import { SponsorDashboardScreen } from '@/screens/sponsor/SponsorDashboardScreen';
import { LeadCaptureScreen } from '@/screens/sponsor/LeadCaptureScreen';
import { LeadListScreen } from '@/screens/sponsor/LeadListScreen';
import { LeadDetailScreen } from '@/screens/sponsor/LeadDetailScreen';
import { LeadExportScreen } from '@/screens/sponsor/LeadExportScreen';
import { SponsorAnalyticsScreen } from '@/screens/sponsor/SponsorAnalyticsScreen';
import { SponsorMessagesScreen } from '@/screens/sponsor/SponsorMessagesScreen';
import { BoothManagementScreen } from '@/screens/sponsor/BoothManagementScreen';
import { DirectMessagesProvider } from '@/context/DirectMessagesContext';

// Video infrastructure
import { DailyProvider } from '@/providers/DailyProvider';
import { MiniPlayer } from '@/components/video/MiniPlayer';
import { useVideoSessionStore } from '@/store/videoSession.store';

// Tab icon component
import { TabIcon } from '@/components/ui/TabIcon';

const Tab = createBottomTabNavigator<MainTabParamList>();
const HomeStack = createNativeStackNavigator<HomeStackParamList>();
const ExploreStack = createNativeStackNavigator<ExploreStackParamList>();
const NetworkStack = createNativeStackNavigator<NetworkingStackParamList>();
const NotifStack = createNativeStackNavigator<NotificationsStackParamList>();
const ProfStack = createNativeStackNavigator<ProfileStackParamList>();
const SponStack = createNativeStackNavigator<SponsorStackParamList>();

const screenOptions = {
  headerShown: false,
  contentStyle: { backgroundColor: colors.background },
  animation: 'slide_from_right' as const,
};

function HomeNavigator() {
  return (
    <HomeStack.Navigator screenOptions={screenOptions}>
      <HomeStack.Screen name="AttendeeHome" component={AttendeeHomeScreen} />
      <HomeStack.Screen name="EventHub" component={EventHubScreen} />
      <HomeStack.Screen name="SessionDetail" component={SessionDetailScreen} />
      <HomeStack.Screen name="SessionLive" component={SessionLiveScreen} options={{ animation: 'slide_from_bottom' }} />
      <HomeStack.Screen name="BreakoutRoom" component={BreakoutRoomScreen} options={{ animation: 'slide_from_bottom' }} />
      <HomeStack.Screen name="AttendeeList" component={AttendeeListScreen} />
      <HomeStack.Screen name="AttendeeProfile" component={AttendeeProfileScreen} />
      <HomeStack.Screen name="GamificationHub" component={GamificationHubScreen} />
      <HomeStack.Screen name="Leaderboard" component={LeaderboardScreen} />
      <HomeStack.Screen name="Achievements" component={AchievementsScreen} />
      <HomeStack.Screen name="Teams" component={TeamScreen} />
      <HomeStack.Screen name="ExpoHall" component={ExpoHallScreen} />
      <HomeStack.Screen name="BoothDetail" component={BoothDetailScreen} />
    </HomeStack.Navigator>
  );
}

function ExploreNavigator() {
  return (
    <ExploreStack.Navigator screenOptions={screenOptions}>
      <ExploreStack.Screen name="EventBrowse" component={EventBrowseScreen} />
      <ExploreStack.Screen name="PublicEventDetail" component={PublicEventDetailScreen} />
      <ExploreStack.Screen name="TicketSelection" component={TicketSelectionScreen} />
      <ExploreStack.Screen name="Checkout" component={CheckoutScreen} />
      <ExploreStack.Screen name="CheckoutConfirmation" component={CheckoutConfirmationScreen} options={{ gestureEnabled: false }} />
    </ExploreStack.Navigator>
  );
}

function NetworkNavigator() {
  return (
    <DirectMessagesProvider>
      <NetworkStack.Navigator screenOptions={screenOptions}>
        <NetworkStack.Screen name="ConnectionsList" component={ConnectionsListScreen} />
        <NetworkStack.Screen name="DirectMessages" component={DirectMessagesScreen} />
        <NetworkStack.Screen name="Conversation" component={ConversationScreen} />
        <NetworkStack.Screen name="UserProfile" component={UserProfileScreen} />
      </NetworkStack.Navigator>
    </DirectMessagesProvider>
  );
}

function NotificationsNavigator() {
  return (
    <NotifStack.Navigator screenOptions={screenOptions}>
      <NotifStack.Screen name="NotificationsList" component={NotificationsListScreen} />
      <NotifStack.Screen name="NotificationPreferences" component={NotificationPreferencesScreen} />
    </NotifStack.Navigator>
  );
}

function ProfileNavigator() {
  return (
    <ProfStack.Navigator screenOptions={screenOptions}>
      <ProfStack.Screen name="ProfileHome" component={ProfileHomeScreen} />
      <ProfStack.Screen name="EditProfile" component={EditProfileScreen} />
      <ProfStack.Screen name="MyTickets" component={MyTicketsScreen} />
      <ProfStack.Screen name="Settings" component={SettingsScreen} />
    </ProfStack.Navigator>
  );
}

export function SponsorNavigator({ route }: { route?: { params?: { sponsorId?: string; eventId?: string; sponsorName?: string } } }) {
  const initialParams = route?.params;
  return (
    <SponStack.Navigator screenOptions={screenOptions}>
      <SponStack.Screen
        name="SponsorDashboard"
        component={SponsorDashboardScreen}
        initialParams={initialParams as SponsorStackParamList['SponsorDashboard']}
      />
      <SponStack.Screen name="LeadCapture" component={LeadCaptureScreen} />
      <SponStack.Screen name="LeadList" component={LeadListScreen} />
      <SponStack.Screen name="LeadDetail" component={LeadDetailScreen} />
      <SponStack.Screen name="LeadExport" component={LeadExportScreen} />
      <SponStack.Screen name="SponsorAnalytics" component={SponsorAnalyticsScreen} />
      <SponStack.Screen name="SponsorMessages" component={SponsorMessagesScreen} />
      <SponStack.Screen name="BoothManagement" component={BoothManagementScreen} />
    </SponStack.Navigator>
  );
}

function MiniPlayerWrapper() {
  const navigation = useNavigation<NativeStackNavigationProp<HomeStackParamList>>();
  const { activeSessionId, activeEventId, activeSessionTitle } = useVideoSessionStore();

  const handleMaximize = useCallback(() => {
    if (activeSessionId && activeEventId && activeSessionTitle) {
      useVideoSessionStore.getState().maximizePlayer();
      navigation.navigate('SessionLive', {
        sessionId: activeSessionId,
        eventId: activeEventId,
        sessionTitle: activeSessionTitle,
        chatOpen: false,
        qaOpen: false,
        pollsOpen: false,
        reactionsOpen: false,
      });
    }
  }, [activeSessionId, activeEventId, activeSessionTitle, navigation]);

  return <MiniPlayer onMaximize={handleMaximize} />;
}

export function MainTabs() {
  const unreadCount = useNotificationStore((s) => s.unreadCount);
  const { colors: c } = useTheme();

  return (
    <DailyProvider>
    <Tab.Navigator
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.primary.gold,
        tabBarInactiveTintColor: c.neutral[400],
        tabBarStyle: {
          backgroundColor: c.background,
          borderTopColor: c.border,
          borderTopWidth: 1,
          paddingBottom: 4,
          paddingTop: 4,
          height: 56,
        },
        tabBarLabelStyle: {
          fontSize: 11,
          fontWeight: '600',
        },
      }}
    >
      <Tab.Screen
        name="HomeTab"
        component={HomeNavigator}
        options={{
          tabBarLabel: 'Home',
          tabBarIcon: ({ color, size }) => (
            <TabIcon name="home" color={color} size={size} />
          ),
        }}
      />
      <Tab.Screen
        name="ExploreTab"
        component={ExploreNavigator}
        options={{
          tabBarLabel: 'Explore',
          tabBarIcon: ({ color, size }) => (
            <TabIcon name="search" color={color} size={size} />
          ),
        }}
      />
      <Tab.Screen
        name="NetworkingTab"
        component={NetworkNavigator}
        options={{
          tabBarLabel: 'Network',
          tabBarIcon: ({ color, size }) => (
            <TabIcon name="users" color={color} size={size} />
          ),
        }}
      />
      <Tab.Screen
        name="NotificationsTab"
        component={NotificationsNavigator}
        options={{
          tabBarLabel: 'Alerts',
          tabBarIcon: ({ color, size }) => (
            <TabIcon name="bell" color={color} size={size} />
          ),
          tabBarBadge: unreadCount > 0
            ? unreadCount > 99 ? '99+' : unreadCount
            : undefined,
          tabBarBadgeStyle: { backgroundColor: colors.destructive, fontSize: 10 },
        }}
      />
      <Tab.Screen
        name="ProfileTab"
        component={ProfileNavigator}
        options={{
          tabBarLabel: 'Profile',
          tabBarIcon: ({ color, size }) => (
            <TabIcon name="user" color={color} size={size} />
          ),
        }}
      />
    </Tab.Navigator>
    <MiniPlayerWrapper />
    </DailyProvider>
  );
}
