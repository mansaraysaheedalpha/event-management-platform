// Team management screen — create, join, leave teams

import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  TextInput,
  Alert,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { RouteProp } from '@react-navigation/native';
import type { HomeStackParamList } from '@/navigation/types';
import { useTeams } from '@/hooks/useTeams';
import { Avatar } from '@/components/ui/Avatar';
import { GamificationSocketWrapper } from '@/components/gamification/GamificationSocketWrapper';
import { LoadingSpinner, Button } from '@/components/ui';
import { colors, typography, spacing, borderRadius } from '@/theme';
import type { Team, TeamMember } from '@/types/gamification';

type TeamsRoute = RouteProp<HomeStackParamList, 'Teams'>;

function TeamContent() {
  const navigation = useNavigation();
  const teams = useTeams();
  const [isCreating, setIsCreating] = useState(false);
  const [teamName, setTeamName] = useState('');

  const handleCreate = useCallback(async () => {
    if (!teamName.trim()) return;
    const result = await teams.createTeam(teamName.trim());
    if (result.success) {
      setIsCreating(false);
      setTeamName('');
    } else {
      Alert.alert('Error', result.error || 'Failed to create team');
    }
  }, [teamName, teams.createTeam]);

  const handleJoin = useCallback(
    async (teamId: string) => {
      const result = await teams.joinTeam(teamId);
      if (!result.success) {
        Alert.alert('Error', result.error || 'Failed to join team');
      }
    },
    [teams.joinTeam]
  );

  const handleLeave = useCallback(() => {
    Alert.alert('Leave Team', 'Are you sure you want to leave this team?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Leave',
        style: 'destructive',
        onPress: async () => {
          const result = await teams.leaveTeam();
          if (!result.success) {
            Alert.alert('Error', result.error || 'Failed to leave team');
          }
        },
      },
    ]);
  }, [teams.leaveTeam]);

  const renderMember = useCallback(
    ({ item }: { item: TeamMember }) => {
      const name = item.user
        ? `${item.user.firstName} ${item.user.lastName}`
        : 'Unknown';
      const isCreator = teams.currentTeam?.creatorId === item.userId;
      const isMe = item.userId === teams.currentUserId;

      return (
        <View style={styles.memberRow}>
          <Avatar name={name} uri={item.user?.imageUrl} size={36} />
          <View style={styles.memberInfo}>
            <Text style={styles.memberName}>
              {name}
              {isMe ? ' (You)' : ''}
            </Text>
            {isCreator && <Text style={styles.creatorBadge}>👑 Creator</Text>}
          </View>
        </View>
      );
    },
    [teams.currentTeam?.creatorId, teams.currentUserId]
  );

  const renderAvailableTeam = useCallback(
    ({ item }: { item: Team }) => {
      const isMine = item.id === teams.currentTeam?.id;
      return (
        <View style={[styles.teamCard, isMine && styles.myTeamCard]}>
          <View style={styles.teamCardLeft}>
            <Text style={styles.teamEmoji}>👥</Text>
            <View>
              <Text style={styles.teamName}>{item.name}</Text>
              <Text style={styles.teamMembers}>
                {item.members.length} {item.members.length === 1 ? 'member' : 'members'}
              </Text>
            </View>
          </View>
          {!teams.isInTeam && (
            <TouchableOpacity
              style={styles.joinBtn}
              onPress={() => handleJoin(item.id)}
              disabled={teams.isLoading}
            >
              <Text style={styles.joinBtnText}>Join</Text>
            </TouchableOpacity>
          )}
          {isMine && <Text style={styles.yourTeamBadge}>Your Team</Text>}
        </View>
      );
    },
    [teams.currentTeam?.id, teams.isInTeam, teams.isLoading, handleJoin]
  );

  const keyExtractor = useCallback((item: Team) => item.id, []);
  const memberKeyExtractor = useCallback((item: TeamMember) => item.userId, []);

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        {/* Header */}
        <View style={styles.header}>
          <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
            <Text style={styles.backText}>←</Text>
          </TouchableOpacity>
          <Text style={styles.title}>Teams</Text>
          <View style={styles.backBtn} />
        </View>

        {/* My Team Section */}
        {teams.currentTeam && (
          <View style={styles.section}>
            <View style={styles.sectionHeader}>
              <Text style={styles.sectionTitle}>Your Team</Text>
              <TouchableOpacity onPress={handleLeave}>
                <Text style={styles.leaveText}>Leave</Text>
              </TouchableOpacity>
            </View>

            <View style={styles.myTeamSection}>
              <Text style={styles.myTeamName}>{teams.currentTeam.name}</Text>
              <FlatList
                data={teams.currentTeam.members}
                renderItem={renderMember}
                keyExtractor={memberKeyExtractor}
                scrollEnabled={false}
                ItemSeparatorComponent={() => <View style={styles.separator} />}
              />
            </View>
          </View>
        )}

        {/* Create Team */}
        {!teams.isInTeam && (
          <View style={styles.section}>
            {isCreating ? (
              <View style={styles.createForm}>
                <TextInput
                  style={styles.input}
                  placeholder="Team name..."
                  placeholderTextColor={colors.neutral[400]}
                  value={teamName}
                  onChangeText={setTeamName}
                  maxLength={100}
                  autoFocus
                />
                <View style={styles.createActions}>
                  <TouchableOpacity
                    onPress={() => {
                      setIsCreating(false);
                      setTeamName('');
                    }}
                  >
                    <Text style={styles.cancelText}>Cancel</Text>
                  </TouchableOpacity>
                  <Button
                    title="Create"
                    onPress={handleCreate}
                    disabled={!teamName.trim() || teams.isLoading}
                    loading={teams.isLoading}
                    size="sm"
                  />
                </View>
              </View>
            ) : (
              <TouchableOpacity
                style={styles.createButton}
                onPress={() => setIsCreating(true)}
              >
                <Text style={styles.createIcon}>+</Text>
                <Text style={styles.createText}>Create a Team</Text>
              </TouchableOpacity>
            )}
          </View>
        )}

        {/* Error */}
        {teams.error && (
          <View style={styles.errorBanner}>
            <Text style={styles.errorText}>{teams.error}</Text>
            <TouchableOpacity onPress={teams.clearError}>
              <Text style={styles.dismissText}>Dismiss</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* Available Teams */}
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>
            Available Teams ({teams.teamCount})
          </Text>
        </View>

        <FlatList
          data={teams.teams}
          renderItem={renderAvailableTeam}
          keyExtractor={keyExtractor}
          contentContainerStyle={styles.list}
          ListEmptyComponent={
            <View style={styles.emptyContainer}>
              <Text style={styles.emptyIcon}>👥</Text>
              <Text style={styles.emptyText}>No teams yet</Text>
              <Text style={styles.emptySubtext}>
                Create the first team!
              </Text>
            </View>
          }
        />
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

export function TeamScreen() {
  const route = useRoute<TeamsRoute>();
  const { eventId, sessionId } = route.params;

  return (
    <GamificationSocketWrapper sessionId={sessionId} eventId={eventId}>
      <TeamContent />
    </GamificationSocketWrapper>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  flex: {
    flex: 1,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.base,
    paddingVertical: spacing.md,
  },
  backBtn: {
    width: 40,
    height: 40,
    justifyContent: 'center',
    alignItems: 'center',
  },
  backText: {
    fontSize: 24,
    color: colors.foreground,
  },
  title: {
    ...typography.h3,
    color: colors.foreground,
  },
  section: {
    marginHorizontal: spacing.base,
    marginBottom: spacing.base,
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: spacing.base,
    marginBottom: spacing.sm,
  },
  sectionTitle: {
    ...typography.h4,
    color: colors.foreground,
  },
  leaveText: {
    ...typography.bodySmall,
    color: colors.destructive,
    fontWeight: '600',
  },
  myTeamSection: {
    backgroundColor: colors.primary.navy + '08',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.primary.navy + '20',
    padding: spacing.base,
  },
  myTeamName: {
    ...typography.h4,
    color: colors.foreground,
    marginBottom: spacing.md,
  },
  memberRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingVertical: spacing.xs,
  },
  memberInfo: {
    flex: 1,
  },
  memberName: {
    ...typography.body,
    color: colors.foreground,
  },
  creatorBadge: {
    ...typography.caption,
    color: colors.primary.goldDark,
  },
  separator: {
    height: 1,
    backgroundColor: colors.border,
    marginVertical: spacing.xs,
  },
  createButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: colors.primary.gold,
    borderStyle: 'dashed',
    borderRadius: 12,
    paddingVertical: spacing.base,
    gap: spacing.sm,
  },
  createIcon: {
    fontSize: 20,
    color: colors.primary.gold,
    fontWeight: '700',
  },
  createText: {
    ...typography.button,
    color: colors.primary.gold,
  },
  createForm: {
    backgroundColor: colors.neutral[50],
    borderRadius: 12,
    padding: spacing.base,
    borderWidth: 1,
    borderColor: colors.border,
  },
  input: {
    ...typography.body,
    color: colors.foreground,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    backgroundColor: colors.card,
    marginBottom: spacing.md,
  },
  createActions: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    alignItems: 'center',
    gap: spacing.base,
  },
  cancelText: {
    ...typography.body,
    color: colors.neutral[500],
  },
  errorBanner: {
    flexDirection: 'row',
    backgroundColor: colors.destructiveLight,
    marginHorizontal: spacing.base,
    padding: spacing.md,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: spacing.md,
  },
  errorText: {
    ...typography.bodySmall,
    color: colors.destructive,
    flex: 1,
  },
  dismissText: {
    ...typography.bodySmall,
    color: colors.destructive,
    fontWeight: '600',
    marginLeft: spacing.sm,
  },
  list: {
    paddingHorizontal: spacing.base,
    paddingBottom: spacing['2xl'],
  },
  teamCard: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: colors.card,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.base,
    marginBottom: spacing.sm,
  },
  myTeamCard: {
    borderColor: colors.primary.gold + '40',
    backgroundColor: colors.primary.gold + '08',
  },
  teamCardLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    flex: 1,
  },
  teamEmoji: {
    fontSize: 24,
  },
  teamName: {
    ...typography.body,
    fontWeight: '600',
    color: colors.foreground,
  },
  teamMembers: {
    ...typography.caption,
    color: colors.neutral[500],
  },
  joinBtn: {
    backgroundColor: colors.primary.gold,
    paddingHorizontal: spacing.base,
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.md,
  },
  joinBtnText: {
    ...typography.label,
    color: colors.primary.navy,
    fontWeight: '700',
  },
  yourTeamBadge: {
    ...typography.caption,
    color: colors.primary.goldDark,
    fontWeight: '600',
  },
  emptyContainer: {
    alignItems: 'center',
    paddingTop: spacing['4xl'],
    gap: spacing.sm,
  },
  emptyIcon: {
    fontSize: 48,
  },
  emptyText: {
    ...typography.h4,
    color: colors.foreground,
  },
  emptySubtext: {
    ...typography.bodySmall,
    color: colors.neutral[500],
  },
});
