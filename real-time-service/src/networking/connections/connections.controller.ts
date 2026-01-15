//src/networking/connections/connections.controller.ts
import {
  Controller,
  Get,
  Post,
  Patch,
  Body,
  Param,
  Query,
  UseGuards,
  Request,
} from '@nestjs/common';
import { ApiTags, ApiOperation, ApiBearerAuth } from '@nestjs/swagger';
import { JwtAuthGuard } from 'src/common/guards/jwt-auth.guard';
import { ConnectionsService } from './connections.service';
import { CreateConnectionDto, ReportOutcomeDto } from './dto';

@ApiTags('Connections')
@Controller('connections')
@UseGuards(JwtAuthGuard)
@ApiBearerAuth()
export class ConnectionsController {
  constructor(private readonly connectionsService: ConnectionsService) {}

  @Post()
  @ApiOperation({ summary: 'Create a new connection' })
  async createConnection(@Body() dto: CreateConnectionDto) {
    return this.connectionsService.createConnection(dto);
  }

  @Get('user/:userId')
  @ApiOperation({ summary: "Get all of a user's connections" })
  async getUserConnections(@Param('userId') userId: string) {
    return this.connectionsService.getUserConnections(userId);
  }

  @Get('user/:userId/event/:eventId')
  @ApiOperation({ summary: "Get user's connections for a specific event" })
  async getUserEventConnections(
    @Param('userId') userId: string,
    @Param('eventId') eventId: string,
  ) {
    return this.connectionsService.getUserEventConnections(userId, eventId);
  }

  @Get('event/:eventId')
  @ApiOperation({ summary: 'Get all connections for an event (organizer)' })
  async getEventConnections(@Param('eventId') eventId: string) {
    return this.connectionsService.getEventConnections(eventId);
  }

  @Get(':id')
  @ApiOperation({ summary: 'Get a specific connection with context' })
  async getConnection(@Param('id') id: string) {
    return this.connectionsService.getConnectionWithContext(id);
  }

  @Patch(':id/follow-up/sent')
  @ApiOperation({ summary: 'Mark follow-up as sent' })
  async markFollowUpSent(@Param('id') id: string) {
    await this.connectionsService.markFollowUpSent(id);
    return { success: true };
  }

  @Patch(':id/follow-up/opened')
  @ApiOperation({ summary: 'Mark follow-up as opened' })
  async markFollowUpOpened(@Param('id') id: string) {
    await this.connectionsService.markFollowUpOpened(id);
    return { success: true };
  }

  @Patch(':id/follow-up/replied')
  @ApiOperation({ summary: 'Mark follow-up as replied' })
  async markFollowUpReplied(@Param('id') id: string) {
    await this.connectionsService.markFollowUpReplied(id);
    return { success: true };
  }

  @Patch(':id/outcome')
  @ApiOperation({ summary: 'Report an outcome for a connection' })
  async reportOutcome(
    @Param('id') id: string,
    @Body() dto: ReportOutcomeDto,
  ) {
    return this.connectionsService.reportOutcome(id, dto);
  }

  @Get('stats/event/:eventId')
  @ApiOperation({ summary: 'Get networking statistics for an event' })
  async getEventStats(@Param('eventId') eventId: string) {
    return this.connectionsService.getEventNetworkingStats(eventId);
  }

  @Get('stats/user/:userId')
  @ApiOperation({ summary: 'Get networking statistics for a user' })
  async getUserStats(@Param('userId') userId: string) {
    return this.connectionsService.getUserNetworkingStats(userId);
  }

  @Get('check/:userAId/:userBId/:eventId')
  @ApiOperation({ summary: 'Check if a connection exists between two users' })
  async checkConnection(
    @Param('userAId') userAId: string,
    @Param('userBId') userBId: string,
    @Param('eventId') eventId: string,
  ) {
    const exists = await this.connectionsService.connectionExists(
      userAId,
      userBId,
      eventId,
    );
    return { exists };
  }
}
