//src/comm/chat/dto/react-to-message.dto.ts
import { IsNotEmpty, IsString, IsUUID, MaxLength } from 'class-validator';

export class ReactToMessageDto {
  @IsNotEmpty()
  @IsUUID('4')
  messageId: string;

  @IsString()
  @IsNotEmpty()
  @MaxLength(8) // Allow for complex emojis
  emoji: string;

  @IsNotEmpty()
  @IsUUID('4')
  idempotencyKey: string;
}
