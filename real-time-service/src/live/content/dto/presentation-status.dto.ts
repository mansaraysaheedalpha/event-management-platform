export class PresentationStatusDto {
  sessionId: string;
  status: 'ready' | 'failed' | 'processing';
  userId: string;
}
