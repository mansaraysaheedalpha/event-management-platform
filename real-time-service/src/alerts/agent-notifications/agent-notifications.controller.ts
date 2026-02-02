import {
  Controller,
  Get,
  Patch,
  Post,
  Query,
  Param,
  Body,
  UseGuards,
  Request,
} from '@nestjs/common';
import { ApiTags, ApiOperation, ApiBearerAuth, ApiQuery } from '@nestjs/swagger';
import { AuthGuard } from '@nestjs/passport';
import { AgentNotificationsService } from './agent-notifications.service';
import { MarkAllAsReadDto } from './dto/agent-notification.dto';

@ApiTags('Agent Notifications')
@Controller('agent-notifications')
@UseGuards(AuthGuard('jwt'))
@ApiBearerAuth()
export class AgentNotificationsController {
  constructor(private readonly service: AgentNotificationsService) {}

  @Get()
  @ApiOperation({ summary: 'Get agent notifications for an event' })
  @ApiQuery({ name: 'eventId', required: true })
  @ApiQuery({ name: 'limit', required: false })
  @ApiQuery({ name: 'cursor', required: false })
  async getNotifications(
    @Request() req: { user: { sub: string } },
    @Query('eventId') eventId: string,
    @Query('limit') limit?: string,
    @Query('cursor') cursor?: string,
  ) {
    const parsedLimit = limit ? parseInt(limit, 10) : 50;
    return this.service.getNotifications(
      eventId,
      req.user.sub,
      parsedLimit,
      cursor,
    );
  }

  @Get('unread-count')
  @ApiOperation({ summary: 'Get unread notification count' })
  @ApiQuery({ name: 'eventId', required: true })
  async getUnreadCount(
    @Request() req: { user: { sub: string } },
    @Query('eventId') eventId: string,
  ) {
    const count = await this.service.getUnreadCount(eventId, req.user.sub);
    return { count };
  }

  @Patch(':id/read')
  @ApiOperation({ summary: 'Mark notification as read' })
  async markAsRead(
    @Request() req: { user: { sub: string } },
    @Param('id') id: string,
  ) {
    await this.service.markAsRead(id, req.user.sub);
    return { success: true };
  }

  @Post('mark-all-read')
  @ApiOperation({ summary: 'Mark all notifications as read for an event' })
  async markAllAsRead(
    @Request() req: { user: { sub: string } },
    @Body() body: MarkAllAsReadDto,
  ) {
    return this.service.markAllAsRead(body.eventId, req.user.sub);
  }
}
