from .issue_plugins_base import IssuePluginBase

class JiraPlugin(IssuePluginBase):
    """Stub only. Fill in JIRA REST calls using your domain and credentials."""
    def __init__(self, base_url: str = "", user: str = "", token: str = "", project_key: str = ""):
        super().__init__()
        self.base_url = base_url
        self.user = user
        self.token = token
        self.project_key = project_key

    def create_issue(self, title: str, description: str, severity: str, attachments=None):
        return {"status": "stub", "issue_key": "JIRA-000"}
