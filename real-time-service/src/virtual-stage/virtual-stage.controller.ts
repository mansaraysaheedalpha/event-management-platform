// src/virtual-stage/virtual-stage.controller.ts
import {
  Controller,
  Post,
  Delete,
  Body,
  Param,
  UseGuards,
  Logger,
  InternalServerErrorException,
} from '@nestjs/common';
import { JwtAuthGuard } from '../common/guards/jwt-auth.guard';
import { CurrentUser } from '../common/decorators/current-user.decorator';
import { VirtualStageService } from './virtual-stage.service';
import { CreateStageRoomDto } from './dto/create-stage-room.dto';
import { GetStageTokenDto } from './dto/get-stage-token.dto';

interface JwtUser {
  sub: string;
  email: string;
  firstName?: string;
  lastName?: string;
  orgId?: string;
  permissions?: string[];
}

@Controller('virtual-stage')
@UseGuards(JwtAuthGuard)
export class VirtualStageController {
  private readonly logger = new Logger(VirtualStageController.name);

  constructor(private readonly virtualStageService: VirtualStageService) {}

  /**
   * POST /virtual-stage/rooms
   * Creates a Daily room for a session.
   */
  @Post('rooms')
  async createRoom(
    @Body() dto: CreateStageRoomDto,
    @CurrentUser() user: JwtUser,
  ) {
    this.logger.log(
      `User ${user.sub} creating room for session ${dto.sessionId}`,
    );

    const result = await this.virtualStageService.createSessionRoom(dto);
    if (!result) {
      throw new InternalServerErrorException('Failed to create Daily room');
    }

    return {
      success: true,
      roomName: result.roomName,
      roomUrl: result.roomUrl,
    };
  }

  /**
   * POST /virtual-stage/token
   * Generates a meeting token for a user to join a session.
   */
  @Post('token')
  async getToken(
    @Body() dto: GetStageTokenDto,
    @CurrentUser() user: JwtUser,
  ) {
    const userName =
      [user.firstName, user.lastName].filter(Boolean).join(' ') ||
      user.email ||
      'Participant';

    this.logger.log(
      `User ${user.sub} requesting token for room ${dto.roomName} (speaker: ${dto.isSpeaker})`,
    );

    const token = await this.virtualStageService.generateToken({
      roomName: dto.roomName,
      userId: user.sub,
      userName,
      isSpeaker: dto.isSpeaker,
      broadcastOnly: dto.broadcastOnly,
    });

    if (!token) {
      throw new InternalServerErrorException(
        'Failed to generate meeting token',
      );
    }

    return { success: true, token };
  }

  /**
   * DELETE /virtual-stage/rooms/:roomName
   * Deletes a Daily room (session cleanup).
   */
  @Delete('rooms/:roomName')
  async deleteRoom(@Param('roomName') roomName: string) {
    const result = await this.virtualStageService.deleteSessionRoom(roomName);
    return { success: result };
  }
}
