import React from 'react';
import { StatusBar } from 'expo-status-bar';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { StripeProvider } from '@stripe/stripe-react-native';
import { ApolloProvider } from '@/lib/apollo-provider';
import { RootNavigator } from '@/navigation/RootNavigator';
import { NotificationProvider } from '@/context/NotificationContext';
import { ToastProvider } from '@/components/notifications/ToastProvider';
import { ErrorBoundary } from '@/components/ui/ErrorBoundary';
import { OfflineBanner } from '@/components/ui/OfflineBanner';
import { NetworkProvider } from '@/context/NetworkContext';
import { initSentry } from '@/lib/sentry';
import { env } from '@/lib/env';

initSentry();

export default function App() {
  return (
    <ErrorBoundary>
      <GestureHandlerRootView style={{ flex: 1 }}>
        <SafeAreaProvider>
          <NetworkProvider>
            <StripeProvider
              publishableKey={env.STRIPE_PUBLISHABLE_KEY}
              merchantIdentifier="merchant.com.eventdynamics"
            >
              <ApolloProvider>
                <NotificationProvider>
                  <ToastProvider>
                    <RootNavigator />
                    <OfflineBanner />
                    <StatusBar style="auto" />
                  </ToastProvider>
                </NotificationProvider>
              </ApolloProvider>
            </StripeProvider>
          </NetworkProvider>
        </SafeAreaProvider>
      </GestureHandlerRootView>
    </ErrorBoundary>
  );
}
