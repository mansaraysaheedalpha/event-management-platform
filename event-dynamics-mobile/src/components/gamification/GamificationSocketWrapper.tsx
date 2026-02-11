// Wrapper that provides SessionSocketProvider for standalone gamification screens
// These screens receive sessionId/eventId from route params and need their own socket

import React, { ReactNode } from 'react';
import { SessionSocketProvider } from '@/context/SessionSocketContext';

interface GamificationSocketWrapperProps {
  children: ReactNode;
  sessionId: string;
  eventId: string;
}

export function GamificationSocketWrapper({
  children,
  sessionId,
  eventId,
}: GamificationSocketWrapperProps) {
  if (!sessionId || !eventId) {
    return <>{children}</>;
  }

  return (
    <SessionSocketProvider sessionId={sessionId} eventId={eventId}>
      {children}
    </SessionSocketProvider>
  );
}
