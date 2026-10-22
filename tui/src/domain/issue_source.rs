use crate::domain::errors::IssuesUnread;
use crate::domain::issue_text::IssueText;
use crate::domain::open_issue::OpenIssue;

pub trait IssueSource: Send {
    fn repo_of_directory(&mut self) -> Result<String, IssuesUnread>;

    fn latest_open(&mut self, repo: &str, limit: usize) -> Result<Vec<OpenIssue>, IssuesUnread>;

    fn body_of(&mut self, repo: &str, number: u64) -> Result<IssueText, IssuesUnread>;
}
