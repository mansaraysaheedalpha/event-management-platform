//src/common/guards/internal-api-key.guard.ts
import {
  Injectable,
  CanActivate,
  ExecutionContext,
  UnauthorizedException,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';

@Injectable()
export class InternalApiKeyGuard implements CanActivate {
  constructor(private readonly configService: ConfigService) {}

  canActivate(context: ExecutionContext): boolean {
    const request = context
      .switchToHttp()
      .getRequest<{ headers: Record<string, string | undefined> }>();
    const providedKey = request.headers['x-internal-api-key'];
    const validKey = this.configService.get<string>('INTERNAL_API_KEY');

    if (providedKey && validKey && providedKey === validKey) {
      return true;
    }

    throw new UnauthorizedException('Invalid or missing internal API key.');
  }
}
