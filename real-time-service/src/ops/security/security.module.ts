//src/ops/security/security.module.ts
import { Module } from '@nestjs/common';
import { SecurityService } from './security.service';
import { SecurityGateway } from './security.gateway';

@Module({
  providers: [SecurityService, SecurityGateway],
})
export class SecurityModule {}
