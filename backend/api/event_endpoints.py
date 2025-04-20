"""API endpoints for event creation.

This module defines the API endpoints for selecting a time slot
and creating Google Calendar events.
"""

from typing import List, Optional
from datetime import datetime
import os # For environment variables

from fastapi import APIRouter, Depends, HTTPException, Body, Header
from pydantic import BaseModel, Field, EmailStr
# Import Clerk for verification
from clerk_sdk import Clerk
from clerk_sdk.request_verification import RequestVerificationError
# Import Google Credentials
from google.oauth2.credentials import Credentials

from core.models import TimeSlot, CalendarEvent, EventParticipant, CalendarType
from core.calendar_service import CalendarService
from adapters.base import AuthenticationError, EventCreationError


# Pydantic models for API request/response
class ParticipantInput(BaseModel):
    """Model for participant input in API requests."""
    email: EmailStr
    name: Optional[str] = None


class TimeSlotInput(BaseModel):
    """Model for time slot input in API requests."""
    start: datetime
    end: datetime
    timezone: str


class EventInput(BaseModel):
    """Model for event input in API requests."""
    title: str
    description: Optional[str] = None
    location: Optional[str] = None
    selected_slot: TimeSlotInput
    participants: List[ParticipantInput]
    organizer_email: Optional[str] = None


class EventOutput(BaseModel):
    """Model for event output in API responses."""
    event_id: str
    calendar_link: str
    title: str
    start_time: datetime
    end_time: datetime
    timezone: str
    status: str
    attendees: List[str]


# Initialize Clerk client (requires CLERK_SECRET_KEY environment variable)
# You might want to move this initialization to a central config or main app file
clerk_secret_key = os.getenv("CLERK_SECRET_KEY")
if not clerk_secret_key:
    # Log a warning or raise an error if the key is missing
    # For now, let it potentially fail later if Clerk is used without a key
    print("Warning: CLERK_SECRET_KEY environment variable not set. Clerk verification will fail.")
    # Or raise ImproperlyConfigured("CLERK_SECRET_KEY must be set")

clerk = Clerk(secret_key=clerk_secret_key)


# --- Clerk Authentication Dependency ---
async def get_verified_session(authorization: Optional[str] = Header(None)) -> dict:
    """FastAPI dependency to verify Clerk session token from Authorization header."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")

    # Expecting "Bearer <token>"
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authorization header format")

    token = parts[1]
    try:
        # Verify the session token using Clerk SDK
        session_claims = clerk.verify_token(token)
        return session_claims
    except RequestVerificationError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")
    except Exception as e:
        # Catch other potential errors during verification
        raise HTTPException(status_code=500, detail=f"Token verification failed: {e}")


async def get_google_credentials_from_session(
    session: dict = Depends(get_verified_session)
) -> Credentials:
    """Dependency to extract Google OAuth token from verified Clerk session.

    Assumes the Google OAuth token is stored in the public metadata
    or private metadata of the Clerk session. Adjust the key ('google_oauth_token')
    as needed based on your Clerk setup.
    """
    # --- Placeholder: Extract Google Token from Clerk Session --- 
    # This part is highly dependent on how you configure Clerk
    # to store provider tokens (e.g., in public_metadata or private_metadata).
    # You might need to make an API call to Clerk's backend API here
    # using the session user_id if the token isn't directly in the JWT claims.
    
    # Example: Assuming token info is in public_metadata (adjust key as needed)
    metadata = session.get('public_metadata', {})
    google_token_info = metadata.get('google_oauth_token') # Replace with your actual key
    
    # Example: Assuming token info is in private_metadata (less common for passing to frontend)
    # metadata = session.get('private_metadata', {})
    # google_token_info = metadata.get('google_oauth_token')

    # Example: Placeholder if you need to call Clerk Backend API (more complex)
    # user_id = session.get('sub') # Get user ID from standard JWT claim
    # if user_id:
    #    try:
    #        # This requires implementing a method to call Clerk's API
    #        google_token_info = await fetch_google_token_from_clerk_api(user_id)
    #    except Exception as e:
    #        raise HTTPException(status_code=500, detail=f"Failed to retrieve Google token: {e}")
    
    if not google_token_info or not isinstance(google_token_info, dict):
        raise HTTPException(
            status_code=403, 
            detail="Google OAuth token not found in session metadata or is invalid."
        )

    # Construct Google Credentials object
    # Assumes google_token_info contains keys like 'access_token', 'refresh_token', etc.
    # You *must* get client_id and client_secret from your Google Cloud config
    # (e.g., environment variables) as they are not typically in Clerk session.
    try:
        # IMPORTANT: Get these from your secure configuration (e.g., env vars)
        google_client_id = os.getenv("GOOGLE_CLIENT_ID")
        google_client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        if not google_client_id or not google_client_secret:
             raise ValueError("GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set in environment")
             
        credentials = Credentials(
            token=google_token_info.get('access_token'),
            refresh_token=google_token_info.get('refresh_token'),
            token_uri=google_token_info.get('token_uri', 'https://oauth2.googleapis.com/token'),
            client_id=google_client_id, # From env
            client_secret=google_client_secret, # From env
            scopes=google_token_info.get('scopes', ['https://www.googleapis.com/auth/calendar'])
            # Add expiry if available from Clerk token info
            # expiry=datetime.fromtimestamp(google_token_info.get('expires_at')) if google_token_info.get('expires_at') else None
        )
        
        # Optional: Trigger a refresh if close to expiry? Or rely on Google client lib.
        # Clerk should ideally provide a valid, non-expired token.
        if credentials.expired:
             # Potentially try to refresh here if refresh token exists, but it adds complexity.
             # It's often better to ensure the token passed from frontend/Clerk is fresh.
             print("Warning: Google token from session is expired.")
             # raise HTTPException(status_code=401, detail="Google OAuth token is expired.")
             
        return credentials
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to construct Google Credentials: {e}"
        )
# --- End Clerk Authentication Dependencies ---


# Create router
router = APIRouter(prefix="/api/calendar", tags=["calendar"])


# Dependency to get services
def get_calendar_service():
    """Get the calendar service instance."""
    return CalendarService()


@router.post("/create-event", response_model=EventOutput)
async def create_event(
    event_input: EventInput,
    # Inject dependencies: Get CalendarService and verified Google Credentials
    calendar_service: CalendarService = Depends(get_calendar_service),
    google_credentials: Credentials = Depends(get_google_credentials_from_session)
):
    """Create a Google Calendar event from a selected time slot (Requires Clerk Auth).
    
    This endpoint creates a calendar event with the specified details
    and sends invites to all participants.
    
    Args:
        event_input: The event details including selected time slot
        calendar_service: Service for creating calendar events
        google_credentials: Verified Google OAuth credentials
        
    Returns:
        Details of the created event
        
    Raises:
        HTTPException: If event creation fails
    """
    try:
        # Convert input models to domain models
        time_slot = TimeSlot(
            start=event_input.selected_slot.start,
            end=event_input.selected_slot.end,
            timezone=event_input.selected_slot.timezone
        )
        
        # Convert participant inputs to domain model
        participants = [
            EventParticipant(
                email=p.email,
                name=p.name,
                calendar_type=CalendarType.GOOGLE  # Force Google Calendar for event creation
            )
            for p in event_input.participants
        ]
        
        # Create calendar event
        calendar_event = CalendarEvent(
            title=event_input.title,
            start_time=time_slot.start,
            end_time=time_slot.end,
            timezone=time_slot.timezone,
            description=event_input.description,
            location=event_input.location,
            participants=participants,
            organizer=event_input.organizer_email
        )
        
        # Set preferred calendar to Google Calendar
        calendar_event.metadata['preferred_calendar'] = 'GOOGLE'
        
        # Create the event using the calendar service
        confirmation = calendar_service.create_event(
            calendar_event, 
            google_credentials=google_credentials
        )
        
        # Construct attendee list
        attendees = [p.email for p in participants]
        
        # Convert to API response model
        return EventOutput(
            event_id=confirmation.event_id,
            calendar_link=confirmation.calendar_link,
            title=confirmation.event.title,
            start_time=confirmation.event.start_time,
            end_time=confirmation.event.end_time,
            timezone=confirmation.event.timezone,
            status=confirmation.status,
            attendees=attendees
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except EventCreationError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Event creation failed: {str(e)}")