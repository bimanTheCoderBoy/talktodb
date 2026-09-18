"""
Async utility functions for coverage API calls.
"""

import json
import os
import asyncio
from pathlib import Path
from typing import Dict, Any
import aiofiles
import httpx

from agent.utils.state import CoverageUrlConfig
from agent.config.coverage_config import CoverageAPIConfig
from agent import apiclient
from urllib.parse import urlencode, quote, quote_plus
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def load_config(file_path: str) -> Dict[str, Any]:
    """
    Load configuration from a JSON file.
    
    Args:
        file_path: Path to the configuration JSON file
        
    Returns:
        Dictionary containing the configuration
    """
    async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
        content = await f.read()
        return json.loads(content)


async def send_post_request(url: str, headers: Dict[str, str], payload: Dict[str, Any]) -> httpx.Response:
    """
    Send an async POST request to the API with the provided payload.
    
    Uses the global API client with connection reuse and retry logic.
    
    Args:
        url: API endpoint URL
        headers: Request headers dictionary
        payload: JSON payload to send
        
    Returns:
        Response object from the API
    """
    response = await apiclient.post(url, headers=headers, json=payload)
    print('Response Status Code:', response.status_code)
    print('Response Content:', response.text)
    return response


async def load_payload_from_json(file_path: str) -> Dict[str, Any]:
    """
    Load JSON payload from a file.
    
    Args:
        file_path: Path to the JSON payload file
        
    Returns:
        Dictionary containing the JSON payload
    """
    async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
        content = await f.read()
        return json.loads(content)


async def update_cell_object(config: Dict[str, Any], json_file_path: str) -> httpx.Response:
    """
    Update the cell object using the payload from the JSON file.
    
    Args:
        config: Configuration dictionary containing 'url' and 'headers'
        json_file_path: Path to the JSON payload file
        
    Returns:
        Response object from the API
        
    Raises:
        ValueError: If config is missing required fields
        FileNotFoundError: If the JSON file doesn't exist
        json.JSONDecodeError: If the JSON file is invalid
    """
    url = config.get('url')
    headers = config.get('headers')

    if not url or not headers:
        raise ValueError("Configuration must include 'url' and 'headers'.")

    # Load the payload from the JSON file
    payload = await load_payload_from_json(json_file_path)
    
    # Send the request
    response = await send_post_request(url, headers, payload)
    return response


async def get_latest_json_file(export_folder: str = "Rest_CWE") -> str:
    """
    Retrieve the latest JSON file from the export folder.
    
    Args:
        export_folder: Folder containing the JSON files (default: "Rest_CWE")
        
    Returns:
        Full path to the latest JSON file
        
    Raises:
        FileNotFoundError: If no JSON files are found in the export folder
    """
    json_files = await asyncio.to_thread(lambda: list(Path(export_folder).glob("CWE*.json")))
    if not json_files:
        raise FileNotFoundError(f"No JSON files found in the export folder: {export_folder}")
    
    # Run blocking os.path.getctime in thread pool to avoid blocking event loop
    async def _get_ctime(file_path):
        return await asyncio.to_thread(os.path.getctime, file_path)
    
    # Get creation times for all files in parallel
    ctime_tasks = [_get_ctime(str(f)) for f in json_files]
    ctimes = await asyncio.gather(*ctime_tasks)
    
    # Find file with max creation time
    latest_file = json_files[ctimes.index(max(ctimes))]
    return str(latest_file)


async def coverage_api_call(coverage_url_config: CoverageUrlConfig, project_name: str, payload_file_path: str | None = None) -> httpx.Response:
    """
    Main function to call the coverage API.
    
    This function:
    1. Loads the configuration from CoverageAPIConfig
    2. Gets the latest JSON payload file from Rest_CWE folder
    3. Sends the POST request to update the cell object
    
    Returns:
        Response object from the API
        
    Raises:
        FileNotFoundError: If config file or payload file is not found
        ValueError: If configuration is invalid
        httpx.RequestError: If the API call fails
    """
    # Load config from config class
    api_config = CoverageAPIConfig()
    export_folder = api_config.payload_store
    
    # URL level config data
    base_coverage_api_url = api_config.create_coverage_endpoint
    project=quote(project_name)
    technology=quote(coverage_url_config.technology)
    resolution=quote(coverage_url_config.resolution)
    mode=quote(coverage_url_config.mode)
    terminal=quote(coverage_url_config.terminal)
    autoApprove=str(coverage_url_config.autoApprove).lower()
    url = f"{base_coverage_api_url}?project={project}&technology={technology}&resolution={resolution}&mode={mode}&terminal={terminal}&autoApprove={autoApprove}"
    if coverage_url_config.height:
        height=quote(coverage_url_config.height)
        url += f"&height={height}"
    if coverage_url_config.carrier:
        carrier=quote(coverage_url_config.carrier)
        url += f"&carrier={carrier}"
    
    logger.info(f"Coverage API URL: {url}")
    config ={
        "url": url,
        "headers": {
        "Content-Type": "application/json-patch+json",
        "Accept": "text/plain",
        "api-key": api_config.api_key
    }
    }
    
   
    # Use explicit payload file if provided, otherwise fall back to latest
    if payload_file_path:
        json_file = payload_file_path
    else:
        json_file = await get_latest_json_file(export_folder)
    
    print(f"Using payload file: {json_file}")
    
    # Update cell object via API
    response = await update_cell_object(config, json_file)
    
    return response
