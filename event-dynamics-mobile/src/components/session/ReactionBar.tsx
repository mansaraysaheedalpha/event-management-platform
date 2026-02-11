// Reaction bar with emoji options — sits at the bottom of session view
// Horizontal scrollable row of popular emojis with a "more" button

import React, { useState, useRef, useEffect } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  Modal,
  Pressable,
} from 'react-native';
import { colors, typography } from '@/theme';
import { ALLOWED_EMOJIS } from '@/hooks/useSessionReactions';

interface ReactionBarProps {
  onReaction: (emoji: string) => boolean;
  disabled?: boolean;
}

const QUICK_EMOJIS = ALLOWED_EMOJIS.slice(0, 6);

export function ReactionBar({ onReaction, disabled = false }: ReactionBarProps) {
  const [showAll, setShowAll] = useState(false);
  const [lastTapped, setLastTapped] = useState<string | null>(null);
  const tapTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (tapTimerRef.current) clearTimeout(tapTimerRef.current);
    };
  }, []);

  const handleTap = (emoji: string) => {
    if (disabled) return;
    const sent = onReaction(emoji);
    if (sent) {
      setLastTapped(emoji);
      if (tapTimerRef.current) clearTimeout(tapTimerRef.current);
      tapTimerRef.current = setTimeout(() => setLastTapped(null), 300);
    }
  };

  return (
    <>
      <View style={[styles.bar, disabled && styles.barDisabled]}>
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.scrollContent}
        >
          {QUICK_EMOJIS.map((emoji) => (
            <TouchableOpacity
              key={emoji}
              onPress={() => handleTap(emoji)}
              style={[
                styles.emojiBtn,
                lastTapped === emoji && styles.emojiBtnActive,
              ]}
              activeOpacity={0.6}
              disabled={disabled}
            >
              <Text style={styles.emojiText}>{emoji}</Text>
            </TouchableOpacity>
          ))}
          <TouchableOpacity
            onPress={() => setShowAll(true)}
            style={styles.moreBtn}
            disabled={disabled}
          >
            <Text style={styles.moreText}>+</Text>
          </TouchableOpacity>
        </ScrollView>
      </View>

      <Modal
        visible={showAll}
        transparent
        animationType="slide"
        onRequestClose={() => setShowAll(false)}
      >
        <Pressable style={styles.modalOverlay} onPress={() => setShowAll(false)}>
          <Pressable style={styles.modalContent} onPress={(e) => e.stopPropagation()}>
            <Text style={styles.modalTitle}>Reactions</Text>
            <View style={styles.emojiGrid}>
              {ALLOWED_EMOJIS.map((emoji) => (
                <TouchableOpacity
                  key={emoji}
                  onPress={() => {
                    handleTap(emoji);
                    setShowAll(false);
                  }}
                  style={styles.gridEmojiBtn}
                  activeOpacity={0.6}
                >
                  <Text style={styles.gridEmojiText}>{emoji}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </Pressable>
        </Pressable>
      </Modal>
    </>
  );
}

const styles = StyleSheet.create({
  bar: {
    backgroundColor: colors.card,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    paddingVertical: 8,
  },
  barDisabled: {
    opacity: 0.4,
  },
  scrollContent: {
    paddingHorizontal: 12,
    gap: 6,
    flexDirection: 'row',
    alignItems: 'center',
  },
  emojiBtn: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: colors.neutral[100],
    justifyContent: 'center',
    alignItems: 'center',
  },
  emojiBtnActive: {
    backgroundColor: colors.primary.goldLight,
    transform: [{ scale: 1.15 }],
  },
  emojiText: {
    fontSize: 22,
  },
  moreBtn: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: colors.neutral[200],
    justifyContent: 'center',
    alignItems: 'center',
  },
  moreText: {
    fontSize: 20,
    fontWeight: '700',
    color: colors.neutral[600],
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.4)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: colors.background,
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    padding: 20,
    paddingBottom: 40,
  },
  modalTitle: {
    ...typography.h3,
    color: colors.foreground,
    marginBottom: 16,
    textAlign: 'center',
  },
  emojiGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'center',
    gap: 8,
  },
  gridEmojiBtn: {
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: colors.neutral[100],
    justifyContent: 'center',
    alignItems: 'center',
  },
  gridEmojiText: {
    fontSize: 26,
  },
});
