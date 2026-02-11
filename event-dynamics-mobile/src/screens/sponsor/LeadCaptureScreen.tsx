import React, { useState, useCallback, useRef, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Alert,
  TextInput,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { CameraView, useCameraPermissions } from 'expo-camera';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { RouteProp } from '@react-navigation/native';
import { useAuthStore } from '@/store/auth.store';
import { useLeadsStore } from '@/store/leads.store';
import { env } from '@/lib/env';
import { Card, Button, Input } from '@/components/ui';
import { colors, typography } from '@/theme';
import type { SponsorStackParamList } from '@/navigation/types';
import type { OfflineLead } from '@/types/leads';

type Nav = NativeStackNavigationProp<SponsorStackParamList, 'LeadCapture'>;
type Route = RouteProp<SponsorStackParamList, 'LeadCapture'>;

type CaptureMode = 'qr' | 'manual';

export function LeadCaptureScreen() {
  const navigation = useNavigation<Nav>();
  const route = useRoute<Route>();
  const { sponsorId, eventId } = route.params;

  const { token } = useAuthStore();
  const { addOfflineLead } = useLeadsStore();
  const [permission, requestPermission] = useCameraPermissions();

  const [mode, setMode] = useState<CaptureMode>('qr');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [scanProcessing, setScanProcessing] = useState(false);
  const scanTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Cleanup scan timeout on unmount
  useEffect(() => {
    return () => {
      if (scanTimeoutRef.current) clearTimeout(scanTimeoutRef.current);
    };
  }, []);

  // Manual form fields
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [company, setCompany] = useState('');
  const [title, setTitle] = useState('');
  const [phone, setPhone] = useState('');
  const [notes, setNotes] = useState('');

  const captureLead = useCallback(
    async (leadData: {
      name?: string;
      email?: string;
      company?: string;
      title?: string;
      phone?: string;
      notes?: string;
      userId?: string;
    }) => {
      setIsSubmitting(true);

      const payload = {
        user_id: leadData.userId || `manual_${Date.now()}`,
        user_name: leadData.name || null,
        user_email: leadData.email || null,
        user_company: leadData.company || null,
        user_title: leadData.title || null,
        interaction_type: 'qr_scan',
        interaction_metadata: {
          phone: leadData.phone || null,
          notes: leadData.notes || null,
          captured_via: 'mobile_app',
        },
      };

      try {
        const response = await fetch(
          `${env.EVENT_SERVICE_URL}/sponsors/events/${eventId}/sponsors/${sponsorId}/capture-lead`,
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              ...(token && { Authorization: `Bearer ${token}` }),
            },
            body: JSON.stringify(payload),
          },
        );

        if (!response.ok) {
          throw new Error(`Failed: ${response.status}`);
        }

        Alert.alert('Lead Captured', `${leadData.name || 'Lead'} has been captured successfully.`);
        // Reset form
        setName('');
        setEmail('');
        setCompany('');
        setTitle('');
        setPhone('');
        setNotes('');
      } catch {
        // Offline fallback — save locally
        const offlineLead: OfflineLead = {
          localId: `offline_${Date.now()}_${Math.random().toString(36).slice(2)}`,
          sponsorId,
          eventId,
          name: leadData.name || '',
          email: leadData.email || '',
          company: leadData.company,
          title: leadData.title,
          phone: leadData.phone,
          notes: leadData.notes,
          scannedAt: new Date().toISOString(),
          synced: false,
        };
        addOfflineLead(offlineLead);
        Alert.alert(
          'Saved Offline',
          'Lead saved locally. It will sync when you are back online.',
        );
      } finally {
        setIsSubmitting(false);
      }
    },
    [token, sponsorId, eventId, addOfflineLead],
  );

  const handleBarCodeScanned = useCallback(
    ({ data }: { data: string }) => {
      if (scanProcessing) return;
      setScanProcessing(true);

      // QR data could be JSON with user info or just a userId
      try {
        const parsed = JSON.parse(data);
        captureLead({
          userId: parsed.userId || parsed.id,
          name: parsed.name,
          email: parsed.email,
          company: parsed.company,
          title: parsed.title,
        });
      } catch {
        // Plain string — treat as userId
        captureLead({ userId: data });
      }

      scanTimeoutRef.current = setTimeout(() => setScanProcessing(false), 2000);
    },
    [scanProcessing, captureLead],
  );

  const handleManualSubmit = useCallback(() => {
    if (!name.trim() && !email.trim()) {
      Alert.alert('Required', 'Please enter at least a name or email.');
      return;
    }
    captureLead({ name, email, company, title, phone, notes });
  }, [name, email, company, title, phone, notes, captureLead]);

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()}>
          <Text style={styles.backText}>Back</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Capture Lead</Text>
        <View style={{ width: 40 }} />
      </View>

      {/* Mode tabs */}
      <View style={styles.tabRow}>
        <TouchableOpacity
          style={[styles.tab, mode === 'qr' && styles.tabActive]}
          onPress={() => setMode('qr')}
        >
          <Text style={[styles.tabText, mode === 'qr' && styles.tabTextActive]}>
            QR Scanner
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.tab, mode === 'manual' && styles.tabActive]}
          onPress={() => setMode('manual')}
        >
          <Text style={[styles.tabText, mode === 'manual' && styles.tabTextActive]}>
            Manual Entry
          </Text>
        </TouchableOpacity>
      </View>

      {mode === 'qr' ? (
        <View style={styles.scannerContainer}>
          {!permission?.granted ? (
            <View style={styles.permissionContainer}>
              <Text style={styles.permissionText}>
                Camera permission is needed to scan QR codes
              </Text>
              <Button
                title="Grant Permission"
                onPress={requestPermission}
                variant="primary"
              />
            </View>
          ) : (
            <>
              <CameraView
                style={styles.camera}
                barcodeScannerSettings={{
                  barcodeTypes: ['qr'],
                }}
                onBarcodeScanned={scanProcessing ? undefined : handleBarCodeScanned}
              />
              <View style={styles.scanOverlay}>
                <View style={styles.scanFrame} />
                <Text style={styles.scanHint}>
                  Point camera at attendee badge QR code
                </Text>
              </View>
            </>
          )}
        </View>
      ) : (
        <KeyboardAvoidingView
          style={{ flex: 1 }}
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        >
          <ScrollView contentContainerStyle={styles.formContainer}>
            <Input label="Name" value={name} onChangeText={setName} placeholder="Full name" />
            <Input
              label="Email"
              value={email}
              onChangeText={setEmail}
              placeholder="email@company.com"
              keyboardType="email-address"
              autoCapitalize="none"
            />
            <Input label="Company" value={company} onChangeText={setCompany} placeholder="Company name" />
            <Input label="Job Title" value={title} onChangeText={setTitle} placeholder="Job title" />
            <Input
              label="Phone"
              value={phone}
              onChangeText={setPhone}
              placeholder="+1 (555) 000-0000"
              keyboardType="phone-pad"
            />
            <Input
              label="Notes"
              value={notes}
              onChangeText={setNotes}
              placeholder="Add notes..."
              multiline
              numberOfLines={3}
              style={{ height: 80, textAlignVertical: 'top' }}
            />
            <Button
              title="Capture Lead"
              onPress={handleManualSubmit}
              loading={isSubmitting}
              fullWidth
              style={{ marginTop: 8 }}
            />
          </ScrollView>
        </KeyboardAvoidingView>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  backText: { ...typography.label, color: colors.primary.gold },
  headerTitle: { ...typography.h4, color: colors.foreground },
  tabRow: {
    flexDirection: 'row',
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  tab: { flex: 1, paddingVertical: 12, alignItems: 'center' },
  tabActive: { borderBottomWidth: 2, borderBottomColor: colors.primary.gold },
  tabText: { ...typography.label, color: colors.neutral[400] },
  tabTextActive: { color: colors.primary.gold },
  scannerContainer: { flex: 1 },
  camera: { flex: 1 },
  scanOverlay: {
    ...StyleSheet.absoluteFillObject,
    justifyContent: 'center',
    alignItems: 'center',
  },
  scanFrame: {
    width: 250,
    height: 250,
    borderWidth: 2,
    borderColor: colors.primary.gold,
    borderRadius: 16,
  },
  scanHint: {
    ...typography.body,
    color: '#fff',
    marginTop: 24,
    textAlign: 'center',
    textShadowColor: 'rgba(0,0,0,0.5)',
    textShadowRadius: 4,
    textShadowOffset: { width: 0, height: 1 },
  },
  permissionContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  permissionText: {
    ...typography.body,
    color: colors.neutral[500],
    textAlign: 'center',
    marginBottom: 16,
  },
  formContainer: { padding: 20 },
});
