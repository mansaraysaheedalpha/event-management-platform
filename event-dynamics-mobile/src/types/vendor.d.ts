// Type declarations for vendor packages not installed locally
// These stubs prevent TS2307 when native dependencies are absent

declare module 'expo-camera' {
  export const Camera: {
    requestCameraPermissionsAsync(): Promise<{ status: 'granted' | 'denied' | 'undetermined' }>;
  };

  export interface BarcodeScanningResult {
    type: string;
    data: string;
    cornerPoints: { x: number; y: number }[];
    bounds: { origin: { x: number; y: number }; size: { width: number; height: number } };
  }

  export function useCameraPermissions(): [
    { status: 'granted' | 'denied' | 'undetermined'; granted: boolean } | null,
    () => Promise<{ status: 'granted' | 'denied' | 'undetermined'; granted: boolean }>,
  ];

  export const CameraView: import('react').ComponentType<{
    style?: import('react-native').StyleProp<import('react-native').ViewStyle>;
    facing?: 'front' | 'back';
    barcodeScannerSettings?: { barcodeTypes: string[] };
    onBarcodeScanned?: (result: BarcodeScanningResult) => void;
    children?: import('react').ReactNode;
  }>;
}

declare module 'expo-av' {
  export const Audio: {
    requestPermissionsAsync(): Promise<{ status: 'granted' | 'denied' | 'undetermined' }>;
  };
}

declare module '@react-native-community/netinfo' {
  export interface NetInfoState {
    type: 'wifi' | 'cellular' | 'none' | 'unknown' | 'bluetooth' | 'ethernet' | 'wimax' | 'vpn' | 'other';
    isConnected: boolean | null;
    isInternetReachable: boolean | null;
  }

  const NetInfo: {
    addEventListener(listener: (state: NetInfoState) => void): () => void;
    fetch(): Promise<NetInfoState>;
  };

  export default NetInfo;
}

declare module 'expo-battery' {
  export function getBatteryLevelAsync(): Promise<number>;
}

declare module 'expo-screen-orientation' {
  export enum OrientationLock {
    DEFAULT = 0,
    ALL = 1,
    PORTRAIT = 2,
    PORTRAIT_UP = 3,
    PORTRAIT_DOWN = 4,
    LANDSCAPE = 5,
    LANDSCAPE_LEFT = 6,
    LANDSCAPE_RIGHT = 7,
  }

  export function lockAsync(orientationLock: OrientationLock): Promise<void>;
  export function unlockAsync(): Promise<void>;
  export function getOrientationAsync(): Promise<number>;
}

declare module '@react-native-async-storage/async-storage' {
  export interface AsyncStorageStatic {
    getItem(key: string): Promise<string | null>;
    setItem(key: string, value: string): Promise<void>;
    removeItem(key: string): Promise<void>;
    clear(): Promise<void>;
  }

  const AsyncStorage: AsyncStorageStatic;
  export default AsyncStorage;
}

declare module '@sentry/react-native' {
  export function init(options: {
    dsn: string;
    tracesSampleRate?: number;
    enableAutoSessionTracking?: boolean;
    attachStacktrace?: boolean;
    environment?: string;
    [key: string]: unknown;
  }): void;
  export function captureException(error: unknown, context?: { extra?: Record<string, unknown> }): void;
  export function addBreadcrumb(breadcrumb: {
    category: string;
    message: string;
    data?: Record<string, unknown>;
    level?: string;
  }): void;
  export function setUser(user: { id: string; email?: string } | null): void;
}

declare module '@shopify/flash-list' {
  import { ComponentType } from 'react';
  import { StyleProp, ViewStyle, ScrollViewProps } from 'react-native';

  export interface FlashListProps<T> extends Omit<ScrollViewProps, 'contentContainerStyle'> {
    data: T[] | null | undefined;
    renderItem: (info: { item: T; index: number }) => React.ReactElement | null;
    estimatedItemSize: number;
    keyExtractor?: (item: T, index: number) => string;
    ItemSeparatorComponent?: ComponentType<unknown> | null;
    ListEmptyComponent?: ComponentType<unknown> | React.ReactElement | null;
    ListHeaderComponent?: ComponentType<unknown> | React.ReactElement | null;
    ListFooterComponent?: ComponentType<unknown> | React.ReactElement | null;
    onEndReached?: () => void;
    onEndReachedThreshold?: number;
    refreshing?: boolean;
    onRefresh?: () => void;
    contentContainerStyle?: { paddingHorizontal?: number; paddingVertical?: number; paddingBottom?: number; paddingTop?: number; padding?: number };
    extraData?: unknown;
    numColumns?: number;
    inverted?: boolean;
    horizontal?: boolean;
    showsVerticalScrollIndicator?: boolean;
    showsHorizontalScrollIndicator?: boolean;
  }

  export class FlashList<T> extends React.Component<FlashListProps<T>> {
    scrollToEnd(params?: { animated?: boolean }): void;
    scrollToIndex(params: { index: number; animated?: boolean; viewOffset?: number; viewPosition?: number }): void;
    scrollToOffset(params: { offset: number; animated?: boolean }): void;
  }
}
