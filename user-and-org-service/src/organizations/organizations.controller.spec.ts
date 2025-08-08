//src/organizations/organizations.controller.spec.ts
import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication, ValidationPipe } from '@nestjs/common';
import * as request from 'supertest';
import { AppModule } from '../app.module';
import { PrismaService } from '../prisma.service';
import * as bcrypt from 'bcrypt';
import { AuthService } from '../auth/auth.service';

describe('OrganizationsController (Integration)', () => {
  let app: INestApplication;
  let prisma: PrismaService;
  let authService: AuthService;
  let accessToken: string;
  let userId: string;
  let orgId: string;

  beforeAll(async () => {
    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();

    app = moduleFixture.createNestApplication();
    app.useGlobalPipes(new ValidationPipe());
    await app.init();

    prisma = app.get<PrismaService>(PrismaService);
    authService = app.get<AuthService>(AuthService);

    // Clean and seed the database once for all tests in this file
    await prisma.membership.deleteMany({});
    await prisma.organization.deleteMany({});
    await prisma.user.deleteMany({});
    await prisma.role.deleteMany({});
    await prisma.role.createMany({
      data: [
        { name: 'OWNER', isSystemRole: true },
        { name: 'ADMIN', isSystemRole: true },
        { name: 'MEMBER', isSystemRole: true },
      ],
    });
  });

  // Create a default user and organization to use in the tests
  beforeEach(async () => {
    const hashedPassword = await bcrypt.hash('password123', 10);
    const user = await prisma.user.create({
      data: {
        email: 'org-owner@example.com',
        password: hashedPassword,
        first_name: 'Org',
        last_name: 'Owner',
      },
    });
    const org = await prisma.organization.create({
      data: { name: 'Test Org' },
    });
    const ownerRole = await prisma.role.findFirst({ where: { name: 'OWNER' } });
    await prisma.membership.create({
      data: { userId: user.id, organizationId: org.id, roleId: ownerRole!.id },
    });

    // Log in the user to get a valid token for authenticated requests
    const tokens = await authService.login({
      email: user.email,
      password: 'password123',
    });
    if ('access_token' in tokens) {
      accessToken = tokens.access_token;
    }

    userId = user.id;
    orgId = org.id;
  });

  afterEach(async () => {
    await prisma.membership.deleteMany({});
    await prisma.organization.deleteMany({});
    await prisma.user.deleteMany({});
  });

  afterAll(async () => {
    await app.close();
  });

  describe('GET /organizations/:orgId/members', () => {
    it('should list all members of an organization', async () => {
      // ACT
      const response = await request(app.getHttpServer())
        .get(`/organizations/${orgId}/members`)
        .set('Authorization', `Bearer ${accessToken}`);

      // ASSERT
      expect(response.status).toBe(200);
      expect(response.body.membershipRecord).toHaveLength(1);
      expect(response.body.membershipRecord[0].user.email).toBe(
        'org-owner@example.com',
      );
    });
  });

  describe('POST /organizations', () => {
    it('should allow an authenticated user to create a new organization', async () => {
      // ARRANGE
      const newOrgData = {
        organization_name: 'My New Venture',
      };

      // ACT
      const response = await request(app.getHttpServer())
        .post('/organizations')
        .set('Authorization', `Bearer ${accessToken}`)
        .send(newOrgData);

      // ASSERT
      expect(response.status).toBe(201);
      expect(response.body.organization.name).toBe(
        newOrgData.organization_name,
      );

      // Verify the user is the OWNER of the new org in the database
      const newOrgId = response.body.organization.id;
      const newMembership = await prisma.membership.findFirst({
        where: { userId: userId, organizationId: newOrgId },
        include: { role: true },
      });
      expect(newMembership?.role.name).toBe('OWNER');
    });
  });
});
