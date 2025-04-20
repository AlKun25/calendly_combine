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
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
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
        credentials_path: Path to the Google API credentials file
        token_path: Path to store the authentication token
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
        credentials_path: Optional[str] = None, 
        token_path: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        """Initialize the Google Calendar adapter.
        
        Args:
            credentials_path: Path to the Google API credentials file
            token_path: Path to store the authentication token
            api_key: Optional Google Calendar API key for non-OAuth requests
        """
        self.credentials_path = credentials_path or os.getenv("GOOGLE_CREDENTIALS_PATH")
        self.token_path = token_path or os.getenv("GOOGLE_TOKEN_PATH", "token.json")
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self._credentials = None
        self._service = None
        self._http_client = None
        
        # Try to load existing credentials
        self._load_credentials()
    
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
    
    def _load_credentials(self) -> None:
        """Load Google API credentials from file or refresh token."""
        if os.path.exists(self.token_path):
            try:
                with open(self.token_path, "r") as token:
                    self._credentials = Credentials.from_authorized_user_info(
                        eval(token.read()), SCOPES
                    )
            except Exception as e:
                logger.warning(f"Failed to load token: {e}")
                self._credentials = None
        
        # If credentials exist but expired, refresh them
        if self._credentials and self._credentials.expired and self._credentials.refresh_token:
            try:
                self._credentials.refresh(Request())
                self._save_credentials()
            except Exception as e:
                logger.warning(f"Failed to refresh token: {e}")
                self._credentials = None
    
    def _save_credentials(self) -> None:
        """Save the current credentials to the token file."""
        if not self._credentials:
            return
            
        # Save credentials to the file
        with open(self.token_path, "w") as token:
            token.write(str(self._credentials.to_json()))
    
    def authenticate(self, credentials: Dict[str, Any] = None) -> bool:
        """Authenticate with Google Calendar API.
        
        Args:
            credentials: Optional credentials dict if not using file
            
        Returns:
            True if authentication was successful
            
        Raises:
            AuthenticationError: If authentication fails
        """
        try:
            # If already authenticated, return True
            if self.is_authenticated():
                return True
                
            # If credentials provided directly, use them
            if credentials and 'token' in credentials:
                self._credentials = Credentials(
                    token=credentials.get('token'),
                    refresh_token=credentials.get('refresh_token'),
                    client_id=credentials.get('client_id'),
                    client_secret=credentials.get('client_secret'),
                    scopes=SCOPES,
                    token_uri='https://oauth2.googleapis.com/token'
                )
                self._save_credentials()
                return self.is_authenticated()
            
            # Otherwise, use credentials file
            if not self.credentials_path or not os.path.exists(self.credentials_path):
                raise AuthenticationError("No credentials file found")
                
            flow = InstalledAppFlow.from_client_secrets_file(
                self.credentials_path, SCOPES
            )
            self._credentials = flow.run_local_server(port=0)
            self._save_credentials()
            
            return self.is_authenticated()
        except Exception as e:
            logger.error(f"Google Calendar authentication failed: {e}")
            raise AuthenticationError(f"Google Calendar authentication failed: {e}") from e
    
    def is_authenticated(self) -> bool:
        """Check if authenticated with Google Calendar API.
        
        Returns:
            True if authenticated, False otherwise
        """
        if not self._credentials:
            return False
            
        # If credentials exist but expired and can't be refreshed, consider not authenticated
        if self._credentials.expired and not self._credentials.refresh_token:
            return False
            
        # Initialize service if needed
        if not self._service:
            try:
                self._service = build('calendar', 'v3', credentials=self._credentials)
            except Exception as e:
                logger.error(f"Failed to build Google Calendar service: {e}")
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

    def create_event(self, event: CalendarEvent) -> EventConfirmation:
        """Create an event in Google Calendar.
        
        Args:
            event: The event to create
            
        Returns:
            Confirmation details for the created event
            
        Raises:
            AuthenticationError: If not authenticated
            EventCreationError: If event creation fails
        """
        if not self.is_authenticated():
            raise AuthenticationError("Not authenticated with Google Calendar")
        
        # Convert CalendarEvent to Google Calendar event format
        calendar_id = 'primary'
        if event.organizer:
            calendar_id = event.organizer
        
        attendees = []
        for participant in event.participants:
            attendee = {'email': participant.email}
            if participant.name:
                attendee['displayName'] = participant.name
            attendees.append(attendee)
        
        # Create the event
        google_event = {
            'summary': event.title,
            'description': event.description or '',
            'start': {
                'dateTime': event.start_time.isoformat(),
                'timeZone': event.timezone,
            },
            'end': {
                'dateTime': event.end_time.isoformat(),
                'timeZone': event.timezone,
            },
            'attendees': attendees,
        }
        
        # Add location if specified
        if event.location:
            google_event['location'] = event.location
        
        try:
            created_event = self._service.events().insert(
                calendarId=calendar_id,
                body=google_event,
                sendUpdates='all'  # Send emails to attendees
            ).execute()
            
            return EventConfirmation(
                event_id=created_event['id'],
                calendar_link=created_event['htmlLink'],
                event=event,
                status=created_event['status'],
                provider=CalendarType.GOOGLE
            )
        except Exception as e:
            logger.error(f"Failed to create Google Calendar event: {e}")
            raise EventCreationError(f"Failed to create Google Calendar event: {e}") from e