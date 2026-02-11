// Video grid component for multi-participant layout
// Ported from ../globalconnect/src/components/features/breakout/video/VideoGrid.tsx

import React, { useMemo } from 'react';
import { View, ScrollView, StyleSheet, useWindowDimensions } from 'react-native';
import type { DailyParticipant } from '@daily-co/react-native-daily-js';
import { VideoTile } from './VideoTile';

interface VideoGridProps {
  participants: DailyParticipant[];
  style?: object;
}

export function VideoGrid({ participants, style }: VideoGridProps) {
  const { width: windowWidth, height: windowHeight } = useWindowDimensions();
  const isLandscape = windowWidth > windowHeight;

  // Find screen sharer or determine main speaker
  const { speaker, others } = useMemo(() => {
    // Prioritize screen sharers
    const screenSharer = participants.find((p) => p.screen);
    if (screenSharer) {
      return {
        speaker: screenSharer,
        others: participants.filter((p) => p.session_id !== screenSharer.session_id),
      };
    }

    // If only one remote participant, make them the speaker
    const local = participants.find((p) => p.local);
    const remotes = participants.filter((p) => !p.local);

    if (remotes.length === 1) {
      return {
        speaker: remotes[0],
        others: local ? [local] : [],
      };
    }

    // Multiple remotes - use grid layout
    return {
      speaker: null,
      others: participants,
    };
  }, [participants]);

  // Calculate grid columns based on participant count
  const gridColumns = useMemo(() => {
    const count = speaker ? others.length : participants.length;
    if (count === 1) return 1;
    if (count === 2) return isLandscape ? 2 : 1;
    if (count <= 4) return 2;
    if (count <= 6) return isLandscape ? 3 : 2;
    if (count <= 9) return isLandscape ? 3 : 2;
    return isLandscape ? 4 : 2;
  }, [speaker, others.length, participants.length, isLandscape]);

  // Speaker + sidebar layout
  if (speaker) {
    return (
      <View style={[styles.speakerLayout, style]}>
        {/* Main speaker/screen share */}
        <View style={styles.speakerMain}>
          <VideoTile participant={speaker} isLocal={speaker.local} isLarge style={styles.speakerTile} />
        </View>

        {/* Sidebar with other participants */}
        {others.length > 0 && (
          <ScrollView
            horizontal={!isLandscape}
            style={[styles.sidebar, isLandscape ? styles.sidebarVertical : styles.sidebarHorizontal]}
            contentContainerStyle={styles.sidebarContent}
            showsHorizontalScrollIndicator={false}
            showsVerticalScrollIndicator={false}
          >
            {others.map((participant) => (
              <VideoTile
                key={participant.session_id}
                participant={participant}
                isLocal={participant.local}
                style={[isLandscape ? styles.sidebarTileVertical : styles.sidebarTileHorizontal]}
              />
            ))}
          </ScrollView>
        )}
      </View>
    );
  }

  // Grid layout for equal participants
  return (
    <ScrollView style={[styles.gridContainer, style]} contentContainerStyle={styles.gridContent}>
      <View style={[styles.grid, { gap: 8 }]}>
        {participants.map((participant) => (
          <View
            key={participant.session_id}
            style={[
              styles.gridItem,
              {
                width: windowWidth / gridColumns - 12,
              },
            ]}
          >
            <VideoTile participant={participant} isLocal={participant.local} />
          </View>
        ))}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  speakerLayout: {
    flex: 1,
    flexDirection: 'row',
  },
  speakerMain: {
    flex: 1,
    minWidth: 0,
    minHeight: 0,
  },
  speakerTile: {
    width: '100%',
    height: '100%',
  },
  sidebar: {
    flexShrink: 0,
  },
  sidebarHorizontal: {
    height: 100,
  },
  sidebarVertical: {
    width: 176,
  },
  sidebarContent: {
    gap: 8,
    padding: 8,
  },
  sidebarTileHorizontal: {
    width: 140,
    height: 84,
  },
  sidebarTileVertical: {
    width: 160,
    aspectRatio: 16 / 9,
  },
  gridContainer: {
    flex: 1,
  },
  gridContent: {
    padding: 8,
  },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'flex-start',
  },
  gridItem: {
    marginBottom: 8,
  },
});
