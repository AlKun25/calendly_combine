# Calendar Integrator Backend - Audit

## Overview

This backend service aims to find overlapping availability across multiple calendar scheduling links (currently Calendly and Google Calendar) and facilitate the creation of a meeting event in Google Calendar based on a selected common slot.

It is built using Python with FastAPI for the API layer.

## Code Structure

The codebase is organized into the following main directories:

-   **`core/`**: Contains the core business logic and data models.
    -   `models.py`: Defines Pydantic and Dataclass models for `TimeSlot`, `AvailabilitySchedule`, `CalendarEvent`, etc., including timezone handling and validation.
    -   `overlap_engine.py`: Implements the algorithm to find overlapping `TimeSlot`s across multiple `AvailabilitySchedule`s. It normalizes slots to UTC and merges adjacent/overlapping slots.
    -   `calendar_service.py`: A service layer responsible for orchestrating event creation. Currently, it is hardcoded to only use the Google Calendar adapter for creating events.

-   **`adapters/`**: Handles communication with external calendar platforms.
    -   `base.py`: Defines an abstract `BaseAdapter` class with required methods like `authenticate`, `extract_availability`, and `create_event`.
    -   `calendly.py`: Implements the adapter for Calendly.
        -   Uses the official Calendly API to extract availability from user links (requires `CALENDLY_API_KEY`).
        -   Includes a mock mode fallback if the API key is missing or an HTTP error occurs during availability extraction.
        -   **Event creation is not implemented (`NotImplementedError`).**
    -   `google_calendar.py`: Implements the adapter for Google Calendar.
        -   Extracts availability from Google Calendar booking links using **unofficial, internal Google APIs**. This approach is potentially unstable and may break without notice.
        -   Creates events using the official Google Calendar API via OAuth 2.0. Handles token storage and refresh.

-   **`api/`**: Defines the FastAPI web application and endpoints.
    -   `main.py`: Sets up the FastAPI app and includes the `/api/calendar/process` endpoint. This endpoint takes a list of calendar links, fetches availability using the appropriate adapters, calculates overlaps, and returns the results.
    -   `event_endpoints.py`: Defines the `/api/calendar/create-event` endpoint. This takes details of a selected time slot and event information (title, participants) and uses the `CalendarService` to create the event.

-   **`tests/`**: Contains unit tests for various components.
    -   Includes tests for models (`test_models.py`), the overlap engine (`test_overlap_engine.py`), and the Calendly adapter (`test_calendly_adapters.py`).
    -   Tests for the base adapter functionality (`test_adapters.py`) and the API layer (`test_api.py`) appear to be missing or empty.

## Intended Workflow

1.  **Find Overlaps:** A client sends a POST request to `/api/calendar/process` with a list of calendar links (type: `calendly` or `google`) and optionally a desired meeting duration.
2.  The backend uses the `CalendlyAdapter` and `GoogleCalendarAdapter` to fetch `AvailabilitySchedule` objects for each link.
3.  The `OverlapProcessor` calculates the common available `TimeSlot`s across all schedules, normalized to UTC.
4.  If a duration was specified, the slots are filtered to only include those long enough.
5.  The API responds with the list of overlapping `TimeSlot`s and participant details derived from the input.
6.  **Create Event:** The client selects a desired `TimeSlot` from the results and sends a POST request to `/api/calendar/create-event` with the slot details, event title, description, location, and participant list.
7.  The `CalendarService` uses the `GoogleCalendarAdapter` to create the event in the organizer's (or authenticated user's) Google Calendar, inviting the specified participants.
8.  The API responds with confirmation details of the created event (ID, link, status).

## Current Status & Assessment

### What's Working (Based on Code Implementation)

-   **Core Logic:** Data modeling and the overlap calculation algorithm appear robust and handle timezones correctly.
-   **Overlap API:** The `/api/calendar/process` endpoint structure is in place and wired to the core logic and adapters.
-   **Calendly Availability:** Extraction seems functional using the official API (requires API key). Mock fallback exists.
-   **Google Event Creation:** Creating events in Google Calendar via the `/api/calendar/create-event` endpoint is implemented using the official API.

### Potential Issues & Missing Functionality

-   **Google Availability Extraction:**
    -   **HIGH RISK:** Relies on **unofficial internal Google APIs**. These are undocumented and highly likely to change or break unexpectedly, rendering availability extraction non-functional.
    -   Authentication for availability seems limited; likely only works for public booking pages and doesn't leverage the OAuth credentials or API key used for event creation.
-   **Calendly Event Creation:**
    -   **NOT IMPLEMENTED:** The `create_event` method in the `CalendlyAdapter` is not implemented. Events can *only* be created in Google Calendar via the current `CalendarService`.
-   **Google Authentication Flow:**
    -   The current OAuth 2.0 flow (`InstalledAppFlow`) in `GoogleCalendarAdapter` requires manual user interaction (opening a browser URL) *on the server*. This is unsuitable for a typical backend API. It needs to be replaced with a server-side web flow or a service account approach for production use.
-   **Error Handling:**
    -   While basic error handling exists, it could be more granular for specific API errors (e.g., rate limits, invalid inputs to external APIs).
    -   The Calendly adapter's fallback to mock data on *any* HTTP error might obscure underlying issues.
-   **Missing Link Generation:** The ability to generate shareable links (mentioned in the previous README version) is not implemented.
-   **Incomplete Testing:** API layer and base adapter functionality lack tests, potentially hiding integration issues.

## Setup & Configuration

-   Requires Python 3.x.
-   Dependencies are listed in `requirements.txt`. Install using `pip install -r requirements.txt`.
-   Configuration is managed via a `.env` file. See `.env.example` (if available) or the code for required variables:
    -   `CALENDLY_API_KEY`: Required for Calendly availability extraction (otherwise uses mock data).
    -   `GOOGLE_CREDENTIALS_PATH`: Path to Google `credentials.json` file for OAuth.
    -   `GOOGLE_TOKEN_PATH`: Path where the Google OAuth token will be stored (`token.json` by default).
    -   `GOOGLE_API_KEY`: Optional, potentially for future use or non-OAuth Google API calls (currently not used for availability).

## Running the API

Use an ASGI server like Uvicorn:
`uvicorn api.main:app --reload`

The API documentation (Swagger UI) should be available at `/docs`.