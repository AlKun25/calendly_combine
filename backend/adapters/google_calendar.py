"""Google Calendar adapter for extracting availability and creating events.

This module provides functionality to interact with the Google Calendar API,
including extracting availability information and creating calendar events.
"""

import logging
import os
import re
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta, timezone

import httpx
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from core.models import (
    AvailabilitySchedule, TimeSlot, CalendarType, 
    CalendarEvent, EventConfirmation
)
from adapters.base import (
    BaseAdapter, AuthenticationError, 
    ResourceNotFoundError, EventCreationError
)

# Configure module logger
logger = logging.getLogger(__name__)

# Google Calendar API scopes
SCOPES = ['https://www.googleapis.com/auth/calendar']


class GoogleCalendarAdapter(BaseAdapter):
    """Adapter for interacting with Google Calendar.
    
    This adapter provides functionality to:
    1. Extract availability from Google Calendar links
    2. Create events in Google Calendar
    
    Attributes:
        api_key: Optional API key for requests that don't require OAuth
    """
    
    # Regex patterns to extract calendar ID from links
    BOOKING_LINK_PATTERN_LEGACY = r'calendar/appointments/schedules/([^/\?]+)'
    BOOKING_LINK_PATTERN_NEW = r'calendar\.app\.google/([A-Za-z0-9]+)'
    
    # Google Calendar API base URLs
    API_BASE_URL = "https://www.googleapis.com/calendar/v3"
    BOOKING_API_BASE_URL = "https://calendar-pa.clients6.google.com/v1/calendar"
    
    def __init__(
        self,
        api_key: Optional[str] = None
    ):
        """Initialize the Google Calendar adapter.

        Args:
            api_key: Optional Google Calendar API key for non-OAuth requests
                     (Note: Currently primarily uses OAuth via Clerk).
        """
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self._credentials = None # Credentials will be passed per-request
        self._service = None # Service will be built per-request with credentials
        self._http_client = None
    
    @property
    def http_client(self) -> httpx.Client:
        """Get or create the HTTP client for API requests.
        
        Returns:
            Configured HTTP client
        """
        if not self._http_client:
            self._http_client = httpx.Client(
                timeout=10.0,
                transport=httpx.HTTPTransport(retries=3)
            )
                
        return self._http_client
    
    def authenticate(self, credentials: Optional[Credentials] = None) -> bool:
        """Validate provided Google OAuth credentials.

        This method now expects credentials (obtained via Clerk on the frontend)
        to be passed in, rather than initiating an OAuth flow.

        Args:
            credentials: Google OAuth Credentials object.

        Returns:
            True if the provided credentials appear valid (not expired).

        Raises:
            AuthenticationError: If no credentials are provided or they are invalid/expired.
        """
        if not credentials or not isinstance(credentials, Credentials):
            raise AuthenticationError("Google OAuth Credentials object required.")

        # Check if credentials have expired (basic check, doesn't guarantee API access)
        # Refresh logic should ideally happen before passing credentials here,
        # managed by the Clerk frontend/backend interaction.
        if credentials.expired:
             # If refresh token exists, maybe try a refresh? Or expect frontend to handle.
             # For now, consider expired credentials needing refresh as an error here.
             # if credentials.refresh_token:
             #     try:
             #         # Note: This requires google.auth.transport.requests Request
             #         # credentials.refresh(Request())
             #         # return True # If refresh succeeds
             #     except Exception as e:
             #         logger.error(f"Failed to refresh Google token: {e}")
             #         raise AuthenticationError(f"Google OAuth token expired and refresh failed: {e}")
             raise AuthenticationError("Google OAuth token is expired.")

        # Store credentials temporarily for potential immediate use (e.g., is_authenticated)
        # This might be removed if is_authenticated is also removed or refactored.
        self._credentials = credentials
        return True
    
    def is_authenticated(self) -> bool:
        """Check if valid credentials have been provided for the current request.

        Note: This is less meaningful now as authentication is checked per-request
        via Clerk middleware. This method primarily checks if credentials
        were passed to `authenticate` recently.
        """
        # Check if credentials exist and are not expired
        if not self._credentials or not isinstance(self._credentials, Credentials):
             return False
        if self._credentials.expired:
             # A refresh token existing doesn't guarantee it will work,
             # and refresh should happen before calling adapter methods.
             return False
        return True
    
    def extract_availability(self, booking_link: str) -> AvailabilitySchedule:
        """Extract availability information from a Google Calendar booking link.
        
        Args:
            booking_link: The Google Calendar booking link
            
        Returns:
            An AvailabilitySchedule with the extracted time slots
            
        Raises:
            ValueError: If the link format is invalid
            ResourceNotFoundError: If the booking schedule cannot be found
            AuthenticationError: If authentication with the API fails
            EventCreationError: For other API or parsing errors
        """
        logger.info(f"Extracting availability from Google Calendar booking link: {booking_link}")
        
        # Validate input
        if not booking_link or not isinstance(booking_link, str):
            raise ValueError("Google Calendar booking link must be a non-empty string")
        
        # Extract schedule ID from the link
        schedule_id = self._extract_schedule_id(booking_link)
        
        if not schedule_id:
            logger.error(f"Invalid Google Calendar booking link format: {booking_link}")
            raise ValueError(f"Invalid Google Calendar booking link format: {booking_link}")
        
        try:
            # Get schedule information
            schedule_info = self._get_schedule_info(schedule_id)
            
            # Create availability schedule
            schedule = AvailabilitySchedule(
                calendar_id=schedule_id,
                calendar_type=CalendarType.GOOGLE,
                owner_name=self._extract_owner_name(schedule_info)
            )
            
            # Get available time slots
            available_slots = self._get_available_slots(schedule_id)
            
            # Add slots to schedule
            for slot in available_slots:
                schedule.add_slot(slot)
            
            logger.info(
                f"Successfully extracted {len(schedule.time_slots)} available time slots"
            )
            return schedule
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.error(f"Appointment schedule not found: {e}")
                raise ResourceNotFoundError(f"Appointment schedule not found: {e}") from e
            elif e.response.status_code == 401 or e.response.status_code == 403:
                logger.error(f"Authentication failed with Google Calendar API: {e}")
                raise AuthenticationError("Authentication failed with Google Calendar API") from e
            else:
                logger.error(f"HTTP error during Google Calendar API request: {e}")
                raise EventCreationError(f"Google Calendar API error: {e}") from e
                
        except httpx.HTTPError as e:
            logger.error(f"HTTP error during Google Calendar API request: {e}")
            raise EventCreationError(f"Google Calendar API error: {e}") from e
            
        except Exception as e:
            logger.error(f"Error extracting availability from Google Calendar: {e}")
            raise EventCreationError(f"Error extracting availability: {e}") from e
    
    def _extract_schedule_id(self, booking_link: str) -> str:
        """Extract schedule ID from a Google Calendar booking link.
        
        Args:
            booking_link: The Google Calendar booking link to extract from.
            
        Returns:
            The schedule ID as a string, or empty string if not found.
        """
        # Try legacy format first
        match = re.search(self.BOOKING_LINK_PATTERN_LEGACY, booking_link)
        
        if match:
            schedule_id = match.group(1)
            logger.debug(f"Extracted schedule_id={schedule_id} (legacy format)")
            return schedule_id
            
        # Try new shortlink format
        match = re.search(self.BOOKING_LINK_PATTERN_NEW, booking_link)
        
        if match:
            # For shortlinks, we'll need to convert the code to an actual schedule ID
            # by making an API call or using a conversion method
            shortcode = match.group(1)
            logger.debug(f"Extracted shortcode={shortcode} (new format)")
            
            # Get the actual schedule ID from the shortcode
            schedule_id = self._resolve_shortcode(shortcode)
            return schedule_id
            
        return ""
    
    def _resolve_shortcode(self, shortcode: str) -> str:
        """Resolve a Google Calendar shortcode to a schedule ID.
        
        Args:
            shortcode: The shortcode from a calendar.app.google URL.
            
        Returns:
            The resolved schedule ID or the shortcode itself if resolution fails.
        """
        try:
            # Endpoint to resolve shortcodes
            url = f"https://calendar.app.google/api/resolve/{shortcode}"
            
            response = self.http_client.get(url)
            response.raise_for_status()
            
            data = response.json()
            
            # Extract the schedule ID from the response
            schedule_id = data.get("scheduleId") or data.get("id")
            
            if schedule_id:
                logger.debug(f"Resolved shortcode {shortcode} to schedule ID {schedule_id}")
                return schedule_id
            else:
                logger.warning(f"Could not extract schedule ID from shortcode response")
                return shortcode  # Return the shortcode itself as fallback
                
        except (httpx.HTTPError, KeyError, ValueError) as e:
            logger.warning(f"Error resolving shortcode {shortcode}: {e}")
            return shortcode  # Return the shortcode itself as fallback
    
    def _get_schedule_info(self, schedule_id: str) -> Dict[str, Any]:
        """Get appointment schedule information.
        
        Args:
            schedule_id: The Google Calendar appointment schedule ID.
            
        Returns:
            Dictionary with schedule information.
            
        Raises:
            ResourceNotFoundError: If the schedule doesn't exist.
            AuthenticationError: If authentication fails.
            httpx.HTTPError: If there's an error communicating with the API.
        """
        logger.debug(f"Getting schedule info for {schedule_id}")
        
        try:
            # For appointment scheduling, we need to use a special endpoint
            url = f"{self.BOOKING_API_BASE_URL}/appointment/schedules/{schedule_id}"
            
            # Add API key if available
            params = {}
            if self.api_key:
                params["key"] = self.api_key
            
            # Make the request
            response = self.http_client.get(url, params=params)
            response.raise_for_status()
            
            return response.json()
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.error(f"Schedule not found: {schedule_id}")
                raise ResourceNotFoundError(f"Schedule not found: {schedule_id}")
            elif e.response.status_code in (401, 403):
                logger.error(f"Authentication failed for schedule: {schedule_id}")
                raise AuthenticationError(f"Authentication failed for schedule: {schedule_id}")
            else:
                logger.error(f"HTTP error getting schedule info: {e}")
                raise
    
    def _extract_owner_name(self, schedule_info: Dict[str, Any]) -> Optional[str]:
        """Extract owner name from schedule information.
        
        Args:
            schedule_info: Dictionary with schedule information.
            
        Returns:
            The owner name if available, otherwise None.
        """
        # Extract owner name from schedule info
        try:
            return schedule_info.get("ownerName") or schedule_info.get("owner", {}).get("name")
        except (KeyError, TypeError):
            logger.warning("Could not extract owner name from schedule info")
            return None
    
    def _get_available_slots(self, schedule_id: str) -> List[TimeSlot]:
        """Get available time slots for a Google Calendar appointment schedule.
        
        Args:
            schedule_id: The Google Calendar appointment schedule ID.
            
        Returns:
            List of TimeSlot objects representing available times.
            
        Raises:
            EventCreationError: If there's an error getting availability data.
        """
        logger.debug(f"Getting available slots for schedule {schedule_id}")
        
        try:
            # Calculate date range (next 30 days)
            now = datetime.now(timezone.utc)
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(days=30)
            
            # Format dates for the API
            start_str = start_date.strftime("%Y-%m-%d")
            end_str = end_date.strftime("%Y-%m-%d")
            
            # Build the request URL
            url = f"{self.BOOKING_API_BASE_URL}/appointment/schedules/{schedule_id}/slots"
            
            # Set query parameters
            params = {
                "startTime": start_str,
                "endTime": end_str,
            }
            
            # Add API key if available
            if self.api_key:
                params["key"] = self.api_key
            
            # Request available slots
            response = self.http_client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # Process the slots
            available_slots = []
            for slot_data in data.get("slots", []):
                try:
                    # Extract start and end times
                    start_time_str = slot_data.get("startTime")
                    end_time_str = slot_data.get("endTime")
                    
                    if not start_time_str or not end_time_str:
                        continue
                    
                    # Parse ISO format datetime strings
                    start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
                    end_time = datetime.fromisoformat(end_time_str.replace("Z", "+00:00"))
                    
                    # Create TimeSlot object
                    time_slot = TimeSlot(
                        start=start_time,
                        end=end_time,
                        timezone="UTC"  # API returns times in UTC
                    )
                    
                    available_slots.append(time_slot)
                    
                except (ValueError, KeyError) as e:
                    logger.warning(f"Error processing slot data: {e}")
                    continue
            
            logger.info(f"Found {len(available_slots)} available slots")
            return available_slots
            
        except httpx.HTTPError as e:
            logger.error(f"Error getting available slots: {e}")
            raise EventCreationError(f"Error getting available slots: {e}") from e
            
        except Exception as e:
            logger.error(f"Unexpected error getting available slots: {e}")
            
            # Try alternative API endpoint for shortlinks if the primary endpoint fails
            return self._get_available_slots_alternative(schedule_id)
    
    def _get_available_slots_alternative(self, schedule_id: str) -> List[TimeSlot]:
        """Alternative method to get available slots using a different API endpoint.
        
        This is used as a fallback when the primary endpoint fails, particularly
        useful for shortcode-based links.
        
        Args:
            schedule_id: The Google Calendar appointment schedule ID or shortcode.
            
        Returns:
            List of TimeSlot objects representing available times.
        """
        logger.debug(f"Trying alternative method to get available slots for {schedule_id}")
        
        try:
            # For shortlinks, we might need a different endpoint
            url = f"https://calendar.app.google/api/scheduling/{schedule_id}/availability"
            
            # Calculate date range (next 30 days)
            now = datetime.now(timezone.utc)
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(days=30)
            
            # Format dates for the API
            params = {
                "start": int(start_date.timestamp()),
                "end": int(end_date.timestamp()),
            }
            
            # Request available slots
            response = self.http_client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # Process the slots
            available_slots = []
            
            # The response format might be different in this API
            slots_data = data.get("availableSlots", []) or data.get("slots", [])
            
            for slot_data in slots_data:
                try:
                    # Extract timestamps (might be in seconds since epoch)
                    start_time_val = slot_data.get("startTime") or slot_data.get("start")
                    end_time_val = slot_data.get("endTime") or slot_data.get("end")
                    
                    if not start_time_val or not end_time_val:
                        continue
                    
                    # Convert to datetime objects (handle both string and timestamp formats)
                    if isinstance(start_time_val, (int, float)):
                        start_time = datetime.fromtimestamp(start_time_val, tz=timezone.utc)
                    else:
                        start_time = datetime.fromisoformat(start_time_val.replace("Z", "+00:00"))
                        
                    if isinstance(end_time_val, (int, float)):
                        end_time = datetime.fromtimestamp(end_time_val, tz=timezone.utc)
                    else:
                        end_time = datetime.fromisoformat(end_time_val.replace("Z", "+00:00"))
                    
                    # Create TimeSlot object
                    time_slot = TimeSlot(
                        start=start_time,
                        end=end_time,
                        timezone="UTC"
                    )
                    
                    available_slots.append(time_slot)
                    
                except (ValueError, KeyError, TypeError) as e:
                    logger.warning(f"Error processing alternative slot data: {e}")
                    continue
            
            logger.info(f"Found {len(available_slots)} available slots using alternative method")
            return available_slots
            
        except Exception as e:
            logger.error(f"Alternative method failed: {e}")
            # Return empty list as last resort
            return []

    def create_event(self, event: CalendarEvent, credentials: Optional[Credentials] = None) -> EventConfirmation:
        """Create an event in Google Calendar using provided credentials.

        Args:
            event: The CalendarEvent object to create.
            credentials: The Google OAuth Credentials object for the authenticated user.

        Returns:
            An EventConfirmation object.

        Raises:
            AuthenticationError: If credentials are not provided or invalid.
            EventCreationError: If the event creation fails via the API.
        """
        if not credentials or not isinstance(credentials, Credentials):
            raise AuthenticationError("Google OAuth credentials are required to create an event.")

        # Simple check for expired credentials, although they should ideally be refreshed before this point.
        if credentials.expired:
            raise AuthenticationError("Provided Google OAuth credentials have expired.")

        try:
            # Build the service dynamically with the provided credentials
            service = build('calendar', 'v3', credentials=credentials)

            # Prepare event body for Google API
            event_body = {
                'summary': event.title,
                'description': event.description,
                'location': event.location,
                'start': {
                    'dateTime': event.start_time.isoformat(),
                    'timeZone': event.timezone,
                },
                'end': {
                    'dateTime': event.end_time.isoformat(),
                    'timeZone': event.timezone,
                },
                'attendees': [
                    {'email': p.email, 'displayName': p.name}
                    for p in event.participants
                ],
                # Add organizer if provided
                # 'organizer': {'email': event.organizer} if event.organizer else None,
                # Add other relevant fields if needed (e.g., recurrence, reminders)
                'reminders': {
                    'useDefault': True,
                },
            }
            # Remove None values from attendees list
            event_body['attendees'] = [att for att in event_body['attendees'] if att is not None]
            # Add organizer only if it exists
            if event.organizer:
                event_body['organizer'] = {'email': event.organizer, 'self': True} # Mark organizer as self


            logger.info(f"Creating Google Calendar event: {event.title}")
            created_event = service.events().insert(
                calendarId='primary', # Use 'primary' calendar
                body=event_body,
                sendNotifications=True # Notify attendees
            ).execute()

            logger.info(f"Event created successfully with ID: {created_event.get('id')}")

            return EventConfirmation(
                event_id=created_event.get('id'),
                calendar_link=created_event.get('htmlLink'),
                event=event, # Return the original event data
                status=created_event.get('status', 'confirmed'),
                provider=CalendarType.GOOGLE
            )

        except Exception as e:
            logger.error(f"Failed to create Google Calendar event: {e}")
            # Check for specific Google API errors if possible
            # Example: from googleapiclient.errors import HttpError
            # if isinstance(e, HttpError):
            #     if e.resp.status == 401:
            #         raise AuthenticationError(f"Google API authentication error: {e}") from e
            #     elif e.resp.status == 403:
            #          raise AuthenticationError(f"Google API permission error: {e}") from e
            raise EventCreationError(f"Failed to create Google Calendar event: {str(e)}") from e