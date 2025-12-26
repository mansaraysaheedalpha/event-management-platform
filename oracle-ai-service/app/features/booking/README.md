# Booking Call Feature

## Overview
The Booking Call feature allows users to schedule calls with speakers and experts through the Event Management Platform. This feature provides a complete booking experience with confirmation details, meeting links, and cost estimates.

## API Endpoint

### POST /oracle/booking/call

Books a call with a speaker or expert.

**Request Body:**
```json
{
  "user_id": "user_123",
  "speaker_id": "spk_1",
  "event_id": "evt_456",
  "preferred_date": "2025-11-15T14:00:00Z",
  "duration_minutes": 60,
  "topic": "AI Implementation Strategy",
  "notes": "Optional additional notes"
}
```

**Response (200 OK):**
```json
{
  "booking_id": "BK-20251026115307-WVXM2C",
  "status": "confirmed",
  "speaker_id": "spk_1",
  "speaker_name": "Dr. Eva Rostova",
  "scheduled_time": "2025-11-15T14:00:00Z",
  "duration_minutes": 60,
  "meeting_link": "https://meet.example.com/call/BK-20251026115307-WVXM2C",
  "confirmation_code": "W60DQLIO",
  "estimated_cost": 500.00,
  "message": "Your call with Dr. Eva Rostova has been confirmed! You will receive a confirmation email shortly."
}
```

## Features

- **Automatic Booking Confirmation**: Instantly confirms bookings with unique booking IDs
- **Meeting Link Generation**: Automatically generates video meeting links
- **Cost Calculation**: Calculates estimated costs based on speaker rates and duration
- **Confirmation Codes**: Provides unique confirmation codes for easy reference
- **Input Validation**: Validates all required fields with proper error messages

## Available Speakers

The system currently has the following speakers available:

1. **Dr. Eva Rostova** (spk_1)
   - Expertise: AI, Machine Learning
   - Rate: $500/hour

2. **John CEO** (spk_2)
   - Expertise: AI, Business Strategy
   - Rate: $1000/hour

3. **DevOps Dan** (spk_3)
   - Expertise: DevOps, Infrastructure
   - Rate: $300/hour

4. **Anna Coder** (spk_4)
   - Expertise: AI, Software Development
   - Rate: $400/hour

## Usage Examples

### Example 1: Book a 60-minute AI Strategy Call
```bash
curl -X POST http://localhost:8000/oracle/booking/call \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_123",
    "speaker_id": "spk_1",
    "event_id": "evt_456",
    "preferred_date": "2025-11-15T14:00:00Z",
    "duration_minutes": 60,
    "topic": "AI Implementation Strategy"
  }'
```

### Example 2: Book a 30-minute DevOps Consultation
```bash
curl -X POST http://localhost:8000/oracle/booking/call \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_456",
    "speaker_id": "spk_3",
    "event_id": "evt_789",
    "preferred_date": "2025-11-20T10:00:00Z",
    "duration_minutes": 30,
    "topic": "CI/CD Pipeline Optimization"
  }'
```

## Integration with Speaker Recommendations

The booking feature is designed to work seamlessly with the speaker recommendation endpoint:

1. Use `POST /oracle/recommendations/speakers` to get speaker suggestions
2. Review the recommendations and select a speaker
3. Use `POST /oracle/booking/call` to book a call with the selected speaker

## Testing

The feature includes comprehensive test coverage:

### Unit Tests
- `tests/features/test_booking_service.py` - Tests for booking service logic
  - Test booking confirmation generation
  - Test cost calculation
  - Test handling of unknown speakers

### API Tests
- `tests/api/test_booking_api.py` - End-to-end API tests
  - Test successful booking flow
  - Test input validation
  - Test with minimal required data

Run tests with:
```bash
pytest tests/features/test_booking_service.py -v
pytest tests/api/test_booking_api.py -v
```

## Future Enhancements

The current implementation is a foundation that can be enhanced with:

- Real calendar integration (Google Calendar, Outlook, etc.)
- Email notifications for confirmations
- Payment processing integration
- Speaker availability checking
- Booking cancellation and rescheduling
- Multi-timezone support
- Recurring meeting support
- Reminder notifications

## Technical Details

### File Structure
```
app/features/booking/
├── __init__.py          # Module initialization
├── router.py            # FastAPI router with endpoint definition
├── schemas.py           # Pydantic models for request/response
└── service.py           # Business logic for booking
```

### Dependencies
- FastAPI for API framework
- Pydantic for data validation
- Standard Python libraries (datetime, random, string)

## API Documentation

The booking endpoint is fully documented in the OpenAPI specification. Access the interactive API documentation at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
