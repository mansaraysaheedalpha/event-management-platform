export interface OfferContent {
  id: string;
  eventId: string;
  title: string;
  description: string;
  price: number;
  original_price?: number;
  currency?: string;
  image_url?: string;
  expires_at?: string;
}
