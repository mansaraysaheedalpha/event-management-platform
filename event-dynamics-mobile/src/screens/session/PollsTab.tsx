import React, { useCallback } from 'react';
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
} from 'react-native';
import { Card, Badge } from '@/components/ui';
import { colors, typography } from '@/theme';
import { useSessionPolls, Poll, PollOption } from '@/hooks/useSessionPolls';

interface PollOptionRowProps {
  option: PollOption;
  totalVotes: number;
  isSelected: boolean;
  isVoted: boolean;
  onVote: () => void;
  isQuiz?: boolean;
  correctOptionId?: string;
}

const PollOptionRow = React.memo(function PollOptionRow({
  option,
  totalVotes,
  isSelected,
  isVoted,
  onVote,
  isQuiz,
  correctOptionId,
}: PollOptionRowProps) {
  const voteCount = option.voteCount || 0;
  const percentage = totalVotes > 0 ? Math.round((voteCount / totalVotes) * 100) : 0;
  const isCorrect = isQuiz && option.id === correctOptionId;

  return (
    <TouchableOpacity
      style={[
        styles.optionRow,
        isSelected && styles.optionRowSelected,
        isVoted && isCorrect && styles.optionRowCorrect,
      ]}
      onPress={onVote}
      disabled={isVoted}
      activeOpacity={0.7}
      accessibilityRole="button"
      accessibilityLabel={`Vote for ${option.text}`}
      accessibilityState={{ selected: isSelected, disabled: isVoted }}
    >
      {/* Percentage bar background */}
      {isVoted && (
        <View
          style={[
            styles.percentageBar,
            {
              width: `${percentage}%`,
              backgroundColor: isSelected
                ? colors.primary.goldLight
                : colors.neutral[100],
            },
          ]}
        />
      )}

      <View style={styles.optionContent}>
        <Text style={styles.optionText} numberOfLines={2}>
          {option.text}
        </Text>
        {isVoted && (
          <View style={styles.optionMeta}>
            <Text style={styles.optionPercent}>{percentage}%</Text>
            <Text style={styles.optionVotes}>{voteCount} votes</Text>
          </View>
        )}
      </View>

      {isSelected && <Text style={styles.checkmark}>✓</Text>}
      {isVoted && isCorrect && <Text style={styles.correctMark}>✓</Text>}
    </TouchableOpacity>
  );
});

interface PollCardProps {
  poll: Poll;
  userVote: string | undefined;
  onVote: (pollId: string, optionId: string) => void;
  isVoting: boolean;
}

const PollCard = React.memo(function PollCard({ poll, userVote, onVote, isVoting }: PollCardProps) {
  const totalVotes = poll.totalVotes || poll.options.reduce((sum, o) => sum + (o.voteCount || 0), 0);
  const hasVoted = !!userVote;

  return (
    <Card style={styles.pollCard}>
      <View style={styles.pollHeader}>
        <View style={styles.pollHeaderLeft}>
          {poll.isActive ? (
            <Badge variant="success" label="Active" />
          ) : (
            <Badge variant="default" label="Closed" />
          )}
          {poll.isQuiz && <Badge variant="info" label="Quiz" />}
        </View>
        <Text style={styles.pollVoteCount}>
          {totalVotes} {totalVotes === 1 ? 'vote' : 'votes'}
        </Text>
      </View>

      <Text style={styles.pollQuestion}>{poll.question}</Text>

      <View style={styles.optionsList}>
        {poll.options.map((option) => (
          <PollOptionRow
            key={option.id}
            option={option}
            totalVotes={totalVotes}
            isSelected={userVote === option.id}
            isVoted={hasVoted || !poll.isActive}
            onVote={() => onVote(poll.id, option.id)}
            isQuiz={poll.isQuiz}
            correctOptionId={poll.correctOptionId}
          />
        ))}
      </View>

      {isVoting && (
        <Text style={styles.votingText}>Submitting vote...</Text>
      )}
    </Card>
  );
});

export function PollsTab() {
  const {
    activePolls,
    closedPolls,
    isJoined,
    pollsOpen,
    isVoting,
    error,
    submitVote,
    getUserVote,
    clearError,
  } = useSessionPolls();

  const allPolls = [...activePolls, ...closedPolls];

  const handleVote = useCallback(
    (pollId: string, optionId: string) => {
      submitVote(pollId, optionId);
    },
    [submitVote],
  );

  const renderItem = useCallback(
    ({ item }: { item: Poll }) => (
      <PollCard
        poll={item}
        userVote={getUserVote(item.id)}
        onVote={handleVote}
        isVoting={isVoting === item.id}
      />
    ),
    [getUserVote, handleVote, isVoting],
  );

  const keyExtractor = useCallback((item: Poll) => item.id, []);

  if (!isJoined) {
    return (
      <View style={styles.center}>
        <Text style={styles.statusText}>Connecting to polls...</Text>
      </View>
    );
  }

  if (!pollsOpen) {
    return (
      <View style={styles.center}>
        <Text style={styles.disabledIcon}>📊</Text>
        <Text style={styles.statusText}>Polls are currently closed</Text>
        <Text style={styles.subText}>The organizer has disabled polls for this session</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {error && (
        <TouchableOpacity style={styles.errorBanner} onPress={clearError}>
          <Text style={styles.errorText}>{error}</Text>
        </TouchableOpacity>
      )}

      <FlatList
        data={allPolls}
        renderItem={renderItem}
        keyExtractor={keyExtractor}
        contentContainerStyle={styles.listContent}
        showsVerticalScrollIndicator={false}
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Text style={styles.emptyText}>No polls yet</Text>
            <Text style={styles.emptySubText}>Polls will appear here when the speaker creates one</Text>
          </View>
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24 },
  statusText: { ...typography.body, color: colors.neutral[500], marginTop: 8 },
  subText: { ...typography.bodySmall, color: colors.neutral[400], marginTop: 4, textAlign: 'center' },
  disabledIcon: { fontSize: 40 },
  errorBanner: {
    backgroundColor: colors.destructiveLight,
    padding: 10,
    alignItems: 'center',
  },
  errorText: { ...typography.bodySmall, color: colors.destructive },
  listContent: { padding: 12, paddingBottom: 20 },
  emptyContainer: { alignItems: 'center', paddingVertical: 60 },
  emptyText: { ...typography.body, color: colors.neutral[500] },
  emptySubText: { ...typography.bodySmall, color: colors.neutral[400], marginTop: 4, textAlign: 'center' },
  pollCard: { marginBottom: 16, padding: 16 },
  pollHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  pollHeaderLeft: { flexDirection: 'row', gap: 6 },
  pollVoteCount: { ...typography.caption, color: colors.neutral[500] },
  pollQuestion: { ...typography.h4, color: colors.foreground, marginBottom: 12 },
  optionsList: { gap: 8 },
  optionRow: {
    position: 'relative',
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 12,
    flexDirection: 'row',
    alignItems: 'center',
  },
  optionRowSelected: {
    borderColor: colors.primary.gold,
    borderWidth: 2,
  },
  optionRowCorrect: {
    borderColor: colors.success,
    borderWidth: 2,
  },
  percentageBar: {
    position: 'absolute',
    left: 0,
    top: 0,
    bottom: 0,
    borderRadius: 10,
  },
  optionContent: {
    flex: 1,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    zIndex: 1,
  },
  optionText: { ...typography.body, color: colors.foreground, flex: 1 },
  optionMeta: { alignItems: 'flex-end', marginLeft: 8 },
  optionPercent: { ...typography.label, fontWeight: '700', color: colors.foreground },
  optionVotes: { ...typography.caption, color: colors.neutral[500] },
  checkmark: {
    fontSize: 16,
    fontWeight: '700',
    color: colors.primary.gold,
    marginLeft: 8,
    zIndex: 1,
  },
  correctMark: {
    fontSize: 16,
    fontWeight: '700',
    color: colors.success,
    marginLeft: 8,
    zIndex: 1,
  },
  votingText: { ...typography.caption, color: colors.neutral[400], marginTop: 8, textAlign: 'center' },
});
