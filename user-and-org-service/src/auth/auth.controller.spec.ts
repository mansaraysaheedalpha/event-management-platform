import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication, ValidationPipe } from '@nestjs/common';
import * as request from 'supertest';
import { AppModule } from '../app.module';
import { PrismaService } from '../prisma.service';
import * as bcrypt from 'bcrypt';

describe('AuthController (Integration)', () => {
  let app: INestApplication;
  let prisma: PrismaService;

  beforeAll(async () => {
    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();

    app = moduleFixture.createNestApplication();
    app.useGlobalPipes(new ValidationPipe()); // Ensure validation pipe is active
    await app.init();

    prisma = app.get<PrismaService>(PrismaService);

    // Clean the database before running tests
    await prisma.membership.deleteMany({});
    await prisma.organization.deleteMany({});
    await prisma.user.deleteMany({});
    await prisma.role.deleteMany({});

    // Seed the necessary system roles for the tests
    await prisma.role.createMany({
      data: [
        { name: 'OWNER', isSystemRole: true },
        { name: 'ADMIN', isSystemRole: true },
        { name: 'MEMBER', isSystemRole: true },
      ],
      skipDuplicates: true,
    });
  });

  // Clean up the database again after each test to ensure isolation
  afterEach(async () => {
    await prisma.membership.deleteMany({});
    await prisma.organization.deleteMany({});
    await prisma.user.deleteMany({});
  });

  afterAll(async () => {
    await app.close();
  });

  describe('POST /auth/login', () => {
    it('should return an access token for a valid user with correct credentials', async () => {
      // ARRANGE: Create a user, org, and membership in the test database
      const hashedPassword = await bcrypt.hash('password123', 10);
      const user = await prisma.user.create({
        data: {
          email: 'test@example.com',
          password: hashedPassword,
          first_name: 'Test',
          last_name: 'User',
        },
      });
      const org = await prisma.organization.create({
        data: { name: 'Test Org' },
      });
      const memberRole = await prisma.role.findFirst({
        where: { name: 'MEMBER' },
      });

      await prisma.membership.create({
        data: {
          userId: user.id,
          organizationId: org.id,
          roleId: memberRole!.id,
        },
      });

      // ACT: Make a request to the login endpoint
      const response = await request(app.getHttpServer())
        .post('/auth/login')
        .send({ email: 'test@example.com', password: 'password123' });

      // ASSERT
      expect(response.status).toBe(201);
      expect(response.body).toHaveProperty('access_token');
      expect(response.headers['set-cookie']).toBeDefined();
    });

    it('should return 401 Unauthorized for invalid credentials', async () => {
      // ACT
      const response = await request(app.getHttpServer())
        .post('/auth/login')
        .send({ email: 'wrong@example.com', password: 'wrongpassword' });

      // ASSERT
      expect(response.status).toBe(401);
    });

    it('should return a 2FA requirement for a user with 2FA enabled', async () => {
      // ARRANGE
      const hashedPassword = await bcrypt.hash('password123', 10);
      await prisma.user.create({
        data: {
          email: '2fa-user@example.com',
          password: hashedPassword,
          first_name: '2FA',
          last_name: 'User',
          isTwoFactorEnabled: true, // 2FA is enabled
        },
      });

      // ACT
      const response = await request(app.getHttpServer())
        .post('/auth/login')
        .send({ email: '2fa-user@example.com', password: 'password123' });

      // ASSERT
      expect(response.status).toBe(201);
      expect(response.body.requires2FA).toBe(true);
      expect(response.body).toHaveProperty('userId');
    });
  });
});
