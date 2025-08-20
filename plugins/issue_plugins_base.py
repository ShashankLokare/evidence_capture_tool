class IssuePluginBase:
    """Base class for issue tracker integrations."""
    def __init__(self, **kwargs):
        pass

    def create_issue(self, title: str, description: str, severity: str, attachments: list[str] | None = None):
        raise NotImplementedError
