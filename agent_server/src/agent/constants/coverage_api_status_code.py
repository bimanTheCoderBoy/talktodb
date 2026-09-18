workflow_status = {
    "pending": "workflow is registered but not started yet",
    "fetching": "data querying to the EDS service is in progress",
    "verifying": "all retrieved data is being checked for errors or missing information",
    "generating": "construction of CGA requests in progress",
    "awaitingApproval": "indicates workflow is paused pending approval",
    "issuing": "transmission of CGA requests in progress",
    "processing": "waiting for CGA to complete its work but processing it’s notifications as they occur to provide update notifications to CWE clients",
    "cancelling": "workflow has been requested to abort at next available check point",
    "cancelled": "workflow was successfully cancelled at the stage it received the command at (finalization value)",
    "partial": "workflow completed with at least one task succeeding but one or more failed tasks (finalization value)",
    "failed": "all tasks in the workflow failed (finalization value)",
    "completed": "workflow completed successfully (finalization value)",
}
