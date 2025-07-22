import { Body, Controller, Post, Req, UseGuards } from '@nestjs/common';
import { AuthGuard } from '@nestjs/passport';
import { TwoFactorService } from './two-factor.service';
import { TwoFactorDTO } from './dto/two-factor.dto';

@Controller('2fa')
export class TwoFactorController {
  constructor(private twoFactorService: TwoFactorService) {}
  @Post('generate')
  @UseGuards(AuthGuard('jwt'))
  async Generate2FA(
    @Req() req: { user: { sub: string } },
  ): Promise<{ qrCodeDataUrl: string }> {
    return await this.twoFactorService.setup2FA(req.user.sub);
  }

  @Post('turn-on')
  @UseGuards(AuthGuard('jwt'))
  async turn2FA(
    @Req() req: { user: { sub: string } },
    @Body() twoFactorDto: TwoFactorDTO,
  ) {
    const userId = req.user.sub;
    return await this.twoFactorService.turnOn2FA(userId, twoFactorDto.code);
  }
}
