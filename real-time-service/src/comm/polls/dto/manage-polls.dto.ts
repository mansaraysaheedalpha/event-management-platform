import { IsIn, IsString, IsUUID } from 'class-validator';

export class ManagePollDto {
  @IsUUID(4)
  pollId: string;

  @IsString()
  @IsIn(['close']) // For now, 'close' is the only action, but this allows for future expansion (e.g., 'open', 'delete')
  action: 'close';

  @IsUUID(4)
  idempotencyKey: string;
}
