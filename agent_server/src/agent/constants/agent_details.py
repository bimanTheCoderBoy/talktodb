from .prompt_registry.master_agent_prompt import master_agent_system_prompt

agents_details = [
    {
        "name": "master_agent",
        "description": master_agent_system_prompt.template,
        
    },
    {
        "name": "run_coverage_agent",
        "description": """
        ### IT IS A HANDOFF TOOL
        Transfer task execution to the Run Coverage Agent for telecom network coverage analysis.
        This tool hands off control to a specialized agent that orchestrates the complete coverage analysis workflow,
        from gathering cell information to generating coverage reports and visualizations.
        
        ## How the Coverage Agent Works [Summary]
        The Run Coverage Agent is a specialized autonomous agent that executes end-to-end network coverage analysis.
        It Receives the task description from the master agent and initializes coverage state. Generates a SQL query to get the cell IIDs based on the user request.
        Executes the SQL query and gets the results. Creates a map of the cells and the boundaries. Displays the map to the user and the user can approve or reject the map.
        Performs the coverage analysis. Returns the coverage analysis result like a Tool Result.
        
        ## When to use
        -   When the user's intent is to "run", "check", "analyze", or "get" network coverage
        -   **NOT** for viewing existing reports (use `list_coverage_reports` or `get_report_data` tools)
        -   **NOT** for simple data queries (use database agent tools)
        
        *NOTE: For this Tool calling , if you are seeing the user's intent is to run coverage analysis then call this tool directly , don't ask for clarification unless the tool output ask for it.*
        If Tools Output ask for clarification then call only ask that clarification question and then when user provide the clarification then call this tool again to with the clarification answer message from user as it is.

        
        Args:
            handoff_message (str): User's coverage analysis intent (what user want to do, whole context not like: user said 'try again' but the intent is run coverage for what user asked previously so here give the whole context) as it is / clarification answer message from user as it is. 
        
        Returns:
            Text: A Text containing the coverage analysis result if success / error message if failed/ Clarification message if needed.

        """,
        
    },
    {
        "name": "ask_human",
        "description": """
        Pause execution to request clarification or approval from the human user.

        ## How the tool works [Summary]
        This tool interrupts the automated agent flow and presents a message to the user in the chat interface.
        1.  It takes a text `message` from the agent.
        2.  It halts the agent's execution.
        3.  It waits for the user to type a response.
        4.  The user's response is then fed back to the agent as the result of this tool call.

        ## Capabilities
        -   **Clarification**: Ask for missing details (e.g., "Which region do you mean?").
        -   **Scope Check**: Verify intent if a request is ambiguous.

        ## When to use
        -   **Ambiguity**: When a query is too vague (e.g., "Show me the cells"). You are not sure about region, site/tower IIDs to get the Cell IIDs by calling `get_cell_iids` tool.
        -   **Safety**: When the agent got empty or error in calling `get_cell_iids` tool and can not solve by own.

        Args:
            detail_task (str): The question or statement to present to the user. Be polite and specific.

        Returns:
            Command: A control flow command that pauses execution (handled by the system).
        """,
    }

]