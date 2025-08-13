import { Test, TestingModule } from '@nestjs/testing';
import { ValidationGateway } from './validation.gateway';
import { ValidationService } from './validation.service';
import { AuthenticatedSocket } from 'src/common/interfaces/auth.interface';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';
import { Handshake } from 'socket.io/dist/socket-types';
import { ForbiddenException } from '@nestjs/common';
import { ValidationResultDto } from './dto/validation-result.dto';
import { ValidateTicketDto, ValidationType } from './dto/validate-ticket.dto';

jest.mock('src/common/utils/auth.utils');
const mockGetAuthenticatedUser = getAuthenticatedUser as jest.Mock;

const mockValidationService = { validateTicket: jest.fn() };

describe('ValidationGateway', () => {
  let gateway: ValidationGateway;
  let module: TestingModule;

  const mockHandshake: Handshake = {
    headers: {},
    time: '',
    address: '',
    xdomain: false,
    secure: false,
    issued: 0,
    url: '',
    query: { eventId: 'event-123' },
    auth: {},
  };
  const mockClientSocket: Partial<AuthenticatedSocket> = {
    handshake: mockHandshake,
  };

  beforeEach(async () => {
    module = await Test.createTestingModule({
      providers: [
        ValidationGateway,
        { provide: ValidationService, useValue: mockValidationService },
      ],
    }).compile();
    // **FIX**: Pass the class name to module.get()
    gateway = module.get<ValidationGateway>(ValidationGateway);
    jest.clearAllMocks();
  });

  afterAll(async () => {
    await module.close();
  });

  const validateDto: ValidateTicketDto = {
    ticketCode: 'TICKET123',
    validationType: ValidationType.QR_CODE,
    idempotencyKey: 'key-1',
  };

  it('should call the service and return a success response if user has permission', async () => {
    mockGetAuthenticatedUser.mockReturnValue({
      sub: 'staff-1',
      permissions: ['event:validate_tickets'],
    });
    const validationResult: ValidationResultDto = {
      isValid: true,
      ticketCode: 'TICKET123',
      validatedAt: new Date(),
    };
    mockValidationService.validateTicket.mockResolvedValue(validationResult);

    const response = await gateway.handleValidateTicket(
      validateDto,
      mockClientSocket as AuthenticatedSocket,
    );

    expect(mockValidationService.validateTicket).toHaveBeenCalledWith(
      'event-123',
      validateDto,
    );
    expect(response.success).toBe(true);
    if (response.success) {
      expect(response.data.isValid).toBe(true);
    }
  });

  it('should throw ForbiddenException if user lacks permission', async () => {
    mockGetAuthenticatedUser.mockReturnValue({
      sub: 'staff-1',
      permissions: [],
    });

    await expect(
      gateway.handleValidateTicket(
        validateDto,
        mockClientSocket as AuthenticatedSocket,
      ),
    ).rejects.toThrow(ForbiddenException);
  });
});
