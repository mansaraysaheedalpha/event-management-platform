//src/common/dto/user-data.dto.ts
/**
 * Basic user profile information used across services.
 * Often returned in lightweight lookups or personalization.
 */
export class UserDataDto {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
}
