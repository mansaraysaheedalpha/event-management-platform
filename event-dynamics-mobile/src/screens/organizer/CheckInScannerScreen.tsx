import React, { useState, useCallback, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  TextInput,
  FlatList,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { CameraView, useCameraPermissions, BarcodeScanningResult } from 'expo-camera';
import { useQuery, useMutation } from '@apollo/client/react';
import * as Haptics from 'expo-haptics';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { RouteProp } from '@react-navigation/native';
import {
  GET_REGISTRATIONS_BY_EVENT_QUERY,
  CHECK_IN_TICKET_MUTATION,
} from '@/graphql';
import { Card, Badge, Button, ScreenSkeleton } from '@/components/ui';
import { colors, typography } from '@/theme';
import type { OrganizerStackParamList } from '@/navigation/types';

type Nav = NativeStackNavigationProp<OrganizerStackParamList, 'CheckInScanner'>;
type Route = RouteProp<OrganizerStackParamList, 'CheckInScanner'>;

interface Registration {
  id: string;
  status: string;
  ticketCode: string;
  checkedInAt: string | null;
  guestEmail?: string;
  guestName?: string;
  user?: {
    id: string;
    first_name: string;
    last_name: string;
    email: string;
  };
}

interface RegistrationsResponse {
  registrationsByEvent: Registration[];
}

interface CheckInResponse {
  checkInTicket: {
    id: string;
    status: string;
    ticketCode: string;
    checkedInAt: string;
  };
}

type ScanMode = 'qr' | 'manual';

interface ScanResult {
  type: 'success' | 'error' | 'already';
  name: string;
  message: string;
}

export function CheckInScannerScreen() {
  const navigation = useNavigation<Nav>();
  const route = useRoute<Route>();
  const { eventId } = route.params;

  const [permission, requestPermission] = useCameraPermissions();
  const [mode, setMode] = useState<ScanMode>('qr');
  const [searchQuery, setSearchQuery] = useState('');
  const [scanResult, setScanResult] = useState<ScanResult | null>(null);
  const scanLockRef = useRef(false);

  const { data, loading, refetch } = useQuery<RegistrationsResponse>(
    GET_REGISTRATIONS_BY_EVENT_QUERY,
    {
      variables: { eventId },
      fetchPolicy: 'cache-and-network',
    },
  );

  const [checkIn, { loading: checkingIn }] = useMutation<CheckInResponse>(
    CHECK_IN_TICKET_MUTATION,
  );

  const registrations = data?.registrationsByEvent ?? [];
  const checkedInCount = registrations.filter((r) => r.checkedInAt).length;
  const totalCount = registrations.length;

  const filteredRegistrations = searchQuery.trim()
    ? registrations.filter((r) => {
        const q = searchQuery.toLowerCase();
        const name = r.user
          ? `${r.user.first_name} ${r.user.last_name}`.toLowerCase()
          : (r.guestName ?? '').toLowerCase();
        const email = (r.user?.email ?? r.guestEmail ?? '').toLowerCase();
        return name.includes(q) || email.includes(q) || r.ticketCode.toLowerCase().includes(q);
      })
    : registrations;

  const getAttendeeName = useCallback((reg: Registration): string => {
    if (reg.user) return `${reg.user.first_name} ${reg.user.last_name}`;
    return reg.guestName ?? 'Guest';
  }, []);

  const performCheckIn = useCallback(
    async (ticketCode: string) => {
      // Find registration by ticket code
      const reg = registrations.find(
        (r) => r.ticketCode.toLowerCase() === ticketCode.toLowerCase(),
      );

      if (!reg) {
        setScanResult({ type: 'error', name: 'Unknown', message: 'Ticket not found' });
        Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
        return;
      }

      const name = getAttendeeName(reg);

      if (reg.checkedInAt) {
        setScanResult({ type: 'already', name, message: 'Already checked in' });
        Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
        return;
      }

      try {
        await checkIn({
          variables: { input: { ticketCode, eventId } },
        });
        setScanResult({ type: 'success', name, message: 'Checked in successfully' });
        Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
        refetch();
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Check-in failed';
        setScanResult({ type: 'error', name, message: msg });
        Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
      }
    },
    [registrations, checkIn, eventId, refetch, getAttendeeName],
  );

  const handleBarcodeScan = useCallback(
    (result: BarcodeScanningResult) => {
      if (scanLockRef.current) return;
      scanLockRef.current = true;

      const ticketCode = result.data.trim();
      performCheckIn(ticketCode);

      // Unlock after 2 seconds to prevent rapid re-scans
      setTimeout(() => {
        scanLockRef.current = false;
      }, 2000);
    },
    [performCheckIn],
  );

  const handleManualCheckIn = useCallback(
    (reg: Registration) => {
      const name = getAttendeeName(reg);
      if (reg.checkedInAt) {
        Alert.alert('Already Checked In', `${name} is already checked in.`);
        return;
      }
      Alert.alert('Check In', `Check in ${name}?`, [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Check In',
          onPress: () => performCheckIn(reg.ticketCode),
        },
      ]);
    },
    [performCheckIn, getAttendeeName],
  );

  const dismissResult = useCallback(() => {
    setScanResult(null);
  }, []);

  // Camera permission handling
  if (mode === 'qr' && !permission) {
    return <ScreenSkeleton count={1} header={false} />;
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()}>
          <Text style={styles.backText}>← Back</Text>
        </TouchableOpacity>
        <View style={styles.checkInCount}>
          <Text style={styles.countValue}>{checkedInCount}</Text>
          <Text style={styles.countLabel}>/ {totalCount} checked in</Text>
        </View>
      </View>

      <Text style={styles.title}>Check-In Scanner</Text>

      {/* Mode toggle */}
      <View style={styles.modeToggle}>
        <TouchableOpacity
          style={[styles.modeButton, mode === 'qr' && styles.modeActive]}
          onPress={() => setMode('qr')}
        >
          <Text style={[styles.modeText, mode === 'qr' && styles.modeTextActive]}>
            QR Scan
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.modeButton, mode === 'manual' && styles.modeActive]}
          onPress={() => setMode('manual')}
        >
          <Text style={[styles.modeText, mode === 'manual' && styles.modeTextActive]}>
            Manual Search
          </Text>
        </TouchableOpacity>
      </View>

      {mode === 'qr' ? (
        <View style={styles.scannerContainer}>
          {permission?.granted ? (
            <CameraView
              style={styles.camera}
              barcodeScannerSettings={{ barcodeTypes: ['qr'] }}
              onBarcodeScanned={scanResult ? undefined : handleBarcodeScan}
            />
          ) : (
            <View style={styles.permissionContainer}>
              <Text style={styles.permissionText}>
                Camera access is needed to scan QR codes.
              </Text>
              <Button title="Grant Permission" onPress={requestPermission} variant="primary" />
            </View>
          )}

          {/* Scan result overlay */}
          {scanResult && (
            <TouchableOpacity
              style={[
                styles.resultOverlay,
                scanResult.type === 'success' && styles.resultSuccess,
                scanResult.type === 'error' && styles.resultError,
                scanResult.type === 'already' && styles.resultWarning,
              ]}
              onPress={dismissResult}
              activeOpacity={0.9}
            >
              <Text style={styles.resultIcon}>
                {scanResult.type === 'success' ? '✓' : scanResult.type === 'already' ? '⚠' : '✗'}
              </Text>
              <Text style={styles.resultName}>{scanResult.name}</Text>
              <Text style={styles.resultMessage}>{scanResult.message}</Text>
              <Text style={styles.resultDismiss}>Tap to scan next</Text>
            </TouchableOpacity>
          )}
        </View>
      ) : (
        <View style={styles.manualContainer}>
          <View style={styles.searchBar}>
            <TextInput
              style={styles.searchInput}
              placeholder="Search by name, email, or ticket code..."
              placeholderTextColor={colors.neutral[500]}
              value={searchQuery}
              onChangeText={setSearchQuery}
              autoCapitalize="none"
              autoCorrect={false}
            />
          </View>

          <FlatList
            data={filteredRegistrations}
            keyExtractor={(item) => item.id}
            renderItem={({ item }) => {
              const name = getAttendeeName(item);
              const email = item.user?.email ?? item.guestEmail ?? '';
              const isCheckedIn = !!item.checkedInAt;

              return (
                <TouchableOpacity
                  onPress={() => handleManualCheckIn(item)}
                  activeOpacity={0.8}
                >
                  <View style={[styles.attendeeRow, isCheckedIn && styles.attendeeCheckedIn]}>
                    <View style={styles.attendeeInfo}>
                      <Text style={styles.attendeeName}>{name}</Text>
                      <Text style={styles.attendeeEmail}>{email}</Text>
                      <Text style={styles.attendeeTicket}>{item.ticketCode}</Text>
                    </View>
                    <Badge
                      variant={isCheckedIn ? 'success' : 'default'}
                      label={isCheckedIn ? 'In' : 'Pending'}
                    />
                  </View>
                </TouchableOpacity>
              );
            }}
            contentContainerStyle={styles.attendeeList}
            showsVerticalScrollIndicator={false}
            ListEmptyComponent={
              <View style={styles.emptyState}>
                <Text style={styles.emptyText}>
                  {searchQuery ? 'No matching attendees found.' : 'No registrations yet.'}
                </Text>
              </View>
            }
          />
        </View>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 24,
    paddingTop: 12,
  },
  backText: { ...typography.body, color: colors.primary.gold, fontWeight: '600' },
  checkInCount: { flexDirection: 'row', alignItems: 'baseline', gap: 4 },
  countValue: { ...typography.h3, color: colors.success },
  countLabel: { ...typography.bodySmall, color: colors.neutral[500] },
  title: { ...typography.h2, color: colors.foreground, paddingHorizontal: 24, paddingTop: 8, paddingBottom: 12 },
  modeToggle: {
    flexDirection: 'row',
    marginHorizontal: 24,
    marginBottom: 16,
    borderRadius: 8,
    backgroundColor: colors.neutral[800],
    padding: 4,
  },
  modeButton: {
    flex: 1,
    paddingVertical: 10,
    alignItems: 'center',
    borderRadius: 6,
  },
  modeActive: { backgroundColor: colors.primary.navy },
  modeText: { ...typography.label, color: colors.neutral[500] },
  modeTextActive: { color: colors.primary.gold },
  scannerContainer: { flex: 1, position: 'relative' },
  camera: { flex: 1 },
  permissionContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
    gap: 16,
  },
  permissionText: { ...typography.body, color: colors.neutral[400], textAlign: 'center' },
  resultOverlay: {
    ...StyleSheet.absoluteFillObject,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: 'rgba(0,0,0,0.85)',
  },
  resultSuccess: { backgroundColor: 'rgba(22, 163, 74, 0.92)' },
  resultError: { backgroundColor: 'rgba(220, 38, 38, 0.92)' },
  resultWarning: { backgroundColor: 'rgba(245, 158, 11, 0.92)' },
  resultIcon: { fontSize: 48, color: '#fff', marginBottom: 12 },
  resultName: { ...typography.h2, color: '#fff', marginBottom: 4 },
  resultMessage: { ...typography.body, color: 'rgba(255,255,255,0.9)', marginBottom: 20 },
  resultDismiss: { ...typography.caption, color: 'rgba(255,255,255,0.6)' },
  manualContainer: { flex: 1 },
  searchBar: { paddingHorizontal: 24, marginBottom: 12 },
  searchInput: {
    ...typography.body,
    color: colors.foreground,
    backgroundColor: colors.neutral[800],
    borderRadius: 8,
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderWidth: 1,
    borderColor: colors.border,
  },
  attendeeList: { paddingHorizontal: 24, paddingBottom: 24 },
  attendeeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  attendeeCheckedIn: { opacity: 0.6 },
  attendeeInfo: { flex: 1 },
  attendeeName: { ...typography.body, color: colors.foreground, fontWeight: '600' },
  attendeeEmail: { ...typography.bodySmall, color: colors.neutral[500] },
  attendeeTicket: { ...typography.caption, color: colors.primary.gold },
  emptyState: { padding: 24, alignItems: 'center' },
  emptyText: { ...typography.body, color: colors.neutral[500], textAlign: 'center' },
});
