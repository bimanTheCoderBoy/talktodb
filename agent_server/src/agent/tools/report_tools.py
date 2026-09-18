from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from typing import List, Dict, Any, Optional, Annotated
from datetime import datetime
import pandas as pd
from pathlib import Path
import json
import asyncio
import aiofiles.os
import os
from langchain_core.messages import ToolMessage, AIMessage
from agent.config.coverage_config import CoverageReportConfig
from agent.utils.state import State
from langchain_core.tools import tool, InjectedToolCallId

config=CoverageReportConfig()


def _compute_coverage_summary(df: pd.DataFrame) -> Dict[str, Any]:
    """Compute summary stats, using overall coverage % (covered area / polygon area)."""
    summary: Dict[str, Any] = {
        "total_rows": len(df),
        "total_polygons": df["Polygon Name"].nunique() if "Polygon Name" in df.columns else 0,
        "columns": df.columns.tolist(),
    }

    if "COVERED AREA [SQKM]" in df.columns:
        df["COVERED AREA [SQKM]"] = pd.to_numeric(df["COVERED AREA [SQKM]"], errors="coerce")
        summary["total_covered_area_sqkm"] = float(df["COVERED AREA [SQKM]"].sum())

    if "Polygon Area [SQKM]" in df.columns:
        df["Polygon Area [SQKM]"] = pd.to_numeric(df["Polygon Area [SQKM]"], errors="coerce")
        if "Polygon Name" in df.columns:
            polygon_area = float(
                df.drop_duplicates(subset=["Polygon Name"])["Polygon Area [SQKM]"].sum()
            )
        else:
            polygon_area = float(df["Polygon Area [SQKM]"].iloc[0])
        summary["total_polygon_area_sqkm"] = polygon_area

        total_covered = summary.get("total_covered_area_sqkm", 0.0)
        if polygon_area > 0:
            summary["overall_coverage_percentage"] = (total_covered / polygon_area) * 100
            summary["uncovered_area_sqkm"] = max(0.0, polygon_area - total_covered)
            summary["uncovered_percentage"] = (summary["uncovered_area_sqkm"] / polygon_area) * 100

    return summary

async def get_report_folder_path() -> str:
    """
    Get the absolute path to the Report_Folder directory.
    
    This helper function retrieves the configured report folder path from the coverage configuration,
    ensures the directory exists (creates it if necessary), and returns the absolute path as a string.
    
    Returns:
        str: The absolute path to the Report_Folder directory. The directory is guaranteed to exist
             after this function returns (created if it didn't exist).
    """
    path=config.report_folder_path
    report_folder = Path(path)
    await aiofiles.os.makedirs(report_folder, exist_ok=True)
    return str(report_folder)


@tool("list_coverage_reports")
async def list_coverage_reports(state: Annotated[State, InjectedState]) -> Command:
    """
    List all coverage reports available in the Report_Folder directory.
    This tool scans the configured report folder and returns metadata about all available CSV coverage reports.
    
    ## How the tool works [Summary]
    This tool performs a read-only directory scan operation.
    1. It retrieves the configured Report_Folder path from the coverage configuration.
    2. It asynchronously lists all files in the directory.
    3. It filters for CSV files (case-insensitive, matching `.csv` extension).
    4. For each CSV file, it extracts metadata: filename, full path, file size (bytes and KB), and last modified timestamp.
    5. It sorts reports by modification date (newest first).
    6. It formats the results into a human-readable message with summary statistics.
    7. Returns a Command routing back to the master agent node with the tool message.
    
    ## Capabilities
    -   **Discovery**: Automatically discovers all coverage report CSV files in the configured directory.

    
    ## When to use
    -   When the user asks to "list", "show", or "find" available coverage reports.
    -   When the user wants to see what reports are available.
    -   When checking for recently generated reports.
    -   **NOT** for reading report contents (use `get_report_data` tool).
    -   **NOT** for querying or filtering report data (use `get_report_data` tool).
    
    ## NOTE:
    -   This tool only lists files with `.csv` extension (case-insensitive).
    -   Empty directories will return a message indicating no reports were found.
    -    No args are required for this tool.
    
    Args:
        
    
    Returns:
      list of dictionaries containing report information (filename, path, size, date)
        
    Examples:
        - list_coverage_reports() -> Returns formatted list of all available CSV reports with metadata
    """
    try:
        # Extract tool_call_id from previous AI message in main_message_context
        tool_call_id = None
        for msg in reversed(state.main_message_context):
            if isinstance(msg, AIMessage) and msg.tool_calls:
                tool_call_id = msg.tool_calls[0].get("id")
                break
        
        report_folder = await get_report_folder_path()
        
       
        reports = []
        # List directory (async)
        filenames = await aiofiles.os.listdir(report_folder)
        for filename in filenames:
            if filename.lower().endswith('.csv'):
                file_path = os.path.join(report_folder, filename)
                stat = await aiofiles.os.stat(file_path)
                reports.append({
                    'filename': filename,
                    'path': file_path,
                    'size_bytes': stat.st_size,
                    'size_kb': round(stat.st_size / 1024, 2),
                    'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
            
        reports.sort(key=lambda x: x['modified'], reverse=True)
        
        if len(reports) == 0:
            content = "No coverage reports found in the Report_Folder."
        else:
            content = f"Found {len(reports)} coverage report(s):\n\n"
            for i, report in enumerate(reports, 1):
                content += f"{i}. {report['filename']}\n"
                content += f"   Size: {report['size_kb']} KB\n"
                content += f"   Modified: {report['modified']}\n\n"
        
        # Create tool message
        tool_message = ToolMessage(
            content=content,
            tool_call_id=tool_call_id,
            name="list_coverage_reports",
            # artifact=json.dumps(reports)
        )
        
        # Return Command to route back to master agent
        return Command(
            goto="master_agent_node",
            update={
                "messages": [tool_message],
                "main_message_context": state.main_message_context + [tool_message]
            }
        )
        
    except Exception as e:
        error_message = f"Error listing reports: {str(e)}"
        tool_message = ToolMessage(
            content=error_message,
            tool_call_id=tool_call_id,
            name="list_coverage_reports"
        )
        
        return Command(
            goto="master_agent_node",
            update={
                "messages": [tool_message],
                "main_message_context": state.main_message_context + [tool_message]
            }
        )


@tool("get_report_data")
async def get_report_data(report_filename: Annotated[str, "Name of the report file (e.g., 'report_2025-01-01.csv'). Can be just the filename or full path"], state: Annotated["State", InjectedState], tool_call_id: Annotated[str, InjectedToolCallId]) -> Command:
    """
    Retrieve and parse data from a specific coverage report CSV file.
    This tool reads a coverage report CSV file, extracts all data, calculates summary statistics, and returns structured data suitable for visualization and analysis.
    
    ## How the tool works [Summary]
    This tool performs a read-only file operation with data processing.
    1. It accepts either a filename (searches in Report_Folder) or a full absolute path to the CSV file.
    2. It validates that the file exists before attempting to read it.
    3. It asynchronously reads the CSV file using pandas, handling large files efficiently.
    4. It calculates summary statistics including:
       - Total number of rows in the report
       - Total number of unique polygons
       - List of all column names
       - Total covered area in square kilometers (if available)
       - Overall coverage percentage: total covered area / total polygon area (if available)
       - Uncovered area and percentage (if available)
    5. It converts the dataframe to a list of dictionaries for easy JSON serialization.
    6. It creates both human-readable formatted content and structured JSON artifact.
    7. Returns the final result.
    
    
    ## When to use
    -   When the user asks to "view", "show", "get", or "read" a specific coverage report.
    -   When the user wants to see the contents of a report file.
    -   When preparing data for visualization or further analysis.
    -   When the user needs summary statistics about a coverage report.
    -   **NOT** for listing available reports (use `list_coverage_reports` tool).
    -   **NOT** for filtering or querying specific rows (this tool returns all data; filtering can be done after retrieval).
    
    Args:
        report_filename (str): Name of the report file to read. Can be provided in two formats:[Filename only (e.g., "report_2025-01-01.csv"): The tool will search in the configured Report_Folder,Full absolute path (e.g., "/path/to/report_2025-01-01.csv"): The tool will use the provided path directly]
       
    Returns:
        dictionary containing:
        - summary: Summary statistics
        - data: List of data rows
        - columns: Column names
        - filename: Report filename
        
    Examples:
        - get_report_data("report_2025-01-01.csv") -> Returns data from report_2025-01-01.csv in Report_Folder
        - get_report_data("/absolute/path/to/report.csv") -> Returns data from the specified absolute path
    """
    try:
        report_folder = await get_report_folder_path()
        
        # If full path provided, use it; otherwise look in report folder
        if os.path.isabs(report_filename) or os.path.dirname(report_filename):
            file_path = report_filename
        else:
            file_path = os.path.join(report_folder, report_filename)
        
        # Check if file exists (async)
        file_exists = await aiofiles.os.path.exists(file_path)
        if not file_exists:
            error_message = f"Report file not found: {report_filename}"
            tool_message = ToolMessage(
                content=error_message,
                tool_call_id=tool_call_id,
                name="get_report_data"
            )
            
            return Command(
                goto="master_agent_node",
                update={
                    "messages": [tool_message],
                    "main_message_context": state.main_message_context + [tool_message]
                }
            )
        
        # Read CSV file (async wrapper for blocking pd.read_csv)
        df = await asyncio.to_thread(pd.read_csv, file_path)
        
        # Calculate summary statistics
        summary = _compute_coverage_summary(df)
        
        # Convert dataframe to list of dictionaries
        data = df.fillna('').to_dict('records')
        
        # Create result dictionary
        result = {
            "summary": summary,
            "data": data,
            "columns": df.columns.tolist(),
            "filename": os.path.basename(file_path)
        }
        
        # Format human-readable content
        content = f"Report: {os.path.basename(file_path)}\n\n"
        content += f"Summary:\n"
        content += f"- Total rows: {summary['total_rows']}\n"
        if summary.get('total_polygons'):
            content += f"- Total polygons: {summary['total_polygons']}\n"
        if "total_covered_area_sqkm" in summary:
            content += f"- Total covered area: {summary['total_covered_area_sqkm']:.2f} sq km\n"
        if "total_polygon_area_sqkm" in summary:
            content += f"- Total polygon area: {summary['total_polygon_area_sqkm']:.2f} sq km\n"
        if "overall_coverage_percentage" in summary:
            content += f"- Overall coverage: {summary['overall_coverage_percentage']:.2f}%\n"
        if "uncovered_area_sqkm" in summary:
            content += (
                f"- Uncovered (<-120 dBm): {summary['uncovered_percentage']:.2f}% "
                f"({summary['uncovered_area_sqkm']:.2f} sq km)\n"
            )
        content += f"\nColumns: {', '.join(summary['columns'])}\n"
        
        # Create tool message
        tool_message = ToolMessage(
            content=content,
            tool_call_id=tool_call_id,
            name="get_report_data",
            artifact=json.dumps(result)
        )
        
        # Return Command to route back to master agent
        return Command(
            goto="master_agent_node",
            update={
                "messages": [tool_message],
                "main_message_context": state.main_message_context + [tool_message]
            }
        )
        
    except Exception as e:
        error_message = f"Error reading report: {str(e)}"
        tool_message = ToolMessage(
            content=error_message,
            tool_call_id=tool_call_id,
            name="get_report_data"
        )
        
        return Command(
            goto="master_agent_node",
            update={
                "messages": [tool_message],
                "main_message_context": state.main_message_context + [tool_message]
            }
        )

