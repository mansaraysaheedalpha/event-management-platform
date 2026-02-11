import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  TextInput,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  Switch,
} from 'react-native';
import { Card, Badge } from '@/components/ui';
import { colors, typography } from '@/theme';
import {
  useSessionQA,
  Question,
  QASortMode,
  QAFilterMode,
} from '@/hooks/useSessionQA';

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

interface QuestionItemProps {
  question: Question;
  currentUserId?: string;
  onUpvote: (id: string) => void;
}

const QuestionItem = React.memo(function QuestionItem({ question, currentUserId, onUpvote }: QuestionItemProps) {
  const authorName = question.isAnonymous
    ? 'Anonymous'
    : `${question.author.firstName} ${question.author.lastName}`.trim();
  const isOwn = question.authorId === currentUserId;
  const canUpvote = !isOwn;

  return (
    <Card style={styles.questionCard}>
      <View style={styles.questionHeader}>
        <Text style={styles.questionAuthor} numberOfLines={1}>
          {authorName}
        </Text>
        <Text style={styles.questionTime}>{timeAgo(question.createdAt)}</Text>
      </View>

      <Text style={styles.questionText}>{question.text}</Text>

      {question.answer && (
        <View style={styles.answerBox}>
          <Text style={styles.answerLabel}>Answer</Text>
          <Text style={styles.answerText}>{question.answer.text}</Text>
          <Text style={styles.answerAuthor}>
            — {question.answer.author.firstName} {question.answer.author.lastName}
          </Text>
        </View>
      )}

      <View style={styles.questionFooter}>
        <TouchableOpacity
          style={[
            styles.upvoteBtn,
            question.hasUpvoted && styles.upvoteBtnActive,
            !canUpvote && styles.upvoteBtnDisabled,
          ]}
          onPress={() => onUpvote(question.id)}
          disabled={!canUpvote}
          activeOpacity={0.6}
          accessibilityRole="button"
          accessibilityLabel={`Upvote question, ${question._count?.upvotes || 0} votes`}
          accessibilityState={{ selected: question.hasUpvoted }}
        >
          <Text style={[styles.upvoteIcon, question.hasUpvoted && styles.upvoteIconActive]}>
            ▲
          </Text>
          <Text style={[styles.upvoteCount, question.hasUpvoted && styles.upvoteCountActive]}>
            {question._count?.upvotes || 0}
          </Text>
        </TouchableOpacity>

        <View style={styles.tagRow}>
          {question.isAnswered && <Badge variant="success" label="Answered" />}
          {question.status === 'pending' && <Badge variant="warning" label="Pending" />}
        </View>
      </View>
    </Card>
  );
});

const SORT_OPTIONS: { key: QASortMode; label: string }[] = [
  { key: 'upvotes', label: 'Top' },
  { key: 'recent', label: 'Recent' },
];

const FILTER_OPTIONS: { key: QAFilterMode; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'unanswered', label: 'Unanswered' },
  { key: 'answered', label: 'Answered' },
];

export function QATab() {
  const {
    questions,
    isJoined,
    qaOpen,
    isSending,
    error,
    currentUserId,
    sortMode,
    setSortMode,
    filterMode,
    setFilterMode,
    askQuestion,
    upvoteQuestion,
    clearError,
  } = useSessionQA();

  const [text, setText] = useState('');
  const [isAnonymous, setIsAnonymous] = useState(false);

  const handleAsk = useCallback(async () => {
    if (!text.trim()) return;
    const q = text;
    setText('');
    await askQuestion(q, isAnonymous);
  }, [text, isAnonymous, askQuestion]);

  const renderItem = useCallback(
    ({ item }: { item: Question }) => (
      <QuestionItem
        question={item}
        currentUserId={currentUserId}
        onUpvote={upvoteQuestion}
      />
    ),
    [currentUserId, upvoteQuestion],
  );

  const keyExtractor = useCallback((item: Question) => item.id, []);

  if (!isJoined) {
    return (
      <View style={styles.center}>
        <Text style={styles.statusText}>Connecting to Q&A...</Text>
      </View>
    );
  }

  if (!qaOpen) {
    return (
      <View style={styles.center}>
        <Text style={styles.disabledIcon}>❓</Text>
        <Text style={styles.statusText}>Q&A is currently closed</Text>
        <Text style={styles.subText}>The organizer has disabled Q&A for this session</Text>
      </View>
    );
  }

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      keyboardVerticalOffset={140}
    >
      {error && (
        <TouchableOpacity style={styles.errorBanner} onPress={clearError}>
          <Text style={styles.errorText}>{error}</Text>
        </TouchableOpacity>
      )}

      {/* Sort & Filter Controls */}
      <View style={styles.controls}>
        <View style={styles.pillRow}>
          {SORT_OPTIONS.map((opt) => (
            <TouchableOpacity
              key={opt.key}
              style={[styles.pill, sortMode === opt.key && styles.pillActive]}
              onPress={() => setSortMode(opt.key)}
              accessibilityRole="button"
              accessibilityState={{ selected: sortMode === opt.key }}
              accessibilityLabel={`Sort by ${opt.label}`}
            >
              <Text style={[styles.pillText, sortMode === opt.key && styles.pillTextActive]}>
                {opt.label}
              </Text>
            </TouchableOpacity>
          ))}
          <View style={styles.pillSep} />
          {FILTER_OPTIONS.map((opt) => (
            <TouchableOpacity
              key={opt.key}
              style={[styles.pill, filterMode === opt.key && styles.pillActive]}
              onPress={() => setFilterMode(opt.key)}
              accessibilityRole="button"
              accessibilityState={{ selected: filterMode === opt.key }}
              accessibilityLabel={`Filter by ${opt.label}`}
            >
              <Text style={[styles.pillText, filterMode === opt.key && styles.pillTextActive]}>
                {opt.label}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>

      <FlatList
        data={questions}
        renderItem={renderItem}
        keyExtractor={keyExtractor}
        contentContainerStyle={styles.listContent}
        showsVerticalScrollIndicator={false}
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Text style={styles.emptyText}>No questions yet</Text>
            <Text style={styles.emptySubText}>Be the first to ask!</Text>
          </View>
        }
      />

      {/* Ask question input */}
      <View style={styles.inputArea}>
        <View style={styles.anonymousRow}>
          <Text style={styles.anonymousLabel}>Ask anonymously</Text>
          <Switch
            value={isAnonymous}
            onValueChange={setIsAnonymous}
            trackColor={{ false: colors.neutral[200], true: colors.primary.goldLight }}
            thumbColor={isAnonymous ? colors.primary.gold : colors.neutral[400]}
          />
        </View>
        <View style={styles.inputRow}>
          <TextInput
            style={styles.textInput}
            value={text}
            onChangeText={setText}
            placeholder="Ask a question..."
            placeholderTextColor={colors.neutral[400]}
            maxLength={500}
            multiline
            editable={!isSending}
            accessibilityLabel="Ask a question"
          />
          <TouchableOpacity
            style={[styles.sendBtn, (!text.trim() || isSending) && styles.sendBtnDisabled]}
            onPress={handleAsk}
            disabled={!text.trim() || isSending}
            accessibilityRole="button"
            accessibilityLabel="Submit question"
          >
            <Text style={styles.sendBtnText}>Ask</Text>
          </TouchableOpacity>
        </View>
      </View>
    </KeyboardAvoidingView>
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
  controls: { paddingHorizontal: 12, paddingTop: 8 },
  pillRow: { flexDirection: 'row', gap: 6, flexWrap: 'wrap', alignItems: 'center' },
  pill: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    backgroundColor: colors.neutral[100],
  },
  pillActive: {
    backgroundColor: colors.primary.navy,
  },
  pillText: { ...typography.caption, fontWeight: '600', color: colors.neutral[600] },
  pillTextActive: { color: '#FFFFFF' },
  pillSep: { width: 1, height: 20, backgroundColor: colors.border, marginHorizontal: 4 },
  listContent: { paddingHorizontal: 12, paddingTop: 8, paddingBottom: 8 },
  emptyContainer: { alignItems: 'center', paddingVertical: 60 },
  emptyText: { ...typography.body, color: colors.neutral[500] },
  emptySubText: { ...typography.bodySmall, color: colors.neutral[400], marginTop: 4 },
  questionCard: { marginBottom: 10, padding: 12 },
  questionHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 },
  questionAuthor: { ...typography.label, color: colors.foreground, fontWeight: '600', flex: 1 },
  questionTime: { ...typography.caption, color: colors.neutral[400] },
  questionText: { ...typography.body, color: colors.foreground, marginBottom: 8 },
  answerBox: {
    backgroundColor: colors.successLight,
    borderRadius: 8,
    padding: 10,
    marginBottom: 8,
  },
  answerLabel: { ...typography.caption, fontWeight: '700', color: colors.success, marginBottom: 4 },
  answerText: { ...typography.bodySmall, color: colors.foreground },
  answerAuthor: { ...typography.caption, color: colors.neutral[500], marginTop: 4, fontStyle: 'italic' },
  questionFooter: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  upvoteBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 16,
    backgroundColor: colors.neutral[100],
  },
  upvoteBtnActive: { backgroundColor: colors.primary.goldLight },
  upvoteBtnDisabled: { opacity: 0.5 },
  upvoteIcon: { fontSize: 12, color: colors.neutral[500] },
  upvoteIconActive: { color: colors.primary.goldDark },
  upvoteCount: { ...typography.label, color: colors.neutral[600] },
  upvoteCountActive: { color: colors.primary.goldDark },
  tagRow: { flexDirection: 'row', gap: 6 },
  inputArea: {
    borderTopWidth: 1,
    borderTopColor: colors.border,
    backgroundColor: colors.card,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  anonymousRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  anonymousLabel: { ...typography.bodySmall, color: colors.neutral[500] },
  inputRow: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: 8,
  },
  textInput: {
    flex: 1,
    ...typography.body,
    color: colors.foreground,
    backgroundColor: colors.neutral[100],
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 10,
    maxHeight: 80,
  },
  sendBtn: {
    backgroundColor: colors.primary.gold,
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 10,
  },
  sendBtnDisabled: { opacity: 0.4 },
  sendBtnText: { ...typography.label, color: colors.primary.navy, fontWeight: '700' },
});
