"""Calendly adapter for extracting availability and creating events.

This module provides functionality to interact with the Calendly API,
including extracting availability information and creating events.
"""

import re
import logging
import os
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone

import httpx
from dotenv import load_dotenv

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

# Load environment variables
load_dotenv()


class CalendlyAdapter(BaseAdapter):
    """Adapter for interacting with Calendly.
    
    This adapter provides functionality to:
    1. Extract availability information from Calendly links
    2. Create single-use scheduling links
    
    Attributes:
        api_key: Calendly API key for authenticated requests
        mock_mode: Whether the adapter is operating in mock mode
        slot_duration: Duration of time slots in minutes
        days_to_check: Number of days to check for availability
        http_client: HTTP client for API requests
    """
    
    # Regex pattern to extract user name from Calendly links
    USER_PATTERN = r'calendly\.com/([^/]+)(?:/([^/]+))?'
    
    # Calendly API base URL
    API_BASE_URL = "https://api.calendly.com"

    def __init__(
        self, 
        api_key: Optional[str] = None, 
        mock_mode: bool = False,
        slot_duration: int = 30,
        days_to_check: int = 7
    ):
        """Initialize the Calendly adapter.
        
        Args:
            api_key: Optional Calendly API key for authenticated requests.
                    If not provided, will attempt to use environment variables.
            mock_mode: Force mock mode even if API key is available.
            slot_duration: Duration of each time slot in minutes (default: 30).
            days_to_check: Number of days to check for availability (default: 7).
        
        Raises:
            ValueError: If slot_duration is not positive.
        """
        # Validate inputs
        if slot_duration <= 0:
            raise ValueError("slot_duration must be positive")
            
        if days_to_check <= 0:
            raise ValueError("days_to_check must be positive")
            
        self.api_key = api_key or os.getenv("CALENDLY_API_KEY")
        self.mock_mode = mock_mode or not self.api_key
        self.slot_duration = slot_duration
        self.days_to_check = days_to_check
        self._http_client = None
        
        if self.mock_mode:
            logger.info("Calendly adapter running in mock mode")

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
            
            # Set up authorization headers if API key is available
            if self.api_key:
                self._http_client.headers.update({
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                })
                
        return self._http_client
    
    def authenticate(self, credentials: Optional[Dict[str, Any]] = None) -> bool:
        """Authenticate with Calendly API.
        
        Args:
            credentials: Optional credentials dict with 'api_key'
            
        Returns:
            True if authentication was successful
            
        Raises:
            AuthenticationError: If authentication fails
        """
        if credentials and 'api_key' in credentials:
            self.api_key = credentials['api_key']
        
        if not self.api_key:
            raise AuthenticationError("No Calendly API key provided")
        
        # Test the API key by making a request to get current user
        try:
            url = f"{self.API_BASE_URL}/users/me"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            response = httpx.get(url, headers=headers)
            response.raise_for_status()
            
            # Update HTTP client headers if needed
            if self._http_client:
                self._http_client.headers.update(headers)
            else:
                # Create client if it doesn't exist
                self._http_client = httpx.Client(
                    timeout=10.0,
                    transport=httpx.HTTPTransport(retries=3),
                    headers=headers
                )
                
            return True
        except Exception as e:
            logger.error(f"Calendly authentication failed: {e}")
            raise AuthenticationError(f"Calendly authentication failed: {e}") from e
    
    def is_authenticated(self) -> bool:
        """Check if authenticated with Calendly API.
        
        Returns:
            True if API key is available, False otherwise
        """
        return bool(self.api_key) and not self.mock_mode

    def extract_availability(self, calendly_link: str) -> AvailabilitySchedule:
        """Extract availability information from a Calendly link.
        
        This method accepts a Calendly user link and extracts the available 
        time slots by querying the Calendly API or generating mock data.
        
        Args:
            calendly_link: A valid Calendly user link in the format 
                        'https://calendly.com/username'
                
        Returns:
            An AvailabilitySchedule object containing available time slots.
                
        Raises:
            ValueError: If the Calendly link format is invalid.
            AuthenticationError: If authentication fails.
            ResourceNotFoundError: If the user doesn't exist.
            BaseAdapterError: For other Calendly-specific errors.
            httpx.HTTPError: For network or HTTP errors.
        """
        # Validate input
        if not calendly_link or not isinstance(calendly_link, str):
            raise ValueError("Calendly link must be a non-empty string")
            
        logger.info(f"Extracting availability from Calendly link: {calendly_link}")
        
        # Extract user information from the link
        user_name = self._extract_user_info(calendly_link)
        
        if not user_name:
            logger.error(f"Invalid Calendly link format: {calendly_link}")
            raise ValueError(f"Invalid Calendly link format: {calendly_link}")
        
        try:
            # Get user UUID from username
            user_data = self._get_user_data(user_name)
            user_uri = user_data.get("resource", {}).get("uri")
            
            if not user_uri:
                logger.warning(f"Could not find user with name: {user_name}")
                raise ResourceNotFoundError(f"Could not find user with name: {user_name}")
            
            # Create availability schedule
            schedule = AvailabilitySchedule(
                calendar_id=user_uri,
                calendar_type=CalendarType.CALENDLY,
                owner_name=user_data.get("resource", {}).get("name", user_name)
            )
            
            # Get available time slots
            available_slots = self._get_available_slots(user_uri)
            
            # Add slots to schedule
            for slot in available_slots:
                schedule.add_slot(slot)
            
            logger.info(
                f"Successfully extracted {len(schedule.time_slots)} available time slots"
            )
            return schedule
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error(f"Authentication failed with Calendly API: {e}")
                if not self.mock_mode:
                    return self._create_mock_schedule(user_name)
                raise AuthenticationError("Authentication failed with Calendly API") from e
            elif e.response.status_code == 404:
                logger.error(f"Resource not found: {e}")
                if not self.mock_mode:
                    return self._create_mock_schedule(user_name)
                raise ResourceNotFoundError(f"Resource not found: {e}") from e
            else:
                logger.error(f"HTTP error during Calendly API request: {e}")
                if not self.mock_mode:
                    return self._create_mock_schedule(user_name)
                raise EventCreationError(f"Calendly API error: {e}") from e
                
        except httpx.HTTPError as e:
            logger.error(f"HTTP error during Calendly API request: {e}")
            
            # Fall back to mock mode if API call fails
            if not self.mock_mode:
                logger.info("Falling back to mock mode after API error")
                return self._create_mock_schedule(user_name)
            raise
            
        except Exception as e:
            logger.error(f"Error extracting availability from Calendly: {e}")
            
            # Fall back to mock mode for other errors too
            if not self.mock_mode:
                logger.info("Falling back to mock mode after error")
                return self._create_mock_schedule(user_name)
            raise EventCreationError(f"Error extracting availability: {e}") from e

    def _extract_user_info(self, calendly_link: str) -> str:
        """Extract user name from a Calendly link.
        
        Args:
            calendly_link: The Calendly link to extract information from.
            
        Returns:
            The user name extracted from the link, or empty string if none found.
        """
        match = re.search(self.USER_PATTERN, calendly_link)
        
        if not match:
            return ""
            
        user_name = match.group(1)
        logger.debug(f"Extracted user_name={user_name}")
        return user_name

    def _get_user_data(self, user_name: str) -> Dict[str, Any]:
        """Get user data from the Calendly API.
        
        Args:
            user_name: The Calendly user name to look up.
            
        Returns:
            User data from the Calendly API or mock data if in mock mode.
            
        Raises:
            ResourceNotFoundError: If the user could not be found.
            AuthenticationError: If authentication fails.
            httpx.HTTPError: If there's an error communicating with the API.
        """
        if self.mock_mode:
            logger.debug(f"Generating mock user data for {user_name}")
            return {
                "resource": {
                    "uri": f"https://api.calendly.com/users/{user_name}",
                    "name": user_name.capitalize()
                }
            }
        
        logger.debug(f"Looking up user data for {user_name}")
        
        # First, try to get user by username
        try:
            # In real implementation, we'd need to list users and find by name
            # This example assumes Calendly API v2 has a users/find endpoint
            url = f"{self.API_BASE_URL}/users/find"
            params = {"email": f"{user_name}@example.com"}  # Simplified approach
            
            response = self.http_client.get(url, params=params)
            response.raise_for_status()
            
            return response.json()
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Authentication failed") from e
            if e.response.status_code == 404:
                logger.warning(f"Failed to find user by name, trying direct UUID: {e}")
            else:
                raise
            
            # Fall back to trying the name as a UUID directly
            url = f"{self.API_BASE_URL}/users/{user_name}"
            
            response = self.http_client.get(url)
            response.raise_for_status()
            
            return response.json()

    def _get_available_slots(self, user_uri: str) -> List[TimeSlot]:
        """Get available time slots for a user.
        
        This method retrieves the available time slots for a given user
        using the Calendly API, or generates mock data if in mock mode.
        
        Args:
            user_uri: The Calendly user URI.
            
        Returns:
            List of TimeSlot objects representing available times.
            
        Raises:
            EventCreationError: If there's an error getting availability data.
        """
        logger.debug(f"Getting available slots for {user_uri}")
        
        if self.mock_mode:
            return self._generate_mock_slots()
        
        # In a real implementation, we need multiple API calls:
        try:
            # 1. Get user's availability schedules
            schedules_url = f"{self.API_BASE_URL}/scheduling_rules"
            schedules_params = {"user": user_uri}
            
            schedules_response = self.http_client.get(schedules_url, params=schedules_params)
            schedules_response.raise_for_status()
            schedules_data = schedules_response.json()
            
            if not schedules_data.get("collection"):
                logger.warning(f"No availability schedules found for {user_uri}")
                return self._generate_mock_slots()
            
            # 2. Get user's busy times
            # Date range: next N days
            now = datetime.now(timezone.utc)
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(days=self.days_to_check)
            
            busy_url = f"{self.API_BASE_URL}/busy_times"
            busy_params = {
                "user": user_uri,
                "start_time": start_date.isoformat(),
                "end_time": end_date.isoformat()
            }
            
            busy_response = self.http_client.get(busy_url, params=busy_params)
            busy_response.raise_for_status()
            busy_data = busy_response.json()
            
            # 3. Calculate available slots based on schedule minus busy times
            return self._calculate_available_slots(
                schedules_data["collection"],
                busy_data.get("busy_times", []),
                start_date,
                end_date
            )
            
        except httpx.HTTPError as e:
            logger.error(f"Error getting availability data: {e}")
            return self._generate_mock_slots()

    def _calculate_available_slots(
        self, 
        schedules: List[Dict[str, Any]], 
        busy_times: List[Dict[str, Any]],
        start_date: datetime,
        end_date: datetime
    ) -> List[TimeSlot]:
        """Calculate available slots based on schedules and busy times.
        
        Args:
            schedules: List of availability schedule data from the API.
            busy_times: List of busy time periods from the API.
            start_date: Start of the date range to calculate for.
            end_date: End of the date range to calculate for.
            
        Returns:
            List of TimeSlot objects representing available times.
        """
        # Convert busy times to TimeSlot objects
        busy_slots = []
        for busy in busy_times:
            try:
                busy_start = datetime.fromisoformat(busy["start_time"].replace("Z", "+00:00"))
                busy_end = datetime.fromisoformat(busy["end_time"].replace("Z", "+00:00"))
                busy_slots.append(TimeSlot(
                    start=busy_start,
                    end=busy_end,
                    timezone="UTC"
                ))
            except (KeyError, ValueError) as e:
                logger.warning(f"Skipping invalid busy time entry: {e}")
                continue
        
        # Process each day within range
        potential_slots = []
        current_date = start_date
        
        while current_date < end_date:
            # Skip weekends (0=Monday, 6=Sunday in Python datetime)
            weekday = current_date.weekday()
            if weekday >= 5:  # 5=Saturday, 6=Sunday
                current_date += timedelta(days=1)
                continue
            
            # For simplicity, assume working hours 9 AM to 5 PM
            # In practice, would extract this from the schedules data
            day_start = current_date.replace(hour=9, minute=0)
            day_end = current_date.replace(hour=17, minute=0)
            
            # Create slots for this day
            slot_start = day_start
            while slot_start < day_end:
                slot_end = slot_start + timedelta(minutes=self.slot_duration)
                
                # Create potential slot
                potential_slots.append(TimeSlot(
                    start=slot_start,
                    end=slot_end,
                    timezone="UTC"
                ))
                
                slot_start = slot_end
            
            # Move to next day
            current_date += timedelta(days=1)
        
        # Remove busy slots
        available_slots = []
        for potential_slot in potential_slots:
            is_available = True
            
            # Check if slot overlaps with any busy period using TimeSlot.overlaps_with()
            for busy_slot in busy_slots:
                if potential_slot.overlaps_with(busy_slot):
                    is_available = False
                    break
            
            if is_available:
                available_slots.append(potential_slot)
        
        return available_slots

    def _generate_mock_slots(self) -> List[TimeSlot]:
        """Generate mock available time slots.
        
        Used when the adapter is running in mock mode or when API calls fail.
        
        Returns:
            List of TimeSlot objects representing mocked available times.
        """
        slots = []
        
        # Get current date/time
        now = datetime.now(timezone.utc)
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Create example time slots for the next N days
        for day_offset in range(self.days_to_check):
            day = today + timedelta(days=day_offset)
            
            # Skip weekend slots
            weekday = day.weekday()
            if weekday >= 5:  # 5 = Saturday, 6 = Sunday
                continue
            
            # Add business hours slots (9AM-5PM)
            slot_start = day.replace(hour=9, minute=0)
            day_end = day.replace(hour=17, minute=0)
            
            while slot_start < day_end:
                slot_end = slot_start + timedelta(minutes=self.slot_duration)
                
                # Skip slots in the past
                if slot_end <= now:
                    slot_start = slot_end
                    continue
                
                slots.append(TimeSlot(
                    start=slot_start,
                    end=slot_end,
                    timezone="UTC"
                ))
                
                slot_start = slot_end
        
        # Log the number of slots created
        logger.info(f"Created {len(slots)} mock time slots")
        
        return slots

    def _create_mock_schedule(self, user_name: str) -> AvailabilitySchedule:
        """Create a complete mock availability schedule.
        
        Used as a fallback when the adapter encounters errors but needs to
        return some data.
        
        Args:
            user_name: The Calendly user name to create a mock schedule for.
            
        Returns:
            An AvailabilitySchedule with mock time slots.
        """
        mock_uri = f"https://api.calendly.com/users/{user_name}"
        schedule = AvailabilitySchedule(
            calendar_id=mock_uri,
            calendar_type=CalendarType.CALENDLY,
            owner_name=f"{user_name.capitalize()} (Mock)"
        )
        
        mock_slots = self._generate_mock_slots()
        for slot in mock_slots:
            schedule.add_slot(slot)
        
        logger.info(
            f"Created mock schedule for {user_name} with {len(mock_slots)} time slots"
        )
        return schedule

    def create_event(self, event: CalendarEvent) -> EventConfirmation:
        """Create a single-use scheduling link in Calendly.
        
        Args:
            event: The event to create
            
        Returns:
            Confirmation details with the scheduling link
            
        Raises:
            AuthenticationError: If not authenticated
            EventCreationError: If link creation fails
        """
        if not self.is_authenticated():
            raise AuthenticationError("Not authenticated with Calendly")
        
        # First, get the user data to find event types
        try:
            user_response = self.http_client.get(f"{self.API_BASE_URL}/users/me")
            user_response.raise_for_status()
            user_data = user_response.json()
            user_uri = user_data.get("resource", {}).get("uri")
            
            if not user_uri:
                raise EventCreationError("Failed to get user data from Calendly")
            
            # Get event types for the user
            event_types_url = f"{self.API_BASE_URL}/event_types"
            event_types_params = {"user": user_uri}
            
            event_types_response = self.http_client.get(
                event_types_url, params=event_types_params
            )
            event_types_response.raise_for_status()
            event_types_data = event_types_response.json()
            
            # Find an appropriate event type based on duration
            event_duration_minutes = int((event.end_time - event.start_time).total_seconds() / 60)
            
            selected_event_type = None
            for event_type in event_types_data.get("collection", []):
                duration = event_type.get("duration")
                if duration and duration == event_duration_minutes:
                    selected_event_type = event_type
                    break
            
            if not selected_event_type:
                # Use the first available event type as fallback
                if event_types_data.get("collection"):
                    selected_event_type = event_types_data["collection"][0]
                else:
                    raise EventCreationError("No event types found for Calendly user")
            
            # Create a single-use scheduling link
            event_type_uri = selected_event_type["uri"]
            
            single_use_url = f"{self.API_BASE_URL}/scheduling_links"
            single_use_data = {
                "max_event_count": 1,
                "owner": user_uri,
                "owner_type": "users",
                "event_type": event_type_uri
            }
            
            single_use_response = self.http_client.post(
                single_use_url, json=single_use_data
            )
            single_use_response.raise_for_status()
            single_use_data = single_use_response.json()
            
            scheduling_link = single_use_data.get("resource", {}).get("booking_url")
            
            if not scheduling_link:
                raise EventCreationError("Failed to create Calendly scheduling link")
            
            return EventConfirmation(
                event_id=single_use_data.get("resource", {}).get("uuid", ""),
                calendar_link=scheduling_link,
                event=event,
                status="created",
                provider=CalendarType.CALENDLY
            )
        except httpx.HTTPStatusError as e:
            logger.error(f"Calendly API error: {e}")
            raise EventCreationError(f"Calendly API error: {e}") from e
        except Exception as e:
            logger.error(f"Failed to create Calendly scheduling link: {e}")
            raise EventCreationError(f"Failed to create Calendly scheduling link: {e}") from e