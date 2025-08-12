// src/comm/chat/chat.gateway.spec.ts
import { Test, TestingModule } from '@nestjs/testing';
import { ChatGateway } from './chat.gateway';
import { ChatService } from './chat.service';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';
import { AuthenticatedSocket } from 'src/common/interfaces/auth.interface';
import { ForbiddenException, NotFoundException } from '@nestjs/common';
import { Handshake } from 'socket.io/dist/socket-types';
import { DeleteMessageDto } from './dto/delete-message.dto';

jest.mock('src/common/utils/auth.utils');
const mockGetAuthenticatedUser = getAuthenticatedUser as jest.Mock;

const mockAuthUser = { sub: 'user-123', permissions: ['chat:delete:own'] };

const mockChatService = {
  sendMessage: jest.fn(),
  editMessage: jest.fn(),
  deleteMessage: jest.fn(),
  reactToMessage: jest.fn(),
};

const mockIoServer = {
  to: jest.fn().mockReturnThis(),
  emit: jest.fn(),
};

describe('ChatGateway', () => {
  let gateway: ChatGateway;

  const mockHandshake: Handshake = {
    headers: {},
    time: new Date().toUTCString(),
    address: '127.0.0.1',
    xdomain: false,
    secure: false,
    issued: Date.now(),
    url: '/socket.io/',
    query: { sessionId: 'session-abc' },
    auth: {},
  };

  const mockClientSocket: Partial<AuthenticatedSocket> = {
    handshake: mockHandshake,
  };

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        ChatGateway,
        { provide: ChatService, useValue: mockChatService },
      ],
    }).compile();

    gateway = module.get<ChatGateway>(ChatGateway);
    (gateway as any).server = mockIoServer;

    jest.clearAllMocks();
    mockGetAuthenticatedUser.mockReturnValue(mockAuthUser);
  });

  it('should be defined', () => {
    expect(gateway).toBeDefined();
  });

  describe('handleSendMessage', () => {
    const sendMessageDto = { text: 'Hello', idempotencyKey: 'idem-key-1' };

    it('should call chatService.sendMessage and emit to the session room', async () => {
      const createdMessage = { id: 'msg-1', ...sendMessageDto };
      mockChatService.sendMessage.mockResolvedValue(createdMessage);

      const result = await gateway.handleSendMessage(
        sendMessageDto,
        mockClientSocket as AuthenticatedSocket,
      );

      expect(mockChatService.sendMessage).toHaveBeenCalledWith(
        mockAuthUser.sub,
        'session-abc',
        sendMessageDto,
      );
      expect(mockIoServer.to).toHaveBeenCalledWith('session:session-abc');
      expect(mockIoServer.emit).toHaveBeenCalledWith(
        'chat.message.new',
        createdMessage,
      );
      expect(result).toEqual({ success: true, messageId: 'msg-1' });
    });

    it('should return a structured failure object if service throws HttpException', async () => {
      const error = new NotFoundException('Session not found.');
      mockChatService.sendMessage.mockRejectedValue(error);

      const result = await gateway.handleSendMessage(
        sendMessageDto,
        mockClientSocket as AuthenticatedSocket,
      );

      // **FIXED**: Expect the structured error object that the gateway now correctly returns.
      expect(result).toEqual({
        success: false,
        error: {
          message: 'Session not found.',
          statusCode: 404,
        },
      });
      expect(mockIoServer.emit).not.toHaveBeenCalled();
    });
  });

  describe('handleEditMessage', () => {
    const editMessageDto = {
      messageId: 'msg-1',
      newText: 'Updated',
      idempotencyKey: 'idem-key-2',
    };

    it('should call chatService.editMessage and broadcast the update', async () => {
      const editedMessage = { id: 'msg-1', ...editMessageDto };
      mockChatService.editMessage.mockResolvedValue(editedMessage);

      const result = await gateway.handleEditMessage(
        editMessageDto,
        mockClientSocket as AuthenticatedSocket,
      );

      expect(mockChatService.editMessage).toHaveBeenCalledWith(
        mockAuthUser.sub,
        editMessageDto,
      );
      expect(mockIoServer.to).toHaveBeenCalledWith('session:session-abc');
      expect(mockIoServer.emit).toHaveBeenCalledWith(
        'chat.message.updated',
        editedMessage,
      );
      expect(result).toEqual({ success: true, messageId: editedMessage.id });
    });

    it('should return a structured failure for ForbiddenException', async () => {
      const error = new ForbiddenException(
        'You can only edit your own messages.',
      );
      mockChatService.editMessage.mockRejectedValue(error);

      const result = await gateway.handleEditMessage(
        editMessageDto,
        mockClientSocket as AuthenticatedSocket,
      );

      expect(result).toEqual({
        success: false,
        error: {
          message: 'You can only edit your own messages.',
          statusCode: 403,
        },
      });
    });
  });

  describe('handleDeleteMessage', () => {
    const deleteMessageDto: DeleteMessageDto = {
      messageId: 'msg-1',
      idempotencyKey: 'idem-key-3',
    };

    it('should call chatService.deleteMessage and broadcast the deletion', async () => {
      mockChatService.deleteMessage.mockResolvedValue({
        deletedMessageId: 'msg-1',
        sessionId: 'session-abc',
      });

      const result = await gateway.handleDeleteMessage(
        deleteMessageDto,
        mockClientSocket as AuthenticatedSocket,
      );

      // **FIXED**: Expect the full DTO object to be passed to the service.
      expect(mockChatService.deleteMessage).toHaveBeenCalledWith(
        mockAuthUser.sub,
        deleteMessageDto,
        mockAuthUser.permissions,
      );

      expect(mockIoServer.to).toHaveBeenCalledWith('session:session-abc');
      expect(mockIoServer.emit).toHaveBeenCalledWith('chat.message.deleted', {
        messageId: 'msg-1',
      });
      expect(result).toEqual({ success: true, deletedMessageId: 'msg-1' });
    });
  });

  describe('handleReactToMessage', () => {
    const reactDto = {
      messageId: 'msg-1',
      emoji: '👍',
      idempotencyKey: 'idem-key-4',
    };

    it('should call chatService.reactToMessage and broadcast the update', async () => {
      const updatedMessage = {
        id: 'msg-1',
        text: 'Hello',
        reactionsSummary: { '👍': 1 },
      };
      mockChatService.reactToMessage.mockResolvedValue(updatedMessage);

      const result = await gateway.handleReactToMessage(
        reactDto,
        mockClientSocket as AuthenticatedSocket,
      );

      expect(mockChatService.reactToMessage).toHaveBeenCalledWith(
        mockAuthUser.sub,
        reactDto,
      );
      expect(mockIoServer.to).toHaveBeenCalledWith('session:session-abc');
      expect(mockIoServer.emit).toHaveBeenCalledWith(
        'chat.message.updated',
        updatedMessage,
      );
      expect(result).toEqual({ success: true, messageId: 'msg-1' });
    });

    it('should not broadcast if reactToMessage returns null (message deleted)', async () => {
      mockChatService.reactToMessage.mockResolvedValue(null);
      await gateway.handleReactToMessage(
        reactDto,
        mockClientSocket as AuthenticatedSocket,
      );
      expect(mockIoServer.emit).not.toHaveBeenCalled();
    });
  });
});
