import { Module, forwardRef } from '@nestjs/common';
import { AuditService } from './audit.service';
import { AuditGateway } from './audit.gateway';

@Module({
  // We need to import the HttpModule from our SharedModule for the internal API call
  // Since SharedModule is global, we don't need to explicitly import it here.
  providers: [AuditService, AuditGateway],
  exports: [AuditService],
})
export class AuditModule {}
