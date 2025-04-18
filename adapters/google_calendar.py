"""Google Calendar adapter for extracting availability information.

This module provides functionality to extract availability information from
Google Calendar links using the Google Calendar API.
"""

import re
import logging
import os
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone
import json

import httpx
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv

from core.models import AvailabilitySchedule, TimeSlot, CalendarType


# Configure module logger
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class GoogleCalendarAdapter:
    """Adapter for extracting availability information from Google Calendar links.
    
    This adapter uses the Google Calendar API to extract availability information
    about when a user is free/busy.
    """
    
    # Regex pattern to extract calendar ID from Google Calendar links
    CALENDAR_ID_PATTERN = r'calendar/([^/]+)(?:/([^/]+))?'
    
    # Google Calendar API scopes needed
    SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
    
    def __init__(
        self, 
        service_account_file: Optional[str] = None,
        credentials_file: Optional[str] = None,
        token_file: Optional[str] = None
    ):
        """Initialize the Google Calendar adapter.
        
        Args:
            service_account_file: Path to service account JSON key file.
                If not provided, will try to load from GOOGLE_SA_KEY_FILE env var.
            credentials_file: Path to OAuth client credentials file.
                If not provided, will try to load from GOOGLE_CREDENTIALS_FILE env var.
            token_file: Path to OAuth token file for cached credentials.
                If not provided, defaults to 'token.json' in current directory.
        """
        self.service_account_file = service_account_file or os.getenv("GOOGLE_SA_KEY_FILE")
        self.credentials_file = credentials_file or os.getenv("GOOGLE_CREDENTIALS_FILE")
        self.token_file = token_file or "token.json"
        
        self.service = None
        self._authenticate()
    
    def _authenticate(self) -> None:
        """Authenticate with Google Calendar API.
        
        This method attempts to authenticate with Google Calendar API using either:
        1. Service account credentials (if available)
        2. OAuth 2.0 credentials (if available)
        3. Falls back to a mock mode if neither is available
        
        Authentication is determined by which credential files are available.
        """
        creds = None
        
        try:
            # Attempt to use service account if file is provided
            if self.service_account_file and os.path.exists(self.service_account_file):
                logger.info(f"Using service account from {self.service_account_file}")
                creds = service_account.Credentials.from_service_account_file(
                    self.service_account_file, scopes=self.SCOPES
                )
            
            # Otherwise try OAuth flow (for development/testing)
            elif self.credentials_file and os.path.exists(self.credentials_file):
                logger.info(f"Using OAuth credentials from {self.credentials_file}")
                # Check if we have a cached token
                if os.path.exists(self.token_file):
                    creds = Credentials.from_authorized_user_file(self.token_file, self.SCOPES)
                
                # If there are no valid credentials available, let the user log in
                if not creds or not creds.valid:
                    if creds and creds.expired and creds.refresh_token:
                        creds.refresh(Request())
                    else:
                        flow = InstalledAppFlow.from_client_secrets_file(
                            self.credentials_file, self.SCOPES
                        )
                        creds = flow.run_local_server(port=0)
                    
                    # Save the credentials for the next run
                    with open(self.token_file, "w") as token:
                        token.write(creds.to_json())
            
            # If credentials are available, build the service
            if creds:
                self.service = build("calendar", "v3", credentials=creds)
                logger.info("Successfully authenticated with Google Calendar API")
            else:
                logger.warning(
                    "No Google Calendar API credentials available, running in mock mode"
                )
                self.service = None
                
        except Exception as e:
            logger.error(f"Error authenticating with Google Calendar API: {e}")
            self.service = None
    
    def extract_availability(self, calendar_link: str) -> AvailabilitySchedule:
        """Extract availability information from a Google Calendar link.
        
        Args:
            calendar_link: The Google Calendar link to extract availability from.
            
        Returns:
            An AvailabilitySchedule object with the extracted time slots.
            
        Raises:
            ValueError: If the Google Calendar link format is invalid.
            httpx.HTTPError: If there's an error communicating with Google Calendar API.
        """
        logger.info(f"Extracting availability from Google Calendar link: {calendar_link}")
        
        # Extract calendar ID from the link
        calendar_id = self._extract_calendar_id(calendar_link)
        
        if not calendar_id:
            raise ValueError(f"Invalid Google Calendar link format: {calendar_link}")
        
        try:
            # Create availability schedule
            schedule = AvailabilitySchedule(
                calendar_id=calendar_id,
                calendar_type=CalendarType.GOOGLE,
                owner_name=self._get_calendar_name(calendar_id)
            )
            
            # Get available time slots
            if self.service:
                # If we have an authenticated API client, use it
                available_slots = self._get_available_slots_api(calendar_id)
            else:
                # Otherwise use mocked data
                available_slots = self._mock_available_slots()
            
            # Add slots to schedule
            for slot in available_slots:
                schedule.add_slot(slot)
            
            logger.info(
                f"Successfully extracted {len(schedule.time_slots)} available time slots"
            )
            return schedule
            
        except HttpError as e:
            logger.error(f"Google Calendar API error: {e}")
            raise
        except Exception as e:
            logger.error(f"Error extracting availability from Google Calendar: {e}")
            raise
    
    def _extract_calendar_id(self, calendar_link: str) -> str:
        """Extract calendar ID from a Google Calendar link.
        
        Args:
            calendar_link: The Google Calendar link to extract from.
            
        Returns:
            The calendar ID as a string, or empty string if not found.
        """
        match = re.search(self.CALENDAR_ID_PATTERN, calendar_link)
        
        if not match:
            return ""
            
        # The first capture group should be the calendar ID
        calendar_id = match.group(1)
        
        # Some calendar links use URL encoding for special characters
        calendar_id = calendar_id.replace("%40", "@")
        
        logger.debug(f"Extracted calendar_id={calendar_id}")
        return calendar_id
    
    def _get_calendar_name(self, calendar_id: str) -> Optional[str]:
        """Get the name of a Google Calendar.
        
        Args:
            calendar_id: The Google Calendar ID.
            
        Returns:
            The calendar name or None if not available.
        """
        if not self.service:
            # In mock mode, just use the calendar ID as the name
            return calendar_id
            
        try:
            # Get calendar metadata
            calendar = self.service.calendars().get(calendarId=calendar_id).execute()
            return calendar.get("summary")
        except HttpError as e:
            logger.warning(f"Could not get calendar name: {e}")
            return None
    
    def _get_available_slots_api(self, calendar_id: str) -> List[TimeSlot]:
        """Get available time slots using the Google Calendar API.
        
        This method uses the FreeBusy API to get busy periods and then
        calculates available slots based on working hours.
        
        Args:
            calendar_id: The Google Calendar ID.
            
        Returns:
            List of TimeSlot objects representing available times.
        """
        # Define time range - next 7 days
        now = datetime.now(timezone.utc)
        start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = start_time + timedelta(days=7)
        
        # Define working hours (9 AM to 5 PM)
        working_start_hour = 9
        working_end_hour = 17
        
        # Query for busy times
        body = {
            "timeMin": start_time.isoformat(),
            "timeMax": end_time.isoformat(),
            "timeZone": "UTC",
            "items": [{"id": calendar_id}]
        }
        
        try:
            # Call the FreeBusy API
            freebusy_response = self.service.freebusy().query(body=body).execute()
            
            # Extract busy periods
            busy_periods = freebusy_response.get("calendars", {}).get(calendar_id, {}).get("busy", [])
            
            # Convert to busy slots
            busy_slots = []
            for period in busy_periods:
                start_str = period.get("start")
                end_str = period.get("end")
                
                if start_str and end_str:
                    # Convert ISO strings to datetime objects
                    start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                    end = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                    
                    busy_slots.append((start, end))
            
            # Generate available slots based on working hours minus busy periods
            available_slots = []
            
            # For each day in the range
            for day_offset in range(7):
                day = start_time + timedelta(days=day_offset)
                
                # Skip weekends (5=Saturday, 6=Sunday)
                if day.weekday() >= 5:
                    continue
                
                # Define working hours for this day
                day_start = day.replace(hour=working_start_hour, minute=0)
                day_end = day.replace(hour=working_end_hour, minute=0)
                
                # Skip days in the past
                if day_end < now:
                    continue
                
                # Create 30-minute slots and check if they're available
                current = max(day_start, now.replace(minute=0, second=0, microsecond=0))
                
                while current < day_end:
                    slot_end = current + timedelta(minutes=30)
                    
                    # Check if this slot overlaps with any busy period
                    is_available = True
                    for busy_start, busy_end in busy_slots:
                        if current < busy_end and slot_end > busy_start:
                            is_available = False
                            break
                    
                    if is_available:
                        available_slots.append(TimeSlot(
                            start=current,
                            end=slot_end,
                            timezone="UTC"
                        ))
                    
                    current = slot_end
            
            logger.info(f"Found {len(available_slots)} available slots via API")
            return available_slots
            
        except HttpError as e:
            logger.error(f"FreeBusy API error: {e}")
            # Fall back to mock data if API call fails
            return self._mock_available_slots()
    
    def _mock_available_slots(self) -> List[TimeSlot]:
        """Generate mock available time slots.
        
        Used when real API access is not available.
        
        Returns:
            List of TimeSlot objects representing mocked available times.
        """
        slots = []
        
        # Get current date/time
        now = datetime.now(timezone.utc)
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Create example time slots for the next 7 days
        for day_offset in range(7):
            day = today + timedelta(days=day_offset)
            
            # Skip weekends (5=Saturday, 6=Sunday)
            if day.weekday() >= 5:
                continue
                
            # Add business hours slots (9AM-5PM)
            for hour in range(9, 17):
                # Create a 30-minute slot
                start_time = day.replace(hour=hour, minute=0)
                end_time = day.replace(hour=hour, minute=30)
                
                # Skip slots in the past
                if end_time <= now:
                    continue
                
                slots.append(TimeSlot(
                    start=start_time,
                    end=end_time,
                    timezone="UTC"
                ))
                
                # Add the second half-hour slot
                start_time = day.replace(hour=hour, minute=30)
                end_time = day.replace(hour=hour + 1, minute=0)
                
                # Skip slots in the past
                if end_time <= now:
                    continue
                
                slots.append(TimeSlot(
                    start=start_time,
                    end=end_time,
                    timezone="UTC"
                ))
        
        # Log the number of slots created
        logger.info(f"Created {len(slots)} mock time slots")
        
        return slots