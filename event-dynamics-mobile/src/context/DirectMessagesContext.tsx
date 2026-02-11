// Shared context for Direct Messages — ensures a single socket connection
// is shared across all screens that need DM functionality.
// Pattern follows SessionSocketContext.tsx

import React, { createContext, useContext, ReactNode } from 'react';
import { useDirectMessages } from '@/hooks/useDirectMessages';

type DirectMessagesContextValue = ReturnType<typeof useDirectMessages>;

const DirectMessagesContext = createContext<DirectMessagesContextValue | null>(null);

interface DirectMessagesProviderProps {
  children: ReactNode;
  eventId?: string;
  autoConnect?: boolean;
}

export const DirectMessagesProvider: React.FC<DirectMessagesProviderProps> = ({
  children,
  eventId,
  autoConnect = true,
}) => {
  const dm = useDirectMessages({ eventId, autoConnect });

  return (
    <DirectMessagesContext.Provider value={dm}>
      {children}
    </DirectMessagesContext.Provider>
  );
};

export function useSharedDirectMessages(): DirectMessagesContextValue {
  const context = useContext(DirectMessagesContext);
  if (!context) {
    throw new Error('useSharedDirectMessages must be used within a DirectMessagesProvider');
  }
  return context;
}
