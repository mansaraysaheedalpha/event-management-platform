import { useRef, useCallback } from 'react';
import { NavigationState } from '@react-navigation/native';
import { analytics } from '@/lib/analytics';

function getActiveRouteName(state: NavigationState | undefined): string | undefined {
  if (!state) return undefined;

  const route = state.routes[state.index];
  if (route.state) {
    return getActiveRouteName(route.state as NavigationState);
  }
  return route.name;
}

export function useScreenTracking() {
  const routeNameRef = useRef<string>(undefined);

  const onReady = useCallback(() => {
    // Will be called when NavigationContainer is ready
  }, []);

  const onStateChange = useCallback((state: NavigationState | undefined) => {
    const currentRouteName = getActiveRouteName(state);

    if (currentRouteName && currentRouteName !== routeNameRef.current) {
      analytics.trackScreen(currentRouteName);
      routeNameRef.current = currentRouteName;
    }
  }, []);

  return { onReady, onStateChange };
}
