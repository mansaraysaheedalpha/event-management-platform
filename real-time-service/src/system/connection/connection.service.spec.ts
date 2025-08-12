import { Test, TestingModule } from '@nestjs/testing';
import { ConnectionService, ReconnectReason } from './connection.service';

describe('ConnectionService', () => {
  let service: ConnectionService;

  beforeAll(() => {
    jest.useFakeTimers();
  });

  afterAll(() => {
    jest.useRealTimers();
  });

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [ConnectionService],
    }).compile();
    service = module.get<ConnectionService>(ConnectionService);
  });

  it('startHeartbeat should emit a heartbeat event every 30 seconds', () => {
    const mockClient = { id: 'client-1', emit: jest.fn() } as any;

    service.startHeartbeat(mockClient);

    // Fast-forward time by 30 seconds
    jest.advanceTimersByTime(30000);
    expect(mockClient.emit).toHaveBeenCalledWith(
      'heartbeat',
      expect.any(Object),
    );
    expect(mockClient.emit).toHaveBeenCalledTimes(1);

    // Fast-forward another 30 seconds
    jest.advanceTimersByTime(30000);
    expect(mockClient.emit).toHaveBeenCalledTimes(2);

    service.stopHeartbeat('client-1');
  });

  it('stopHeartbeat should clear the interval timer', () => {
    const clearIntervalSpy = jest.spyOn(global, 'clearInterval');
    const mockClient = { id: 'client-1', emit: jest.fn() } as any;

    service.startHeartbeat(mockClient);
    service.stopHeartbeat('client-1');

    expect(clearIntervalSpy).toHaveBeenCalled();
  });

  it('requestReconnect should emit reconnectRequired and disconnect the client', () => {
    const mockClient = {
      id: 'client-1',
      emit: jest.fn(),
      disconnect: jest.fn(),
    } as any;

    service.requestReconnect(mockClient, ReconnectReason.NEW_VERSION_DEPLOYED);

    expect(mockClient.emit).toHaveBeenCalledWith(
      'reconnectRequired',
      expect.any(Object),
    );
    expect(mockClient.disconnect).toHaveBeenCalledWith(true);
  });
});
