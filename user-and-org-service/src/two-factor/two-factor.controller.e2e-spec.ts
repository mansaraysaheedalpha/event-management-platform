import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication, ValidationPipe } from '@nestjs/common';
import * as request from 'supertest';
import { AppModule } from '../app.module';
import { PrismaService } from '../prisma.service';
import * as bcrypt from 'bcrypt';
import { TwoFactorService } from './two-factor.service';

describe('TwoFactorController (E2E)', () => {
  let app: INestApplication;
  let prisma: PrismaService;
  let twoFactorService: TwoFactorService;
  let accessToken: string;
  let userId: string;

  beforeAll(async () => {
    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();

    app = moduleFixture.createNestApplication();
    prisma = app.get<PrismaService>(PrismaService);
    twoFactorService = app.get<TwoFactorService>(TwoFactorService);
    
    app.useGlobalPipes(new ValidationPipe());
    await app.init();

    // Clean up and seed database
    await prisma.user.deleteMany({ where: { email: 'e2e-2fa-test@example.com' }});
    const hashedPassword = await bcrypt.hash('password123', 10);
    const user = await prisma.user.create({
      data: { email: 'e2e-2fa-test@example.com', password: hashedPassword },
    });
    userId = user.id;

    // Log the user in to get a token for testing
    const loginRes = await request(app.getHttpServer()).post('/auth/login').send({
      email: user.email,
      password: 'password123',
    });
    accessToken = loginRes.body.access_token;
  });

  afterAll(async () => {
    await app.close();
  });

  describe('/2fa/generate (POST)', () => {
    it('should generate a 2FA secret and return a QR code data URL', () => {
      return request(app.getHttpServer())
        .post('/2fa/generate')
        .set('Authorization', `Bearer ${accessToken}`)
        .expect(201)
        .expect((res) => {
          expect(res.body).toHaveProperty('qrCodeDataUrl');
          expect(res.body.qrCodeDataUrl).toContain('data:image/png;base64');
        });
    });
  });

  describe('/2fa/turn-on (POST)', () => {
    it('should fail to turn on with an invalid code', () => {
      return request(app.getHttpServer())
        .post('/2fa/turn-on')
        .set('Authorization', `Bearer ${accessToken}`)
        .send({ code: '000000' }) // An invalid code
        .expect(401);
    });

    it('should successfully turn on with a valid code', async () => {
      // To test this, we need a valid code. We can't guess it,
      // but we can mock the service method that validates it.
      const is2FACodeValidSpy = jest.spyOn(twoFactorService, 'is2FACodeValid').mockResolvedValue(true);

      await request(app.getHttpServer())
        .post('/2fa/turn-on')
        .set('Authorization', `Bearer ${accessToken}`)
        .send({ code: 'a-valid-code' })
        .expect(201)
        .expect((res) => {
          expect(res.body.message).toContain('enabled successfully');
        });
      
      const user = await prisma.user.findUnique({ where: { id: userId } });
      expect(user.isTwoFactorEnabled).toBe(true);

      is2FACodeValidSpy.mockRestore(); // Clean up the spy
    });
  });
});