import {
  Injectable,
  ConflictException,
  NotFoundException,
  UnauthorizedException,
} from '@nestjs/common';
import { RegisterUserDto } from './dto/register-user.dto';
import { PrismaService } from 'src/prisma.service';
import * as bcrypt from 'bcrypt';
import { UpdateProfileDTO } from './dto/update-profile.dto';
import { MailerService } from '@nestjs-modules/mailer';
import { JwtService } from '@nestjs/jwt';
import { ConfigService } from '@nestjs/config';
import { randomBytes } from 'crypto';
import { User } from '@prisma/client';

@Injectable()
export class UsersService {
  constructor(
    private prisma: PrismaService,
    private mailerService: MailerService,
    private jwtService: JwtService,
    private configService: ConfigService,
  ) {}
  async create(registerUserDto: RegisterUserDto) {
    console.log('--Inside of UsersService--');
    //  Check if user exists
    const existingUser = await this.prisma.user.findUnique({
      where: { email: registerUserDto.email },
    });

    if (existingUser) {
      console.log('User email exists already');
      throw new ConflictException('User with this email already exists');
    }
    console.log('User email is unique proceeding..');
    // : Password hashing
    const saltRounds = await bcrypt.genSalt(10);
    const hashedPassword = await bcrypt.hash(
      registerUserDto.password,
      saltRounds,
    );
    console.log('Hashed password already');

    //Use prisma transaction to create User, Organization and Membership
    // ensures that all three operations succeed or none of them do

    const result = await this.prisma.$transaction(async (tx) => {
      // Create the organization record in the database
      const newOrg = await tx.organization.create({
        data: {
          name: registerUserDto.organization_name,
        },
      });
      console.log('Organization created, ', newOrg.id);

      // Create user record in the database
      const newUser = await tx.user.create({
        data: {
          email: registerUserDto.email,
          first_name: registerUserDto.first_name,
          last_name: registerUserDto.last_name,
          password: hashedPassword,
        },
      });
      console.log('User created, ', newUser.id);

      // Create the membership between the User and the organization
      await tx.membership.create({
        data: {
          userId: newUser.id,
          organizationId: newOrg.id,
          role: 'OWNER',
        },
      });
      console.log('Membership Link created: ');

      // Remove password before returning the data
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      const { password, ...newUserToReturn } = newUser;

      return { user: newUserToReturn, organization: newOrg };
    });

    return result;
  }

  async findOne(id: string) {
    const existingUser = await this.prisma.user.findUnique({
      where: { id: id },
    });

    if (!existingUser) {
      throw new NotFoundException(`User with id ${id} not found`);
    }

    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const { password, hashedRefreshToken, ...userToReturn } = existingUser;

    return userToReturn;
  }

  async updateProfile(userId: string, updateProfileDto: UpdateProfileDTO) {
    await this.prisma.user.update({
      where: { id: userId },
      data: {
        ...updateProfileDto,
      },
    });
    return { message: 'User profile updated successfully' };
  }

  async changePassword(
    userId: string,
    currentPassword: string,
    newPassword: string,
  ) {
    const userExists = await this.prisma.user.findUniqueOrThrow({
      where: { id: userId },
    });

    const isPasswordMatch = await bcrypt.compare(
      currentPassword,
      userExists.password,
    );

    if (!isPasswordMatch) {
      throw new UnauthorizedException('wrong/invalid password');
    }

    const salt = await bcrypt.genSalt(10);
    const newHashedPassword = await bcrypt.hash(newPassword, salt);

    await this.prisma.user.update({
      where: { id: userId },
      data: {
        password: newHashedPassword,
      },
    });

    return { message: 'Successfully changed password' };
  }

  // STEP 1: User requests a change.
  async requestEmailChange(userId: string, newEmail: string) {
    // A. Get the user's current email
    const user = await this.prisma.user.findUniqueOrThrow({
      where: { id: userId },
    });
    const oldEmail = user.email;

    // B. Create a secure, single-use token
    const rawToken = randomBytes(32).toString('hex');
    const hashedToken = await bcrypt.hash(rawToken, 10);
    const expiresAt = new Date(Date.now() + 15 * 60 * 1000); // 15 min expiry

    // C. Store the token and the NEW email temporarily on the user's record
    await this.prisma.user.update({
      where: { id: userId },
      data: {
        pendingEmail: newEmail,
        emailChangeToken: hashedToken,
        emailChangeTokenExpiresAt: expiresAt,
      },
    });

    // D. Send a verification email to the OLD address
    const verificationUrl = `http://localhost:3001/users/email-change/verify-old/${rawToken}`;
    await this.mailerService.sendMail({
      to: oldEmail,
      subject: 'Confirm Your Email Change Request',
      html: `<p>A request was made to change your email to ${newEmail}. Please click <a href="${verificationUrl}">here</a> to approve this change. This link expires in 15 minutes.</p>`,
    });

    return {
      message: 'Verification email sent to your current email address.',
    };
  }

  // STEP 2: User clicks the link in the OLD email.
  async confirmOldEmail(token: string) {
    // This is a more complex flow, so let's find the user in a more robust way
    const user = await this.findUserByEmailChangeToken(token);

    if (!user || !user.pendingEmail) {
      throw new UnauthorizedException('Invalid or expired token.');
    }

    // A. Generate a SECOND token for the NEW email address
    const finalRawToken = randomBytes(32).toString('hex');
    const finalHashedToken = await bcrypt.hash(finalRawToken, 10);

    // B. Update the token in the database
    await this.prisma.user.update({
      where: { id: user.id },
      data: {
        emailChangeToken: finalHashedToken,
        emailChangeTokenExpiresAt: new Date(Date.now() + 15 * 60 * 1000), // Reset expiry
      },
    });

    // C. Send the FINAL confirmation email to the NEW address
    const finalUrl = `http://localhost:3001/users/email-change/finalize/${finalRawToken}`;
    await this.mailerService.sendMail({
      to: user.pendingEmail,
      subject: 'Finalize Your Email Address Change',
      html: `<p>Please click this final link to make ${user.pendingEmail} your new login email. This link expires in 15 minutes.</p><p><a href="${finalUrl}">Finalize Change</a></p>`,
    });

    return {
      message:
        'Approval successful. A final confirmation link has been sent to your new email address.',
    };
  }

  // STEP 3: User clicks the link in the NEW email.
  async finalizeEmailChange(token: string) {
    const user = await this.findUserByEmailChangeToken(token);

    if (!user || !user.pendingEmail) {
      throw new UnauthorizedException('Invalid or expired token.');
    }

    // A. Final update: change the email and clear all temp fields
    await this.prisma.user.update({
      where: { id: user.id },
      data: {
        email: user.pendingEmail,
        pendingEmail: null,
        emailChangeToken: null,
        emailChangeTokenExpiresAt: null,
      },
    });

    return { message: 'Your email has been successfully updated.' };
  }

  // Helper method to reliably find a user by their token
  private async findUserByEmailChangeToken(
    token: string,
  ): Promise<User | null> {
    const unexpiredUsers = await this.prisma.user.findMany({
      where: { emailChangeTokenExpiresAt: { gte: new Date() } },
    });

    for (const user of unexpiredUsers) {
      if (user.emailChangeToken) {
        const isMatch = await bcrypt.compare(token, user.emailChangeToken);
        if (isMatch) return user;
      }
    }
    return null;
  }

  async findUserForInternal(userId: string) {
    const user = await this.prisma.user.findUnique({
      where: { id: userId },
      select: {
        id: true,
        email: true,
        first_name: true,
        last_name: true,
      },
    });

    if (!user) {
      throw new NotFoundException('User not found.');
    }
    return user;
  }
}
