# Calendly combine [WIP]

## Initial idea

A simple app in which you paste a bunch of different calendly or google calendar share links, and it generates a new calendly with only the overlapping times, or even autofills a lettucemeet

## Folder structure

```text
calendly_combine/
├── core/
│   ├── __init__.py
│   ├── models.py
│   └── overlap_engine.py
├── adapters/
│   ├── __init__.py
│   ├── calendly.py
│   ├── google_calendar.py
│   └── output/
│       ├── __init__.py
│       └── link_generator.py
├── api/
│   ├── __init__.py
│   └── main.py
├── tests/
│   ├── __init__.py
│   ├── test_models.py
│   ├── test_overlap_engine.py
│   ├── test_adapters.py
│   └── test_api.py
├── requirements.txt
└── Dockerfile
```

## Testing Script

Run this from the project root directory

```bash
$$ python -m pytest tests/test_models.py
```

## Calendly adapter implementation notes

This implementation:

Creates a robust adapter with proper exception handling and logging
Provides a clean interface for extracting availability from Calendly links
Mocks data for MVP purposes while maintaining a structure that would work with the real API
Handles both user-level and event-type-level Calendly links
Includes comprehensive docstrings for all methods

For the MVP, we're mocking the availability data since:

The API doesn't directly support setting or retrieving availability through simple endpoints Calendly Developer
Real implementation would require multiple API calls to different endpoints
We'd need paid Calendly accounts for complete API access

In a production implementation, we would:

Use the List User Availability Schedules endpoint to get working hours
Use the List User Busy Times endpoint to get busy periods
Calculate available slots based on working hours minus busy times
Factor in event type-specific constraints if an event type is specified

This adapter should integrate well with the rest of the system and can be expanded later when we have full API access.

? We also need to take into consideration about how we get access to the OAuth from the user and accounting for the rate limits ?

## Google Calendar adapter implementation notes

This Google Calendar adapter implementation:

Supports multiple authentication methods:

Service account (for production use in server environments) Service accounts are recommended for server-to-server interactions, as they belong to your application rather than an individual user. Google
OAuth 2.0 flow (for development/testing with user accounts)
Mock mode (when neither is available)

Uses FreeBusy API to get busy periods:
The FreeBusy API returns time ranges during which a calendar should be regarded as busy, which allows us to calculate available slots. Googleapis
Handles calendar URL parsing properly:

Extracts calendar IDs from Google Calendar links
Supports both personal and organizational calendars

Provides robust error handling and fallbacks:

Falls back to mock data if API access fails
Includes detailed logging for debugging

Includes time zone handling:

All calculations are done in UTC
The interface returns TimeSlot objects with proper timezone information

The implementation follows a practical approach for the MVP, where it can work with real API access when credentials are available, but also functions in a mock mode when needed. This allows for development and testing without requiring real Google Calendar API credentials.
