use std::sync::Arc;
use std::time::Duration;

use crate::domain::clock::Clock;
use crate::domain::errors::IssuesUnread;
use crate::domain::issue_source::IssueSource;
use crate::domain::issue_text::IssueText;
use crate::domain::open_issue::OpenIssue;
use crate::infrastructure::bounded_run::{BoundedRun, RunFailure, RunOutput};
use crate::infrastructure::child_launcher::{ChildExit, ChildLauncher, Input, Launch, Stream};
use crate::infrastructure::issue_body_payload::IssueBodyPayload;
use crate::infrastructure::open_issues_payload::OpenIssuesPayload;
use crate::infrastructure::repo_view_payload::RepoViewPayload;

pub struct BoundedGhProcess {
    run: BoundedRun,
}

impl BoundedGhProcess {
    pub fn new(
        program: Vec<String>,
        launcher: Arc<dyn ChildLauncher>,
        clock: impl Clock + 'static,
        budget: Duration,
    ) -> Self {
        Self {
            run: BoundedRun::new(program, launcher, clock, budget),
        }
    }

    fn answer_of(&self, arguments: &[&str]) -> Result<String, IssuesUnread> {
        self.run
            .run(arguments, &Launch::new(Input::Empty, Stream::Read, Stream::Read))
            .map_err(|failure| self.unread(failure))
            .and_then(|output| Self::interpreted(&output))
    }

    fn unread(&self, failure: RunFailure) -> IssuesUnread {
        match failure {
            RunFailure::NotLaunched { reason } | RunFailure::Failed { reason } => Self::failed(&reason),
            RunFailure::TimedOut => IssuesUnread::TimedOut {
                budget: self.run.budget(),
            },
        }
    }

    fn interpreted(output: &RunOutput) -> Result<String, IssuesUnread> {
        match output.exit() {
            ChildExit::Code(0) => Ok(output.stdout().to_string()),
            ChildExit::Code(code) if output.stderr().trim().is_empty() => {
                Err(Self::failed(&format!("exited with code {code}")))
            }
            ChildExit::Code(_) => Err(Self::failed(output.stderr().trim())),
            ChildExit::Signal => Err(Self::failed("terminated by a signal")),
        }
    }

    fn failed(reason: &str) -> IssuesUnread {
        IssuesUnread::CommandFailed {
            reason: reason.to_string(),
        }
    }
}

impl IssueSource for BoundedGhProcess {
    fn repo_of_directory(&mut self) -> Result<String, IssuesUnread> {
        let answer = self.answer_of(&["repo", "view", "--json", RepoViewPayload::KEY])?;

        RepoViewPayload::parsed(&answer)
    }

    fn latest_open(&mut self, repo: &str, limit: usize) -> Result<Vec<OpenIssue>, IssuesUnread> {
        let answer = self.answer_of(&[
            "issue",
            "list",
            "--repo",
            repo,
            "--state",
            "open",
            "--limit",
            &limit.to_string(),
            "--json",
            &OpenIssuesPayload::KEYS.join(","),
        ])?;

        OpenIssuesPayload::parsed(&answer)
    }

    fn body_of(&mut self, repo: &str, number: u64) -> Result<IssueText, IssuesUnread> {
        let answer = self.answer_of(&[
            "issue",
            "view",
            &number.to_string(),
            "--repo",
            repo,
            "--json",
            &IssueBodyPayload::KEYS.join(","),
        ])?;

        IssueBodyPayload::parsed(&answer)
    }
}
