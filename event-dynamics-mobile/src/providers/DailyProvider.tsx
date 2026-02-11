// Daily.co video call provider for React Native
// Ported from ../globalconnect/src/components/features/breakout/video/DailyProvider.tsx

import React, { createContext, useContext, useCallback, useState, useEffect, useRef } from 'react';
import { AppState, AppStateStatus } from 'react-native';
import Daily, { DailyCall, DailyParticipant, DailyEventObjectAppMessage } from '@daily-co/react-native-daily-js';
import { Camera } from 'expo-camera';
import { Audio } from 'expo-av';
import NetInfo from '@react-native-community/netinfo';
import * as Battery from 'expo-battery';

export interface CaptionEntry {
  timestamp: number;
  speakerName: string;
  text: string;
  isFinal: boolean;
}

interface DailyContextValue {
  callObject: DailyCall | null;
  participants: DailyParticipant[];
  localParticipant: DailyParticipant | null;
  activeSpeakerId: string | null;
  isJoined: boolean;
  isJoining: boolean;
  isCameraOn: boolean;
  isMicOn: boolean;
  isScreenSharing: boolean;
  isRecording: boolean;
  isTranscribing: boolean;
  captions: CaptionEntry[];
  cpuLoadState: 'normal' | 'high' | 'critical';
  error: string | null;
  joinCall: (url: string, token: string, userName: string) => Promise<void>;
  leaveCall: () => Promise<void>;
  toggleCamera: () => void;
  toggleMic: () => void;
  setReceiveVideoQuality: (quality: 'low' | 'medium' | 'high') => void;
}

const DailyContext = createContext<DailyContextValue | null>(null);

export function useDailyCall() {
  const context = useContext(DailyContext);
  if (!context) {
    throw new Error('useDailyCall must be used within a DailyProvider');
  }
  return context;
}

interface DailyProviderProps {
  children: React.ReactNode;
}

export function DailyProvider({ children }: DailyProviderProps) {
  const [callObject, setCallObject] = useState<DailyCall | null>(null);
  const [participants, setParticipants] = useState<DailyParticipant[]>([]);
  const [localParticipant, setLocalParticipant] = useState<DailyParticipant | null>(null);
  const [activeSpeakerId, setActiveSpeakerId] = useState<string | null>(null);
  const [isJoined, setIsJoined] = useState(false);
  const [isJoining, setIsJoining] = useState(false);
  const [isCameraOn, setIsCameraOn] = useState(true);
  const [isMicOn, setIsMicOn] = useState(true);
  const [isScreenSharing, setIsScreenSharing] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [captions, setCaptions] = useState<CaptionEntry[]>([]);
  const [cpuLoadState, setCpuLoadState] = useState<'normal' | 'high' | 'critical'>('normal');
  const [error, setError] = useState<string | null>(null);

  const callObjectRef = useRef<DailyCall | null>(null);
  const cpuMonitorRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const wasCameraOnRef = useRef<boolean>(true);

  // Update participants list
  const updateParticipants = useCallback((call: DailyCall) => {
    const allParticipants = call.participants();
    const participantList = Object.values(allParticipants);
    setParticipants(participantList);

    const local = allParticipants.local;
    if (local) {
      setLocalParticipant(local);
      setIsCameraOn(local.video);
      setIsMicOn(local.audio);
      setIsScreenSharing(local.screen || false);
    }
  }, []);

  // Monitor CPU load and adapt quality
  const startCpuMonitoring = useCallback((call: DailyCall) => {
    if (cpuMonitorRef.current) {
      clearInterval(cpuMonitorRef.current);
    }

    cpuMonitorRef.current = setInterval(async () => {
      try {
        const stats = await call.getNetworkStats();

        // Check quality threshold
        if (stats?.threshold === 'very-low') {
          setCpuLoadState('critical');
          call.updateReceiveSettings({
            '*': { video: { layer: 0 } },
          });
        } else if (stats?.threshold === 'low') {
          setCpuLoadState('high');
          call.updateReceiveSettings({
            '*': { video: { layer: 1 } },
          });
        } else {
          setCpuLoadState('normal');
        }
      } catch (err) {
        // Stats not available
      }
    }, 5000);
  }, []);

  // Set receive video quality
  const setReceiveVideoQuality = useCallback(
    (quality: 'low' | 'medium' | 'high') => {
      if (!callObject) return;

      const layerMap = { low: 0, medium: 1, high: 2 };
      callObject.updateReceiveSettings({
        '*': { video: { layer: layerMap[quality] } },
      });
    },
    [callObject]
  );

  // Join the call
  const joinCall = useCallback(
    async (url: string, token: string, userName: string) => {
      setIsJoining(true);
      setError(null);

      try {
        // Request permissions
        void 0; // [DailyProvider] Requesting camera and microphone permissions...');
        const cameraPermission = await Camera.requestCameraPermissionsAsync();
        const audioPermission = await Audio.requestPermissionsAsync();

        if (cameraPermission.status !== 'granted' || audioPermission.status !== 'granted') {
          throw new Error('Camera or microphone permission denied. Please allow access and try again.');
        }

        void 0; // [DailyProvider] Permissions granted');

        // Create call object
        const call = Daily.createCallObject();

        // Set up event handlers
        call.on('joined-meeting', () => {
          void 0; // [DailyProvider] Joined meeting');
          setIsJoined(true);
          setIsJoining(false);
          updateParticipants(call);
          startCpuMonitoring(call);
        });

        call.on('left-meeting', () => {
          void 0; // [DailyProvider] Left meeting');
          setIsJoined(false);
          setParticipants([]);
          setLocalParticipant(null);
          setActiveSpeakerId(null);
          if (cpuMonitorRef.current) {
            clearInterval(cpuMonitorRef.current);
          }
        });

        call.on('participant-joined', () => {
          updateParticipants(call);
        });

        call.on('participant-left', () => {
          updateParticipants(call);
        });

        call.on('participant-updated', () => {
          updateParticipants(call);
        });

        call.on('active-speaker-change', (event) => {
          if (event?.activeSpeaker?.peerId) {
            setActiveSpeakerId(event.activeSpeaker.peerId);
            call.updateReceiveSettings({
              [event.activeSpeaker.peerId]: { video: { layer: 2 } },
            });
          }
        });

        call.on('error', (event) => {
          console.error('[DailyProvider] Daily error:', event);
          setError(event?.errorMsg || 'An error occurred');
          setIsJoining(false);
        });

        call.on('camera-error', (event) => {
          console.error('[DailyProvider] Camera error:', event);
        });

        // Recording events
        call.on('recording-started', () => {
          setIsRecording(true);
        });

        call.on('recording-stopped', () => {
          setIsRecording(false);
        });

        call.on('recording-error', (event) => {
          console.error('[DailyProvider] Recording error:', event);
          setIsRecording(false);
        });

        // Transcription events
        call.on('transcription-started', () => {
          setIsTranscribing(true);
        });

        call.on('transcription-stopped', () => {
          setIsTranscribing(false);
        });

        call.on('transcription-error', (event: DailyEventObjectAppMessage) => {
          console.error('[DailyProvider] Transcription error:', event);
          setIsTranscribing(false);
        });

        call.on('transcription-message', (event: DailyEventObjectAppMessage) => {
          const data = event.data as { text?: string; participantId?: string; is_final?: boolean };
          if (!data?.text) return;

          const entry: CaptionEntry = {
            timestamp: Date.now(),
            speakerName: data.participantId
              ? (call.participants()?.[data.participantId]?.user_name || 'Unknown')
              : 'Unknown',
            text: data.text,
            isFinal: data.is_final ?? true,
          };

          setCaptions((prev) => {
            const finals = [...prev.filter((c) => c.isFinal), ...(entry.isFinal ? [entry] : [])].slice(-3);
            return entry.isFinal ? finals : [...finals, entry];
          });
        });

        setCallObject(call);
        callObjectRef.current = call;

        // Join the call
        await call.join({
          url,
          token,
          userName,
        });

        void 0; // [DailyProvider] Call joined successfully');
        updateParticipants(call);

        // Set initial receive settings
        call.updateReceiveSettings({
          '*': { video: { layer: 1 } },
        });
      } catch (err) {
        console.error('[DailyProvider] Failed to join call:', err);
        setError(err instanceof Error ? err.message : 'Failed to join call');
        setIsJoining(false);
      }
    },
    [updateParticipants, startCpuMonitoring]
  );

  // Leave the call
  const leaveCall = useCallback(async () => {
    if (callObject) {
      try {
        await callObject.leave();
        await callObject.destroy();
      } catch (err) {
        console.error('[DailyProvider] Error leaving call:', err);
      }
      setCallObject(null);
      callObjectRef.current = null;
      setIsJoined(false);
      setParticipants([]);
      setLocalParticipant(null);
    }
  }, [callObject]);

  // Toggle camera
  const toggleCamera = useCallback(() => {
    if (callObject) {
      const newState = !isCameraOn;
      callObject.setLocalVideo(newState);
      setIsCameraOn(newState);
      wasCameraOnRef.current = newState;
    }
  }, [callObject, isCameraOn]);

  // Toggle microphone
  const toggleMic = useCallback(() => {
    if (callObject) {
      const newState = !isMicOn;
      void 0; // [DailyProvider] Toggling mic:', { from: isMicOn, to: newState });
      callObject.setLocalAudio(newState);
      setIsMicOn(newState);
    }
  }, [callObject, isMicOn]);

  // Handle app state changes (background/foreground)
  useEffect(() => {
    const subscription = AppState.addEventListener('change', (nextAppState: AppStateStatus) => {
      if (!callObject) return;

      if (nextAppState === 'background') {
        void 0; // [DailyProvider] App backgrounded - pausing video');
        if (isCameraOn) {
          callObject.setLocalVideo(false);
        }
      } else if (nextAppState === 'active') {
        void 0; // [DailyProvider] App foregrounded - resuming video');
        if (wasCameraOnRef.current) {
          callObject.setLocalVideo(true);
        }
      }
    });

    return () => subscription.remove();
  }, [callObject, isCameraOn]);

  // Handle network changes
  useEffect(() => {
    const unsubscribe = NetInfo.addEventListener((state) => {
      if (!callObject) return;

      if (state.type === 'wifi') {
        void 0; // [DailyProvider] WiFi detected - setting high quality');
        setReceiveVideoQuality('high');
      } else if (state.type === 'cellular') {
        void 0; // [DailyProvider] Cellular detected - setting medium quality');
        setReceiveVideoQuality('medium');
      } else {
        void 0; // [DailyProvider] Unknown network - setting low quality');
        setReceiveVideoQuality('low');
      }
    });

    return () => unsubscribe();
  }, [callObject, setReceiveVideoQuality]);

  // Monitor battery level
  useEffect(() => {
    if (!callObject) return;

    const checkBattery = async () => {
      try {
        const batteryLevel = await Battery.getBatteryLevelAsync();
        if (batteryLevel < 0.2) {
          void 0; // [DailyProvider] Low battery - reducing quality');
          setReceiveVideoQuality('low');
        }
      } catch (err) {
        // Battery API not available
      }
    };

    checkBattery();
    const interval = setInterval(checkBattery, 60000); // Check every minute

    return () => clearInterval(interval);
  }, [callObject, setReceiveVideoQuality]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      const call = callObjectRef.current;
      if (call) {
        call.leave().catch(console.error);
        call.destroy().catch(console.error);
        callObjectRef.current = null;
      }
      if (cpuMonitorRef.current) {
        clearInterval(cpuMonitorRef.current);
      }
    };
  }, []);

  const value: DailyContextValue = {
    callObject,
    participants,
    localParticipant,
    activeSpeakerId,
    isJoined,
    isJoining,
    isCameraOn,
    isMicOn,
    isScreenSharing,
    isRecording,
    isTranscribing,
    captions,
    cpuLoadState,
    error,
    joinCall,
    leaveCall,
    toggleCamera,
    toggleMic,
    setReceiveVideoQuality,
  };

  return <DailyContext.Provider value={value}>{children}</DailyContext.Provider>;
}
