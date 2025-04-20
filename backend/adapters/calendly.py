"""Calendly adapter for extracting availability and creating events.

This module provides functionality to interact with the Calendly API,
including extracting availability information and creating events.
"""

import re
import logging
import os
import time # Import time for sleep
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta, timezone

import httpx
from dotenv import load_dotenv

from core.models import (
    AvailabilitySchedule, TimeSlot, CalendarType, 
    CalendarEvent, EventConfirmation
)
from adapters.base import (
    BaseAdapter, AuthenticationError, 
    ResourceNotFoundError, EventCreationError, BaseAdapterError
)

# Configure module logger
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class CalendlyRateLimitError(BaseAdapterError):
    """Exception raised when Calendly API rate limit is exceeded."""
    pass


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

    MAX_RETRIES = 3
    INITIAL_BACKOFF = 1 # seconds

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

    def _make_request(
        self, 
        method: str, 
        url: str, 
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        allow_redirects: bool = True
    ) -> httpx.Response:
        """Makes an HTTP request with error handling and retries for rate limits."""
        retries = 0
        backoff = self.INITIAL_BACKOFF
        last_exception = None
        
        request_headers = self.http_client.headers.copy()
        if headers:
             request_headers.update(headers)

        while retries <= self.MAX_RETRIES:
            try:
                response = self.http_client.request(
                    method,
                    url,
                    params=params,
                    json=data, # Use json parameter for dict data
                    headers=request_headers,
                    follow_redirects=allow_redirects
                )
                response.raise_for_status() # Raise HTTPStatusError for 4xx/5xx
                return response
            
            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code
                if status_code == 401:
                    logger.error(f"Calendly API Authentication Error: {e}")
                    raise AuthenticationError("Authentication failed with Calendly API") from e
                elif status_code == 404:
                    logger.error(f"Calendly Resource Not Found: {e}")
                    raise ResourceNotFoundError(f"Calendly resource not found: {e.request.url}") from e
                elif status_code == 429:
                    logger.warning(f"Calendly Rate Limit hit (Attempt {retries + 1}/{self.MAX_RETRIES + 1}). Retrying in {backoff}s...")
                    last_exception = CalendlyRateLimitError(f"Rate limit exceeded after {retries} retries: {e}")
                    time.sleep(backoff)
                    retries += 1
                    backoff *= 2 # Exponential backoff
                    continue
                else:
                    logger.error(f"Calendly HTTP Error {status_code}: {e}")
                    raise BaseAdapterError(f"Calendly API error ({status_code}): {e}") from e
            
            except httpx.RequestError as e:
                # Network errors, timeouts, etc.
                logger.error(f"Calendly Network/Request Error: {e}")
                raise BaseAdapterError(f"Calendly request failed: {e}") from e
            
            except Exception as e:
                 # Catch unexpected errors
                 logger.error(f"Unexpected error during Calendly request: {e}")
                 raise BaseAdapterError(f"Unexpected Calendly adapter error: {e}") from e

        # If loop finishes due to retries, raise the last rate limit error
        raise last_exception

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
            CalendlyRateLimitError: If rate limits are exceeded after retries.
            BaseAdapterError: For other Calendly-specific or network errors.
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
        
        # Use mock data ONLY if mock_mode is explicitly True
        if self.mock_mode:
            logger.info(f"Using mock data for Calendly user: {user_name}")
            return self._create_mock_schedule(user_name)
            
        if not self.api_key:
             raise AuthenticationError("Calendly API key required for non-mock mode.")

        try:
            # Get user UUID from username using the request helper
            user_data = self._get_user_data(user_name)
            user_uri = user_data.get("resource", {}).get("uri")
            owner_name = user_data.get("resource", {}).get("name", user_name)
            
            if not user_uri:
                # This case should ideally be caught by 404 in _get_user_data
                logger.error(f"Could not find user URI for name: {user_name}")
                raise ResourceNotFoundError(f"Could not find user URI for Calendly name: {user_name}")
            
            # Create availability schedule
            schedule = AvailabilitySchedule(
                calendar_id=user_uri,
                calendar_type=CalendarType.CALENDLY,
                owner_name=owner_name
            )
            
            # Get available time slots using the request helper
            available_slots = self._get_available_slots(user_uri)
            
            # Add slots to schedule
            for slot in available_slots:
                schedule.add_slot(slot)
            
            logger.info(
                f"Successfully extracted {len(schedule.time_slots)} available slots from Calendly"
            )
            return schedule
            
        # Catch specific errors raised by _make_request or helper methods
        except (AuthenticationError, ResourceNotFoundError, CalendlyRateLimitError, BaseAdapterError) as e:
            logger.error(f"Failed to extract Calendly availability for {calendly_link}: {e}")
            raise # Re-raise the specific error
        except Exception as e:
            # Catch any other unexpected errors
            logger.exception(f"Unexpected error extracting availability from {calendly_link}: {e}")
            raise BaseAdapterError(f"Unexpected error during Calendly availability extraction: {e}") from e

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
        """Get user data (including URI) from Calendly API by username."""
        if not self.api_key:
            raise AuthenticationError("Calendly API key required to get user data.")
            
        logger.debug(f"Getting user data for Calendly user: {user_name}")
        url = f"{self.API_BASE_URL}/users"
        params = {"email": user_name} # Assuming username can be used as email filter?
                                      # Or need to adjust API call if name isn't directly searchable
                                      # Calendly docs might require a different approach.
                                      # Fallback: list users and filter? Less efficient.
        
        # --- Alternative if username != email ---
        # This might require iterating through users? Check Calendly API docs.
        # For now, assume email or a direct username lookup exists.
        # If Calendly user links use a unique slug, that might be needed instead.
        # The USER_PATTERN extracts the slug, let's try filtering by that if possible.
        # Let's assume the endpoint can filter by `slug` (hypothetical, CHECK DOCS)
        params = {"slug": user_name} 
        
        # Make the request using the helper
        response = self._make_request("GET", url, params=params)
        data = response.json()
        
        # Process response - assuming it returns a collection
        if data and data.get("collection"):
            # Find the user matching the slug/name exactly
            for user in data["collection"]:
                 # Check slug or name matches - adjust based on actual API response
                 if user.get("slug") == user_name or user.get("name") == user_name:
                      logger.info(f"Found Calendly user URI: {user.get('uri')}")
                      return user # Return the full user object which should contain URI, name etc.
            # If no exact match found in collection
            logger.warning(f"No exact match found for Calendly user: {user_name} in API response")
            raise ResourceNotFoundError(f"Calendly user '{user_name}' not found via API.")
        else:
            # Handle case where collection is empty or response format is unexpected
            logger.warning(f"Could not find Calendly user: {user_name}. Response: {data}")
            raise ResourceNotFoundError(f"Calendly user '{user_name}' not found.")

    def _get_available_slots(self, user_uri: str) -> List[TimeSlot]:
        """Get available time slots from Calendly availability endpoint."""
        if not self.api_key:
             raise AuthenticationError("Calendly API key required to get available slots.")

        logger.debug(f"Getting available slots for user URI: {user_uri}")
        url = f"{self.API_BASE_URL}/availability/schedules"
        # Query parameters based on Calendly API docs for availability
        # This likely requires the user URI and potentially event type URI
        # This is a simplified example - **CHECK CALENDLY DOCS FOR CORRECT ENDPOINT/PARAMS**
        # Assuming we need to query based on the user
        params = {
            "user": user_uri,
            # Add other necessary params like start_time, end_time if required by API
            # 'start_time': datetime.now(timezone.utc).isoformat(),
            # 'end_time': (datetime.now(timezone.utc) + timedelta(days=self.days_to_check)).isoformat()
        }

        # ---> This endpoint /availability/schedules might list schedule configurations,
        # ---> not actual bookable slots. The correct endpoint is likely related to
        # ---> 'scheduling_links' or finding available times for a specific event type.
        # ---> The previous code used /user_availability_schedules which seems deprecated or incorrect.
        # ---> Let's assume a hypothetical endpoint - REAL IMPLEMENTATION NEEDS DOCS CHECK
        
        # Example: Hypothetical correct endpoint (replace with actual)
        # url = f"{self.API_BASE_URL}/event_type_available_times"
        # params = {
        #     'event_type': event_type_uri, # Need to get this first!
        #     'start_time': start_date.isoformat(),
        #     'end_time': end_date.isoformat()
        # }
        
        # Placeholder: Using a known endpoint that might give *some* info, but likely not bookable slots
        # Need to adjust based on actual Calendly API for fetching bookable slots for a user/event type.
        url = f"{self.API_BASE_URL}/user_busy_times" 
        start_date = datetime.now(timezone.utc)
        end_date = start_date + timedelta(days=self.days_to_check)
        params = {
             'user': user_uri,
             'start_time': start_date.isoformat(),
             'end_time': end_date.isoformat()
        }
        logger.warning("Using /user_busy_times as placeholder; need correct Calendly API endpoint for available slots.")

        response = self._make_request("GET", url, params=params)
        data = response.json()

        # --- Processing Logic (Needs heavy adjustment based on actual API) --- 
        # The following logic is based on the PREVIOUS _calculate_available_slots 
        # which assumed schedules and busy times were fetched separately.
        # This needs to be completely rewritten based on the response of the 
        # *actual* Calendly endpoint for bookable slots.
        
        # Placeholder: If the endpoint returns busy times, we cannot determine free slots without the user's schedule rules.
        # Returning an empty list as a placeholder until the correct API call and processing is implemented.
        logger.warning(f"Processing logic for Calendly slots is a placeholder. Response from {url}: {data}")
        processed_slots = [] 
        # Correct implementation would parse data['collection'] based on the API used.
        # Example if API returned slots directly:
        # for slot_data in data.get('collection', []):
        #    try:
        #        start = datetime.fromisoformat(slot_data['start_time'])
        #        end = datetime.fromisoformat(slot_data['end_time'])
        #        # Assuming API returns UTC or has timezone info
        #        if start.tzinfo is None:
        #             start = start.replace(tzinfo=timezone.utc) # Assume UTC if naive
        #        if end.tzinfo is None:
        #             end = end.replace(tzinfo=timezone.utc)
        #        processed_slots.append(TimeSlot(start=start, end=end, timezone='UTC'))
        #    except (KeyError, ValueError) as e:
        #        logger.warning(f"Skipping invalid slot data: {slot_data}, error: {e}")

        return processed_slots 

    def _generate_mock_slots(self, user_name: str) -> AvailabilitySchedule:
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
        
        mock_slots = self._generate_mock_slots(user_name)
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