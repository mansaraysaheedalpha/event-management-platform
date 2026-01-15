//src/common/interfaces/presentation-state.interface.ts
/**
 * Represents the current state of a live presentation.
 * Used to sync presenter view with attendees in real-time.
 */
export interface PresentationState {
  currentSlide: number;
  totalSlides: number;
  isActive: boolean;
  slideUrls: string[];
  downloadEnabled?: boolean;
  originalFilename?: string;
}
