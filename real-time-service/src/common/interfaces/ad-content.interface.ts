export interface AdContent {
  id: string;
  eventId: string;
  content: {
    type: 'BANNER' | 'VIDEO';
    mediaUrl: string;
    clickUrl: string;
  };
}
