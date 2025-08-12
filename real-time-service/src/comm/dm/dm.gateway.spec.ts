import { Test, TestingModule } from '@nestjs/testing';
import { DmGateway } from './dm.gateway';
import { DmService } from './dm.service';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';
import { AuthenticatedSocket } from 'src/common/interfaces/auth.interface';
import { Handshake } from 'socket.io/dist/socket-types';
import { EditDmDto } from './dto/edit-dm.dto';
import { DeleteDmDto } from './dto/delete-dm.dto';
import { PrismaService } from 'src/prisma.service'; // Import PrismaService

jest.mock('src/common/utils/auth.utils');
const mockGetAuthenticatedUser = getAuthenticatedUser as jest.Mock;

const mockAuthUser = { sub: 'user-1' };
const mockRecipientId = 'user-2';

const mockDmService = {
  sendMessage: jest.fn(),
  markAsDelivered: jest.fn(),
  markAsRead: jest.fn(),
  editMessage: jest.fn(),
  deleteMessage: jest.fn(),
};

// **FIX**: We need a mock for PrismaService, even if it's empty,
// because the DmGateway constructor requires it.
const mockPrismaService = {
  conversation: {
    findUnique: jest.fn(),
  },
};

const mockIoServer = {
  to: jest.fn().mockReturnThis(),
  emit: jest.fn(),
};

describe('DmGateway', () => {
  let gateway: DmGateway;

  const mockHandshake: Handshake = {
    headers: {},
    time: new Date().toUTCString(),
    address: '127.0.0.1',
    xdomain: false,
    secure: false,
    issued: Date.now(),
    url: '/socket.io/',
    query: {},
    auth: {},
  };
  const mockClientSocket: Partial<AuthenticatedSocket> = {
    handshake: mockHandshake,
  };

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        DmGateway,
        { provide: DmService, useValue: mockDmService },
        // **FIX**: Add the PrismaService provider back to the testing module.
        { provide: PrismaService, useValue: mockPrismaService },
      ],
    }).compile();

    gateway = module.get<DmGateway>(DmGateway);
    (gateway as any).server = mockIoServer;

    jest.clearAllMocks();
    mockGetAuthenticatedUser.mockReturnValue(mockAuthUser);
  });

  it('should be defined', () => {
    expect(gateway).toBeDefined();
  });

  describe('handleSendMessage', () => {
    const sendDmDto = {
      recipientId: mockRecipientId,
      text: 'Hello!',
      idempotencyKey: 'key-1',
    };
    const newMessage = { id: 'dm-1', timestamp: new Date(), ...sendDmDto };

    it('should emit "dm.new" to both sender and recipient rooms', async () => {
      mockDmService.sendMessage.mockResolvedValue(newMessage);
      await gateway.handleSendMessage(
        sendDmDto,
        mockClientSocket as AuthenticatedSocket,
      );
      expect(mockDmService.sendMessage).toHaveBeenCalledWith(
        mockAuthUser.sub,
        sendDmDto,
      );
      expect(mockIoServer.to).toHaveBeenCalledWith(`user:${mockAuthUser.sub}`);
      expect(mockIoServer.to).toHaveBeenCalledWith(`user:${mockRecipientId}`);
      expect(mockIoServer.emit).toHaveBeenCalledWith('dm.new', newMessage);
      expect(mockIoServer.emit).toHaveBeenCalledTimes(2);
    });
  });

  describe('handleDeliveryReceipt', () => {
    const deliveryDto = { messageId: 'dm-1', idempotencyKey: 'key-2' };
    const updatedMessage = {
      id: 'dm-1',
      senderId: 'original-sender',
      isDelivered: true,
      deliveredAt: new Date(),
      conversationId: 'c1',
    };

    it('should emit "dm.delivery_update" to the original sender', async () => {
      mockDmService.markAsDelivered.mockResolvedValue(updatedMessage);
      await gateway.handleDeliveryReceipt(
        deliveryDto,
        mockClientSocket as AuthenticatedSocket,
      );
      expect(mockDmService.markAsDelivered).toHaveBeenCalledWith(
        mockAuthUser.sub,
        deliveryDto,
      );
      expect(mockIoServer.to).toHaveBeenCalledWith(
        `user:${updatedMessage.senderId}`,
      );
      expect(mockIoServer.emit).toHaveBeenCalledWith(
        'dm.delivery_update',
        expect.any(Object),
      );
    });

    it('should do nothing if service returns null', async () => {
      mockDmService.markAsDelivered.mockResolvedValue(null);
      await gateway.handleDeliveryReceipt(
        deliveryDto,
        mockClientSocket as AuthenticatedSocket,
      );
      expect(mockIoServer.emit).not.toHaveBeenCalled();
    });
  });

  describe('handleEditMessage', () => {
    const editDto: EditDmDto = {
      messageId: 'dm-1',
      newText: 'Hi',
      idempotencyKey: 'key-edit',
    };
    const editResult = {
      updatedMessage: { id: 'dm-1', conversationId: 'convo-1' },
      participantIds: ['user-1', 'user-2'],
    };

    it('should emit "dm.message.updated" to all participants using IDs from the service', async () => {
      mockDmService.editMessage.mockResolvedValue(editResult);
      await gateway.handleEditMessage(
        editDto,
        mockClientSocket as AuthenticatedSocket,
      );
      expect(mockDmService.editMessage).toHaveBeenCalledWith(
        mockAuthUser.sub,
        editDto,
      );
      expect(mockIoServer.to).toHaveBeenCalledWith('user:user-1');
      expect(mockIoServer.to).toHaveBeenCalledWith('user:user-2');
      expect(mockIoServer.emit).toHaveBeenCalledWith(
        'dm.message.updated',
        editResult.updatedMessage,
      );
      expect(mockIoServer.emit).toHaveBeenCalledTimes(2);
    });
  });

  describe('handleDeleteMessage', () => {
    const deleteDto: DeleteDmDto = {
      messageId: 'dm-1',
      idempotencyKey: 'key-delete',
    };
    const deleteResult = {
      deletedMessageId: 'dm-1',
      conversation: {
        participants: [{ userId: 'user-1' }, { userId: 'user-2' }],
      },
    };

    it('should emit "dm.message.deleted" to all participants', async () => {
      mockDmService.deleteMessage.mockResolvedValue(deleteResult);
      await gateway.handleDeleteMessage(
        deleteDto,
        mockClientSocket as AuthenticatedSocket,
      );
      expect(mockDmService.deleteMessage).toHaveBeenCalledWith(
        mockAuthUser.sub,
        deleteDto,
      );
      expect(mockIoServer.to).toHaveBeenCalledWith('user:user-1');
      expect(mockIoServer.to).toHaveBeenCalledWith('user:user-2');
      expect(mockIoServer.emit).toHaveBeenCalledWith('dm.message.deleted', {
        messageId: 'dm-1',
      });
      expect(mockIoServer.emit).toHaveBeenCalledTimes(2);
    });
  });
});
