// Teams hook — socket-based team create/join/leave
// Ported from ../globalconnect/src/hooks/use-teams.ts

import { useState, useEffect, useCallback, useRef } from 'react';
import { useSessionSocket } from '@/context/SessionSocketContext';
import { useAuthStore } from '@/store/auth.store';
import type { Team, CreateTeamResponse, JoinLeaveResponse } from '@/types/gamification';

const SOCKET_TIMEOUT = 30000;

let idempotencyCounter = 0;
function generateIdempotencyKey(): string {
  return `idem_${++idempotencyCounter}_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

export function useTeams() {
  const { socket, isConnected, isJoined } = useSessionSocket();
  const user = useAuthStore((s) => s.user);

  const [teams, setTeams] = useState<Team[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const socketRef = useRef(socket);
  socketRef.current = socket;

  // Derive current team
  const currentTeam = teams.find((t) =>
    t.members.some((m) => m.userId === user?.id)
  ) || null;

  const isInTeam = !!currentTeam;
  const teamCount = teams.length;

  // Socket event listeners
  useEffect(() => {
    if (!socket) return;

    const handleTeamCreated = (team: Team) => {
      setTeams((prev) => {
        if (prev.some((t) => t.id === team.id)) return prev;
        return [...prev, team];
      });
    };

    const handleRosterUpdated = (updatedTeam: Team) => {
      setTeams((prev) =>
        prev.map((t) => (t.id === updatedTeam.id ? updatedTeam : t))
      );
    };

    socket.on('team.created', handleTeamCreated);
    socket.on('team.roster.updated', handleRosterUpdated);

    return () => {
      socket.off('team.created', handleTeamCreated);
      socket.off('team.roster.updated', handleRosterUpdated);
    };
  }, [socket]);

  const createTeam = useCallback(
    (name: string): Promise<CreateTeamResponse> => {
      return new Promise((resolve) => {
        if (!socketRef.current || !isJoined) {
          resolve({ success: false, error: 'Not connected' });
          return;
        }

        setIsLoading(true);
        setError(null);

        const idempotencyKey = generateIdempotencyKey();

        const timeoutId = setTimeout(() => {
          socketRef.current?.off('team.create.response', handler);
          setIsLoading(false);
          setError('Request timed out');
          resolve({ success: false, error: 'Request timed out' });
        }, SOCKET_TIMEOUT);

        const handler = (response: CreateTeamResponse) => {
          clearTimeout(timeoutId);
          socketRef.current?.off('team.create.response', handler);
          setIsLoading(false);

          if (!response.success) {
            setError(response.error || 'Failed to create team');
          }
          resolve(response);
        };

        socketRef.current.on('team.create.response', handler);
        socketRef.current.emit('team.create', { name, idempotencyKey });
      });
    },
    [isJoined]
  );

  const joinTeam = useCallback(
    (teamId: string): Promise<JoinLeaveResponse> => {
      return new Promise((resolve) => {
        if (!socketRef.current || !isJoined) {
          resolve({ success: false, error: 'Not connected' });
          return;
        }

        setIsLoading(true);
        setError(null);

        const idempotencyKey = generateIdempotencyKey();

        const timeoutId = setTimeout(() => {
          socketRef.current?.off('team.join.response', handler);
          setIsLoading(false);
          setError('Request timed out');
          resolve({ success: false, error: 'Request timed out' });
        }, SOCKET_TIMEOUT);

        const handler = (response: JoinLeaveResponse) => {
          clearTimeout(timeoutId);
          socketRef.current?.off('team.join.response', handler);
          setIsLoading(false);

          if (!response.success) {
            setError(response.error || 'Failed to join team');
          }
          resolve(response);
        };

        socketRef.current.on('team.join.response', handler);
        socketRef.current.emit('team.join', { teamId, idempotencyKey });
      });
    },
    [isJoined]
  );

  const leaveTeam = useCallback((): Promise<JoinLeaveResponse> => {
    return new Promise((resolve) => {
      if (!socketRef.current || !isJoined || !currentTeam) {
        resolve({ success: false, error: 'Not in a team' });
        return;
      }

      setIsLoading(true);
      setError(null);

      const idempotencyKey = generateIdempotencyKey();

      const timeoutId = setTimeout(() => {
        socketRef.current?.off('team.leave.response', handler);
        setIsLoading(false);
        setError('Request timed out');
        resolve({ success: false, error: 'Request timed out' });
      }, SOCKET_TIMEOUT);

      const handler = (response: JoinLeaveResponse) => {
        clearTimeout(timeoutId);
        socketRef.current?.off('team.leave.response', handler);
        setIsLoading(false);

        if (!response.success) {
          setError(response.error || 'Failed to leave team');
        }
        resolve(response);
      };

      socketRef.current.on('team.leave.response', handler);
      socketRef.current.emit('team.leave', {
        teamId: currentTeam.id,
        idempotencyKey,
      });
    });
  }, [isJoined, currentTeam]);

  const clearError = useCallback(() => setError(null), []);

  return {
    isConnected,
    isLoading,
    error,
    teams,
    currentTeam,
    currentUserId: user?.id,
    isInTeam,
    teamCount,
    createTeam,
    joinTeam,
    leaveTeam,
    clearError,
  };
}
