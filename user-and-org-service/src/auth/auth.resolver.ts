// src/auth/auth.resolver.ts
import { Resolver, Mutation, Args, ID, Context } from '@nestjs/graphql';
import { AuthService } from './auth.service';
import { UsersService } from '../users/users.service';
import { AuthPayload, LoginPayload } from './gql_types/auth.types';
import {
  LoginInput,
  RegisterUserInput,
  RegisterAttendeeInput,
  Login2FAInput,
  RequestResetInput,
  PerformResetInput,
} from './gql_types/auth.inputs';
import {
  NotFoundException,
  UnauthorizedException,
  UseGuards,
} from '@nestjs/common';
import { Query } from '@nestjs/graphql';
import { GqlThrottlerGuard } from './guards/gql-throttler.guard';
import { GqlAuthGuard } from './guards/gql-auth.guard';
import { CsrfGuard } from '../common/csrf/csrf.guard';
import { Response } from 'express';
import { GqlRefreshTokenGuard } from './guards/gql-refresh-token.guard';

@Resolver()
export class AuthResolver {
  constructor(
    private authService: AuthService,
    private usersService: UsersService,
  ) {}

  @Mutation(() => LoginPayload)
  @UseGuards(GqlThrottlerGuard)
  async login(
    @Args('input') loginInput: LoginInput,
    @Context() context: { res: Response },
  ): Promise<LoginPayload> {
    const loginResult = await this.authService.login(loginInput);

    if ('onboardingToken' in loginResult) {
      return {
        onboardingToken: loginResult.onboardingToken,
        user: loginResult.user,
        requires2FA: false,
      };
    }

    if ('requires2FA' in loginResult) {
      return {
        requires2FA: true,
        userIdFor2FA: loginResult.userId,
      };
    }

    // Handle attendee login (isAttendee flag indicates attendee response)
    if ('isAttendee' in loginResult && loginResult.isAttendee) {
      context.res.cookie('refresh_token', loginResult.refresh_token, {
        httpOnly: true,
        secure: process.env.NODE_ENV !== 'development',
        sameSite: 'strict',
        maxAge: 7 * 24 * 60 * 60 * 1000,
      });

      const user = await this.usersService.findOneByEmail(loginInput.email);
      return {
        token: loginResult.access_token,
        user,
        requires2FA: false,
        isAttendee: true,
      };
    }

    // Handle organizer login (has access_token but no isAttendee flag)
    if ('access_token' in loginResult) {
      context.res.cookie('refresh_token', loginResult.refresh_token, {
        httpOnly: true,
        secure: process.env.NODE_ENV !== 'development',
        sameSite: 'strict',
        maxAge: 7 * 24 * 60 * 60 * 1000,
      });

      const user = await this.usersService.findOneByEmail(loginInput.email);
      return {
        token: loginResult.access_token,
        user,
        requires2FA: false,
      };
    }

    throw new UnauthorizedException('Could not process login request.');
  }
  
  @Mutation(() => AuthPayload)
  async login2FA(
    @Args('input') login2FAInput: Login2FAInput,
    @Context() context: { res: Response }, // <-- ADD THIS
  ): Promise<AuthPayload> {
    const { userId, code } = login2FAInput;
    const tokens = await this.authService.login2FA(userId, code);

    // --- ADD THIS BLOCK TO SET THE COOKIE ---
    context.res.cookie('refresh_token', tokens.refresh_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV !== 'development',
      sameSite: 'strict',
      maxAge: 7 * 24 * 60 * 60 * 1000, // 7 days
    });
    // -----------------------------------------

    const user = await this.usersService.findOne(userId);
    if (!user) {
      throw new NotFoundException('User not found after 2FA verification.');
    }

    return { token: tokens.access_token, user };
  }

  @Mutation(() => AuthPayload) // Registration doesn't involve 2FA, so the original payload is fine
  async registerUser(
    @Args('input') registerUserInput: RegisterUserInput,
  ): Promise<AuthPayload> {
    // 1. Create the user using the existing service
    const { user: newUser } = await this.usersService.create(registerUserInput);

    // 2. Log the new user in to get a token
    const loginResult = await this.authService.login({
      email: registerUserInput.email,
      password: registerUserInput.password,
    });

    if ('access_token' in loginResult) {
      // The user object from the create step is already what we need.
      return { token: loginResult.access_token, user: newUser };
    }

    throw new Error('Registration succeeded but automatic login failed.');
  }

  /**
   * Register a new attendee user.
   * Attendees don't need organizations - returns regular token immediately.
   */
  @Mutation(() => AuthPayload)
  async registerAttendee(
    @Args('input') input: RegisterAttendeeInput,
    @Context() context: { res: Response },
  ): Promise<AuthPayload> {
    const { user, tokens } = await this.authService.registerAttendee({
      email: input.email,
      password: input.password,
      first_name: input.first_name,
      last_name: input.last_name,
    });

    // Set the refresh token cookie
    context.res.cookie('refresh_token', tokens.refresh_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV !== 'development',
      sameSite: 'strict',
      maxAge: 7 * 24 * 60 * 60 * 1000,
    });

    return { token: tokens.access_token, user };
  }

  @Mutation(() => Boolean)
  @UseGuards(CsrfGuard, GqlAuthGuard)
  async logout(
    @Context() context: { req: { user: { sub: string } }; res: Response },
  ): Promise<boolean> {
    const userId = context.req.user.sub;
    await this.authService.logout(userId); // Invalidate token in DB

    // Clear the cookie on the client
    context.res.clearCookie('refresh_token');

    return true;
  }

  @Mutation(() => String)
  async requestPasswordReset(
    @Args('input') requestResetInput: RequestResetInput,
  ): Promise<string> {
    const { message } = await this.authService.handlePasswordResetRequest(
      requestResetInput.email,
    );
    return message;
  }

  @Mutation(() => String)
  async performPasswordReset(
    @Args('input') performResetInput: PerformResetInput,
  ): Promise<string> {
    const { message } = await this.authService.performPasswordReset(
      performResetInput.resetToken,
      performResetInput.newPassword,
    );
    return message;
  }

  @Mutation(() => AuthPayload)
  @UseGuards(CsrfGuard, GqlAuthGuard)
  async switchOrganization(
    @Args('organizationId', { type: () => ID }) organizationId: string,
    @Context() context: { req: { user: { sub: string } } },
  ): Promise<AuthPayload> {
    const userId = context.req.user.sub;
    const { access_token } = await this.authService.switchOrganization(
      userId,
      organizationId,
    );

    // We need the user object to return the full payload
    const user = await this.usersService.findOne(userId);

    return { token: access_token, user };
  }

  @Mutation(() => AuthPayload)
  @UseGuards(CsrfGuard, GqlRefreshTokenGuard)
  async refreshToken(
    @Context() context: { req: { user: any }; res: Response },
  ): Promise<AuthPayload> {
    const { sub: userId, refreshToken } = context.req.user;

    const newTokens = await this.authService.refreshTokenService(
      userId,
      refreshToken,
    );

    context.res.cookie('refresh_token', newTokens.refresh_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV !== 'development',
      sameSite: 'strict',
      maxAge: 7 * 24 * 60 * 60 * 1000,
    });

    const user = await this.usersService.findOne(userId);
    return { token: newTokens.access_token, user };
  }

  @Query(() => String)
  sayHello(): string {
    return 'Hello World! GraphQL server is running.';
  }
}
