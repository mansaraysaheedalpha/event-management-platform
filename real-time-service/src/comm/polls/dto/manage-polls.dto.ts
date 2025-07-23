import { IsIn, IsNotEmpty, IsString, IsUUID } from 'class-validator';

/**
 * DTO for managing a poll, currently supports closing a poll.
 * Contains the poll ID, the action ('close'), and idempotency key.
 */
export class ManagePollDto {
  @IsNotEmpty()
  @IsUUID('4')
  pollId: string;

  @IsString()
  @IsIn(['close']) // Only accepts the string 'close' (expandable later to open, delete etc)
  action: 'close';

  @IsNotEmpty()
  @IsUUID('4')
  idempotencyKey: string;
}
