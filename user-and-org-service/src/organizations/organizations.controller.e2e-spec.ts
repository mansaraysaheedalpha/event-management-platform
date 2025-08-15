//src/organizations/organizations.controller.e2espec.ts
import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication, ValidationPipe } from '@nestjs/common';
import * as request from 'supertest';
import { AppModule } from '../app.module';
import { PrismaService } from '../prisma.service';
import { AuthService } from '../auth/auth.service';
import * as bcrypt from 'bcrypt';

describe('OrganizationsController (E2E)', () => {
  let app: INestApplication;
  let prisma: PrismaService;
  let authService: AuthService;

  let ownerToken: string;
  let adminToken: string;
  let memberToken: string;
  let testOrgId: string;
  let memberUserId: string;

  beforeAll(async () => {
    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();

    app = moduleFixture.createNestApplication();
    prisma = app.get<PrismaService>(PrismaService);
    authService = app.get<AuthService>(AuthService);

    app.useGlobalPipes(new ValidationPipe());
    await app.init();

    // --- SEED DATABASE FOR TESTS ---
    await prisma.membership.deleteMany();
    await prisma.user.deleteMany();
    await prisma.role.deleteMany();
    await prisma.organization.deleteMany();

    const org = await prisma.organization.create({ data: { name: 'E2E Org' } });
    testOrgId = org.id;

    // Create roles for the org
    const ownerRole = await prisma.role.create({
      data: { name: 'OWNER', organizationId: org.id },
    });
    const adminRole = await prisma.role.create({
      data: { name: 'ADMIN', organizationId: org.id },
    });
    const memberRole = await prisma.role.create({
      data: { name: 'MEMBER', organizationId: org.id },
    });

    // Create users
    const hashedPassword = await bcrypt.hash('password123', 10);
    const owner = await prisma.user.create({
      data: { email: 'owner@e2e.com', password: hashedPassword },
    });
    const admin = await prisma.user.create({
      data: { email: 'admin@e2e.com', password: hashedPassword },
    });
    const member = await prisma.user.create({
      data: { email: 'member@e2e.com', password: hashedPassword },
    });
    memberUserId = member.id;

    // Create memberships
    const ownerMembership = await prisma.membership.create({
      data: {
        userId: owner.id,
        organizationId: org.id,
        roleId: ownerRole.id,
        role: { connect: { id: ownerRole.id } },
      },
    });
    const adminMembership = await prisma.membership.create({
      data: {
        userId: admin.id,
        organizationId: org.id,
        roleId: adminRole.id,
        role: { connect: { id: adminRole.id } },
      },
    });
    await prisma.membership.create({
      data: {
        userId: member.id,
        organizationId: org.id,
        roleId: memberRole.id,
        role: { connect: { id: memberRole.id } },
      },
    });

    // Get tokens for each user role
    ownerToken = (
      await authService.getTokensForUser(owner, {
        ...ownerMembership,
        role: ownerRole,
      })
    ).access_token;
    adminToken = (
      await authService.getTokensForUser(admin, {
        ...adminMembership,
        role: adminRole,
      })
    ).access_token;
    memberToken = (
      await authService.getTokensForUser(member, {
        ...adminMembership,
        role: memberRole,
      })
    ).access_token;
  });

  afterAll(async () => {
    await app.close();
  });

  describe('/organizations/:orgId/members (GET)', () => {
    it('should allow a MEMBER to list members', () => {
      return request(app.getHttpServer())
        .get(`/organizations/${testOrgId}/members`)
        .set('Authorization', `Bearer ${memberToken}`)
        .expect(200);
    });
  });

  describe('/organizations/:orgId/members/:memberId (DELETE)', () => {
    it('should forbid a MEMBER from removing another member', () => {
      return request(app.getHttpServer())
        .delete(`/organizations/${testOrgId}/members/${memberUserId}`)
        .set('Authorization', `Bearer ${memberToken}`)
        .expect(403);
    });

    it('should allow an ADMIN to remove another member', () => {
      return request(app.getHttpServer())
        .delete(`/organizations/${testOrgId}/members/${memberUserId}`)
        .set('Authorization', `Bearer ${adminToken}`)
        .expect(204);
    });
  });
});