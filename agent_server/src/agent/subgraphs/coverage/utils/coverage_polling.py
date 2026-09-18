"""
Async utility functions for polling coverage API status.
"""

from datetime import datetime
from typing import Dict, Any, Optional, Tuple
import httpx

from agent.constants.coverage_api_status_code import workflow_status
from agent.config.coverage_config import CoverageAPIConfig
from agent import apiclient
from agent.apiclient import RetryableHTTPError


def parse_timestamp(timestamp: str) -> datetime:
    """
    Parse the timestamp, handling 6 and 7 fractional seconds, with or without 'Z' suffix.
    
    Args:
        timestamp: ISO format timestamp string
        
    Returns:
        Parsed datetime object
        
    Raises:
        ValueError: If timestamp cannot be parsed
    """
    original_timestamp = timestamp
    
    try:
        # Check if the timestamp has more than 6 fractional digits
        # Handle timestamps with 'Z' suffix: '2024-11-19T08:12:53.7144579Z' (27 chars with 7 digits)
        # Handle timestamps without 'Z': '2025-10-31T13:06:06.898699' (26 chars with 6 digits)
        
        has_z_suffix = timestamp.endswith('Z')
        
        if has_z_suffix:
            # Timestamp with 'Z' suffix
            if len(timestamp) > 27:  # More than 6 fractional digits + Z
                timestamp = timestamp[:26] + 'Z'  # Trim to 26 chars + Z (6 digits after decimal)
            return datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%fZ")
        else:
            # Timestamp without 'Z' suffix
            if len(timestamp) > 26:  # More than 6 fractional digits
                timestamp = timestamp[:26]  # Trim to 26 chars (6 digits after decimal)
            return datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%f")
    
    except ValueError as e:
        # Handle the case where the format doesn't match (possibly due to unexpected precision)
        raise ValueError(f"Failed to parse timestamp '{original_timestamp}': {e}")


async def check_coverage_status(token: str, url: str = None, headers: Dict[str, str] = None) -> Tuple[int, str, Optional[Dict[str, Any]]]:
    """
    Check the coverage API status and return the status code, message, and work item.
    
    Args:
        token: API token for the coverage job
        url: API endpoint URL. If None, uses default from config
        headers: Request headers. If None, uses default headers from config
        
    Returns:
        Tuple of (run_code: int, status_message: str, work_item: dict or None)
        - run_code: 0=in progress, 1=completed/partial, 2=failed/cancelled/error
        - status_message: Human-readable status message
        - work_item: Work item data from API or None
    """
    # Load config from config class
    api_config = CoverageAPIConfig()
    
    # Default values from config
    if url is None:
        endpoint = api_config.status_polling_endpoint
        url = f"{endpoint}{token}"
    
    if headers is None:
        headers = {
            'accept': 'application/json',
            'api-key': api_config.api_key
        }
    
    try:
        # Making the async request to the API using the global client with retry logic
        response = await apiclient.get(url, headers=headers)
        data = response.json()

        # Check the status of the first work item
        if data.get('item'):
            work_item = data['item']
            status = work_item.get('status', '')
            status_lower = status.lower()

            # Check if the coverage is 100% complete
            if status_lower == "completed" or status_lower == "partial":
                status_msg = workflow_status.get(status_lower, f"Status: {status}")
                return 1, f" {status_lower}: {status_msg}", work_item
            elif status_lower == "cancelled" or status_lower == "failed":
                status_msg = workflow_status.get(status_lower, f"Status: {status}")
                return 2, f" {status_lower}: {status_msg}", work_item
            else:
                # Handle any status not explicitly checked above (pending, fetching, etc.)
                status_msg = workflow_status.get(status_lower, f"Status: {status}")
                return 0, f" {status_lower}: {status_msg}", work_item
        else:
            # No work item found in response
            return 0, f"No work item found in response token:{data}", None
            
    except RetryableHTTPError as e:
        print(f"API request failed after {e.attempts} attempts: {e.last_error}")
        return 2, f"Error: {e}", None
    except httpx.RequestError as e:
        print(f"Error during API request: {e}")
        return 2, f"Error: {e}", None
    except Exception as e:
        print(f"Error during status check: {e}")
        return 2, f"Error: {e}", None

