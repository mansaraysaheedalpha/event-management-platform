// Video call controls component
// Provides mic, camera, leave, and quality controls

import React, { useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Modal, Alert } from 'react-native';
import { colors } from '@/theme/colors';

interface VideoControlsProps {
  isMicOn: boolean;
  isCameraOn: boolean;
  subtitlesEnabled: boolean;
  onToggleMic: () => void;
  onToggleCamera: () => void;
  onToggleSubtitles: () => void;
  onLeaveCall: () => void;
  onQualityChange: (quality: 'low' | 'medium' | 'high') => void;
  style?: object;
}

export function VideoControls({
  isMicOn,
  isCameraOn,
  subtitlesEnabled,
  onToggleMic,
  onToggleCamera,
  onToggleSubtitles,
  onLeaveCall,
  onQualityChange,
  style,
}: VideoControlsProps) {
  const [showQualityMenu, setShowQualityMenu] = useState(false);
  const [currentQuality, setCurrentQuality] = useState<'low' | 'medium' | 'high'>('medium');

  const handleQualitySelect = (quality: 'low' | 'medium' | 'high') => {
    setCurrentQuality(quality);
    onQualityChange(quality);
    setShowQualityMenu(false);
  };

  const handleLeaveCall = () => {
    Alert.alert('Leave Call', 'Are you sure you want to leave this call?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Leave',
        style: 'destructive',
        onPress: onLeaveCall,
      },
    ]);
  };

  return (
    <View style={[styles.container, style]}>
      <View style={styles.controls}>
        {/* Microphone toggle */}
        <TouchableOpacity
          style={[styles.button, !isMicOn && styles.buttonMuted]}
          onPress={onToggleMic}
          activeOpacity={0.7}
        >
          <Text style={styles.buttonIcon}>{isMicOn ? '🎤' : '🔇'}</Text>
          <Text style={styles.buttonLabel}>Mic</Text>
        </TouchableOpacity>

        {/* Camera toggle */}
        <TouchableOpacity
          style={[styles.button, !isCameraOn && styles.buttonMuted]}
          onPress={onToggleCamera}
          activeOpacity={0.7}
        >
          <Text style={styles.buttonIcon}>{isCameraOn ? '📹' : '📵'}</Text>
          <Text style={styles.buttonLabel}>Camera</Text>
        </TouchableOpacity>

        {/* Subtitle toggle */}
        <TouchableOpacity
          style={[styles.button, subtitlesEnabled && styles.buttonActive]}
          onPress={onToggleSubtitles}
          activeOpacity={0.7}
        >
          <Text style={styles.buttonIcon}>CC</Text>
          <Text style={styles.buttonLabel}>Subs</Text>
        </TouchableOpacity>

        {/* Quality selector */}
        <TouchableOpacity
          style={styles.button}
          onPress={() => setShowQualityMenu(true)}
          activeOpacity={0.7}
        >
          <Text style={styles.buttonIcon}>⚙️</Text>
          <Text style={styles.buttonLabel}>Quality</Text>
        </TouchableOpacity>

        {/* Leave call */}
        <TouchableOpacity style={[styles.button, styles.buttonLeave]} onPress={handleLeaveCall} activeOpacity={0.7}>
          <Text style={styles.buttonIcon}>❌</Text>
          <Text style={styles.buttonLabel}>Leave</Text>
        </TouchableOpacity>
      </View>

      {/* Quality selection modal */}
      <Modal visible={showQualityMenu} transparent animationType="slide" onRequestClose={() => setShowQualityMenu(false)}>
        <TouchableOpacity style={styles.modalOverlay} activeOpacity={1} onPress={() => setShowQualityMenu(false)}>
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>Video Quality</Text>

            <TouchableOpacity
              style={[styles.qualityOption, currentQuality === 'high' && styles.qualityOptionActive]}
              onPress={() => handleQualitySelect('high')}
            >
              <Text style={styles.qualityLabel}>High</Text>
              <Text style={styles.qualityDescription}>Best quality, uses more data</Text>
              {currentQuality === 'high' && <Text style={styles.checkmark}>✓</Text>}
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.qualityOption, currentQuality === 'medium' && styles.qualityOptionActive]}
              onPress={() => handleQualitySelect('medium')}
            >
              <Text style={styles.qualityLabel}>Medium</Text>
              <Text style={styles.qualityDescription}>Balanced quality and data usage</Text>
              {currentQuality === 'medium' && <Text style={styles.checkmark}>✓</Text>}
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.qualityOption, currentQuality === 'low' && styles.qualityOptionActive]}
              onPress={() => handleQualitySelect('low')}
            >
              <Text style={styles.qualityLabel}>Low</Text>
              <Text style={styles.qualityDescription}>Saves data, lower quality</Text>
              {currentQuality === 'low' && <Text style={styles.checkmark}>✓</Text>}
            </TouchableOpacity>

            <TouchableOpacity style={styles.cancelButton} onPress={() => setShowQualityMenu(false)}>
              <Text style={styles.cancelButtonText}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </TouchableOpacity>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: 'rgba(0, 0, 0, 0.8)',
    paddingVertical: 12,
    paddingHorizontal: 16,
  },
  controls: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    alignItems: 'center',
  },
  button: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 12,
    backgroundColor: 'rgba(255, 255, 255, 0.15)',
    minWidth: 60,
  },
  buttonMuted: {
    backgroundColor: colors.destructive,
  },
  buttonActive: {
    backgroundColor: colors.info,
  },
  buttonLeave: {
    backgroundColor: colors.destructive,
  },
  buttonIcon: {
    fontSize: 24,
    marginBottom: 2,
  },
  buttonLabel: {
    color: '#FFFFFF',
    fontSize: 10,
    fontWeight: '500',
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: '#FFFFFF',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    padding: 20,
    paddingBottom: 32,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.primary.navy,
    marginBottom: 16,
    textAlign: 'center',
  },
  qualityOption: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 16,
    paddingHorizontal: 16,
    borderRadius: 12,
    marginBottom: 8,
    backgroundColor: colors.neutral[100],
  },
  qualityOptionActive: {
    backgroundColor: colors.infoLight,
    borderWidth: 2,
    borderColor: colors.info,
  },
  qualityLabel: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.primary.navy,
    flex: 1,
  },
  qualityDescription: {
    fontSize: 12,
    color: colors.neutral[600],
    flex: 2,
  },
  checkmark: {
    fontSize: 20,
    color: colors.info,
    fontWeight: 'bold',
  },
  cancelButton: {
    marginTop: 8,
    paddingVertical: 14,
    borderRadius: 12,
    backgroundColor: colors.neutral[200],
    alignItems: 'center',
  },
  cancelButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.primary.navy,
  },
});
