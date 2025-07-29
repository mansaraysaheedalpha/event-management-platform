import { ConflictException, Injectable, Logger } from '@nestjs/common';
import { PrismaService } from 'src/prisma.service';
import { IdempotencyService } from 'src/shared/services/idempotency.service';
import { SendBackchannelMessageDto } from './dto/send-backchannel-message.dto';

@Injectable()
export class BackchannelService {
  private readonly logger = new Logger(BackchannelService.name);

  constructor(
    private readonly prisma: PrismaService,
    private readonly idempotencyService: IdempotencyService,
  ) {}

  /**
   * Creates and saves a new backchannel message.
   */
  async sendMessage(
    senderId: string,
    sessionId: string,
    dto: SendBackchannelMessageDto,
  ) {
    const canProceed = await this.idempotencyService.checkAndSet(
      dto.idempotencyKey,
    );
    if (!canProceed) {
      throw new ConflictException('This message has already been sent.');
    }

    this.logger.log(
      `User ${senderId} sending backchannel message in session ${sessionId}`,
    );

    return this.prisma.backchannelMessage.create({
      data: {
        text: dto.text,
        senderId,
        sessionId,
      },
      include: {
        sender: {
          select: { id: true, firstName: true, lastName: true },
        },
      },
    });
  }
}
