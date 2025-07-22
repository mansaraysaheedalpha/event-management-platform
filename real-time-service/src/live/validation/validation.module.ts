import { Module } from '@nestjs/common';
import { ValidationService } from './validation.service';
import { ValidationGateway } from './validation.gateway';

@Module({
  providers: [ValidationService, ValidationGateway],
})
export class ValidationModule {}
