import { Test, TestingModule } from '@nestjs/testing';
import { StreamingController } from './streaming.controller';
import { StreamingGateway } from './streaming.gateway';
import { SubtitleChunkDto } from './dto/subtitle-chunk.dto';
import { InternalApiKeyGuard } from 'src/common/guards/internal-api-key.guard';

// Mock the gateway since the controller depends on it
const mockStreamingGateway = {
  broadcastSubtitleChunk: jest.fn(),
};

describe('StreamingController', () => {
  let controller: StreamingController;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      controllers: [StreamingController],
      providers: [
        { provide: StreamingGateway, useValue: mockStreamingGateway },
      ],
    })
      // Mock the guard to always allow access in tests
      .overrideGuard(InternalApiKeyGuard)
      .useValue({ canActivate: () => true })
      .compile();

    controller = module.get<StreamingController>(StreamingController);
    jest.clearAllMocks();
  });

  it('should call the gateway to broadcast a subtitle chunk and return "accepted"', () => {
    const subtitleDto: SubtitleChunkDto = {
      sessionId: 'session-1',
      text: 'Hello world',
      language: 'en',
      timestamp: new Date().toISOString(),
      duration: 1000,
    };

    const response = controller.handleSubtitleChunk(subtitleDto);

    expect(mockStreamingGateway.broadcastSubtitleChunk).toHaveBeenCalledWith(
      subtitleDto,
    );
    expect(response).toEqual({ status: 'accepted' });
  });
});
