// Type declarations for @daily-co/react-native-daily-js
// Stub for when native module is not installed locally

declare module '@daily-co/react-native-daily-js' {
  export interface DailyTrack {
    persistentTrack?: unknown;
    state: 'playable' | 'loading' | 'interrupted' | 'blocked' | 'off' | 'sendable';
  }

  export interface DailyParticipant {
    user_id: string;
    user_name: string;
    local: boolean;
    video: boolean;
    audio: boolean;
    screen: boolean;
    session_id: string;
    tracks: {
      video?: DailyTrack;
      audio?: DailyTrack;
      screenVideo?: DailyTrack;
      screenAudio?: DailyTrack;
      [key: string]: DailyTrack | undefined;
    };
  }

  export interface DailyEventObjectActiveSpeakerChange {
    activeSpeaker: { peerId: string };
  }

  export interface DailyEventObjectError {
    errorMsg: string;
    error?: { type: string; msg: string };
  }

  export interface DailyEventObjectCameraError {
    errorMsg?: { errorMsg: string };
    error?: unknown;
  }

  export interface DailyEventObjectRecordingError {
    errorMsg?: string;
    error?: unknown;
  }

  export interface DailyEventObjectAppMessage {
    data: unknown;
    fromId: string;
  }

  export interface DailyNetworkStats {
    threshold: 'good' | 'low' | 'very-low';
    stats: Record<string, unknown>;
  }

  export interface DailyCall {
    join(options: { url: string; token: string; userName: string }): Promise<void>;
    leave(): Promise<void>;
    destroy(): Promise<void>;
    participants(): Record<string, DailyParticipant> & { local: DailyParticipant };
    setLocalVideo(enabled: boolean): void;
    setLocalAudio(enabled: boolean): void;
    updateReceiveSettings(settings: Record<string, unknown>): void;
    getNetworkStats(): Promise<DailyNetworkStats>;
    on(event: 'joined-meeting', callback: () => void): void;
    on(event: 'left-meeting', callback: () => void): void;
    on(event: 'participant-joined', callback: () => void): void;
    on(event: 'participant-left', callback: () => void): void;
    on(event: 'participant-updated', callback: () => void): void;
    on(event: 'active-speaker-change', callback: (event: DailyEventObjectActiveSpeakerChange) => void): void;
    on(event: 'error', callback: (event: DailyEventObjectError) => void): void;
    on(event: 'camera-error', callback: (event: DailyEventObjectCameraError) => void): void;
    on(event: 'recording-started', callback: () => void): void;
    on(event: 'recording-stopped', callback: () => void): void;
    on(event: 'recording-error', callback: (event: DailyEventObjectRecordingError) => void): void;
    on(event: 'transcription-started', callback: () => void): void;
    on(event: 'transcription-stopped', callback: () => void): void;
    on(event: 'transcription-error', callback: (event: DailyEventObjectAppMessage) => void): void;
    on(event: 'transcription-message', callback: (event: DailyEventObjectAppMessage) => void): void;
    on(event: string, callback: (...args: unknown[]) => void): void;
  }

  const Daily: {
    createCallObject(): DailyCall;
  };

  export default Daily;

  export const DailyMediaView: import('react').ComponentType<{
    videoTrack?: unknown;
    audioTrack?: unknown;
    mirror?: boolean;
    objectFit?: 'cover' | 'contain';
    style?: import('react-native').StyleProp<import('react-native').ViewStyle>;
  }>;
}
