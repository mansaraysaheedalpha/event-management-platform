import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { OrganizerStackParamList } from './types';
import { colors } from '@/theme';

import { OrganizerDashboardScreen } from '@/screens/organizer/OrganizerDashboardScreen';
import { OrganizerEventDetailScreen } from '@/screens/organizer/OrganizerEventDetailScreen';
import { LiveMonitorScreen } from '@/screens/organizer/LiveMonitorScreen';
import { SessionControlScreen } from '@/screens/organizer/SessionControlScreen';
import { CheckInScannerScreen } from '@/screens/organizer/CheckInScannerScreen';
import { IncidentListScreen } from '@/screens/organizer/IncidentListScreen';
import { AnalyticsSnapshotScreen } from '@/screens/organizer/AnalyticsSnapshotScreen';

const Stack = createNativeStackNavigator<OrganizerStackParamList>();

const screenOptions = {
  headerShown: false,
  contentStyle: { backgroundColor: colors.background },
  animation: 'slide_from_right' as const,
};

export function OrganizerNavigator() {
  return (
    <Stack.Navigator screenOptions={screenOptions}>
      <Stack.Screen name="OrganizerDashboard" component={OrganizerDashboardScreen} />
      <Stack.Screen name="OrganizerEventDetail" component={OrganizerEventDetailScreen} />
      <Stack.Screen name="LiveMonitor" component={LiveMonitorScreen} />
      <Stack.Screen name="SessionControl" component={SessionControlScreen} />
      <Stack.Screen name="CheckInScanner" component={CheckInScannerScreen} options={{ animation: 'slide_from_bottom' }} />
      <Stack.Screen name="IncidentList" component={IncidentListScreen} />
      <Stack.Screen name="AnalyticsSnapshot" component={AnalyticsSnapshotScreen} />
    </Stack.Navigator>
  );
}
