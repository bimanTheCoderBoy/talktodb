class ScopeNotConfiguredError(Exception):
    """Raised when RLS is required but the user has no scoped cell IIDs."""

    def __init__(self, project_name: str, email: str) -> None:
        self.project_name = project_name
        self.email = email
        super().__init__(
            f"No scoped cell_iids configured for email={email!r} project={project_name!r}"
        )
