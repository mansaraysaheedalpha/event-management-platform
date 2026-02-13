// src/notifications/update-notifications.gateway.ts
import { Logger } from '@nestjs/common';
import { OnEvent } from '@nestjs/event-emitter';
import {
  WebSocketGateway,
  WebSocketServer,
} from '@nestjs/websockets';
import { Server } from 'socket.io';

/**
 * Gateway for broadcasting event and session update notifications to attendees.
 * Listens to Redis Pub/Sub events and broadcasts them via WebSocket.
 */
@WebSocketGateway({
  cors: { origin: true, credentials: true },
  namespace: '/events',
})
export class UpdateNotificationsGateway {
  @WebSocketServer()
  server: Server;

  private readonly logger = new Logger(UpdateNotificationsGateway.name);

  /**
   * Handle event update notifications from Redis.
   * Broadcasts to all users registered for that event.
   */
  @OnEvent('platform.events.updated.v1')
  handleEventUpdated(payload: {
    eventId: string;
    eventName: string;
    startDate: string | null;
    endDate: string | null;
    organizationId: string;
  }) {
    const { eventId, eventName, startDate, endDate } = payload;
    const eventRoom = `event:${eventId}`;

    // Broadcast to all attendees in the event room
    this.server.to(eventRoom).emit('event.updated', {
      eventId,
      eventName,
      startDate,
      endDate,
      message: 'Event details have been updated',
    });

    this.logger.log(
      `📢 Broadcasted event.updated for event ${eventId} (${eventName}) to room ${eventRoom}`,
    );
  }

  /**
   * Handle session update notifications from Redis.
   * Broadcasts to all users registered for that event.
   */
  @OnEvent('platform.sessions.updated.v1')
  handleSessionUpdated(payload: {
    sessionId: string;
    sessionTitle: string;
    startTime: string | null;
    endTime: string | null;
    eventId: string;
  }) {
    const { sessionId, sessionTitle, startTime, endTime, eventId } = payload;
    const eventRoom = `event:${eventId}`;
    const sessionRoom = `session:${sessionId}`;

    // Broadcast to both event and session rooms
    const updatePayload = {
      sessionId,
      sessionTitle,
      startTime,
      endTime,
      eventId,
      message: 'Session details have been updated',
    };

    this.server.to(eventRoom).emit('session.updated', updatePayload);
    this.server.to(sessionRoom).emit('session.updated', updatePayload);

    this.logger.log(
      `📢 Broadcasted session.updated for session ${sessionId} (${sessionTitle}) to rooms ${eventRoom} and ${sessionRoom}`,
    );
  }
}
