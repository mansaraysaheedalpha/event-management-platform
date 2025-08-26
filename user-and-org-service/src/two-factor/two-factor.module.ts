//src/two-factor/two-factor.module.ts
import { Module } from '@nestjs/common';
import { TwoFactorController } from './two-factor.controller';
import { TwoFactorService } from './two-factor.service';
import { PrismaModule } from 'src/prisma.module';
import { TwoFactorResolver } from './two-factor.resolver';

@Module({
  imports: [PrismaModule],
  controllers: [TwoFactorController],
  providers: [TwoFactorService, TwoFactorResolver],
  exports: [TwoFactorService],
})
export class TwoFactorModule {}
