//src/live/sales/dto/ticket-availability.dto.ts
export class TicketAvailabilityDto {
  eventId: string;
  ticketTypeId: string;
  status: 'AVAILABLE' | 'SOLD_OUT' | 'LOW_STOCK';
  ticketsRemaining?: number;
}
