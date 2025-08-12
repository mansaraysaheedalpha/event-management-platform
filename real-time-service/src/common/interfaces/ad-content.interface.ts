//src/common/interfaces/ad-content.interface.ts
/**
 * @description Advertisement content to be shown during an event.
 * Can be a banner or video with clickable redirect.
 */
export interface AdContent {
  id: string;
  eventId: string;
  content: {
    type: 'BANNER' | 'VIDEO';
    mediaUrl: string;
    clickUrl: string;
  };
}
