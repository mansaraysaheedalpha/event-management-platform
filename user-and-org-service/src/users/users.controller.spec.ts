import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication, ValidationPipe } from '@nestjs/common';
import * as request from 'supertest';
import { AppModule } from '../app.module';
import { PrismaService } from '../prisma.service';
import * as bcrypt from 'bcrypt';

describe('UsersController (Integration)', () => {
  let app: INestApplication;
  let prisma: PrismaService;

  beforeAll(async () => {
    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();

    app = moduleFixture.createNestApplication();
    app.useGlobalPipes(new ValidationPipe());
    await app.init();

    prisma = app.get<PrismaService>(PrismaService);
  });

  // Clean all relevant tables after each test
  afterEach(async () => {
    await prisma.membership.deleteMany({});
    await prisma.organization.deleteMany({});
    await prisma.user.deleteMany({});
  });

  afterAll(async () => {
    // Ensure system roles are not deleted between test file runs
    // await prisma.role.deleteMany({});
    await app.close();
  });

  describe('POST /users', () => {
    it('should successfully register a new user and create their first organization', async () => {
      // ARRANGE
      const registerDto = {
        organization_name: 'Saheed Innovations',
        first_name: 'Saheed',
        last_name: 'Alpha',
        email: 'saheed@test.com',
        password: 'password123',
      };

      // ACT
      const response = await request(app.getHttpServer())
        .post('/users')
        .send(registerDto);

      // ASSERT - Check the API response
      expect(response.status).toBe(201);
      expect(response.body.user.email).toBe(registerDto.email);
      expect(response.body.organization.name).toBe(
        registerDto.organization_name,
      );
      expect(response.body.user.password).toBeUndefined(); // Ensure password is not returned

      // ASSERT - Verify database state
      const dbUser = await prisma.user.findUnique({
        where: { email: registerDto.email },
      });
      const dbOrg = await prisma.organization.findFirst({
        where: { name: registerDto.organization_name },
      });
      const dbMembership = await prisma.membership.findFirst({
        where: { userId: dbUser?.id },
      });
      const ownerRole = await prisma.role.findFirst({
        where: { name: 'OWNER' },
      });

      expect(dbUser).toBeDefined();
      expect(dbOrg).toBeDefined();
      expect(dbMembership).toBeDefined();
      expect(dbMembership?.organizationId).toBe(dbOrg?.id);
      expect(dbMembership?.roleId).toBe(ownerRole!.id);
    });
  });

  describe('GET /users/me', () => {
    it('should return the profile of the authenticated user', async () => {
      // ARRANGE - Create a user and log them in to get a token
      const password = 'password123';
      const hashedPassword = await bcrypt.hash(password, 10);
      const user = await prisma.user.create({
        data: {
          email: 'me@example.com',
          password: hashedPassword,
          first_name: 'Profile',
          last_name: 'User',
        },
      });
      const org = await prisma.organization.create({
        data: { name: 'My Org' },
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

      const loginResponse = await request(app.getHttpServer())
        .post('/auth/login')
        .send({ email: user.email, password: password });

      const accessToken = loginResponse.body.access_token;

      // ACT - Make an authenticated request to the /users/me endpoint
      const profileResponse = await request(app.getHttpServer())
        .get('/users/me')
        .set('Authorization', `Bearer ${accessToken}`);

      // ASSERT
      expect(profileResponse.status).toBe(200);
      expect(profileResponse.body.id).toBe(user.id);
      expect(profileResponse.body.email).toBe(user.email);
      expect(profileResponse.body.password).toBeUndefined();
    });
  });
});
