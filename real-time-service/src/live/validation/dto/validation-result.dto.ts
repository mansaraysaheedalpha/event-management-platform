class ValidatedUserDto {
  id: string;
  name: string;
  avatarUrl?: string;
}

export class ValidationResultDto {
  isValid: boolean;
  ticketCode: string;
  validatedAt: string;
  user?: ValidatedUserDto;
  accessLevel?: string;
  errorReason?: string;
}
