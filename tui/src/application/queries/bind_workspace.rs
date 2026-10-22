use std::time::Instant;

use crate::domain::binding_cadence::BindingCadence;
use crate::domain::clock::Clock;
use crate::domain::errors::IssuesUnread;
use crate::domain::issue_source::IssueSource;
use crate::domain::workspace_binding::WorkspaceBinding;
use crate::domain::workspace_id::WorkspaceId;
use crate::domain::workspace_marker::WorkspaceMarker;
use crate::domain::workspace_repo::WorkspaceRepo;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WorkspaceState {
    repo: WorkspaceRepo,
    id: WorkspaceId,
    binding: WorkspaceBinding,
    title: Option<String>,
    warning: Option<IssuesUnread>,
}

impl WorkspaceState {
    pub fn unresolved(id: WorkspaceId) -> Self {
        Self {
            repo: WorkspaceRepo::Unknown,
            id,
            binding: WorkspaceBinding::Unbound,
            title: None,
            warning: None,
        }
    }

    pub fn bound(repo: String, id: WorkspaceId, parent: u64, title: &str) -> Self {
        Self {
            repo: WorkspaceRepo::Known(repo),
            id,
            binding: WorkspaceBinding::Bound(parent),
            title: Some(title.to_string()),
            warning: None,
        }
    }

    pub fn repo(&self) -> &WorkspaceRepo {
        &self.repo
    }

    pub fn id(&self) -> &WorkspaceId {
        &self.id
    }

    pub fn binding(&self) -> WorkspaceBinding {
        self.binding
    }

    pub fn title(&self) -> Option<&str> {
        self.title.as_deref()
    }

    pub fn warning(&self) -> Option<&IssuesUnread> {
        self.warning.as_ref()
    }
}

pub struct BindWorkspace<S: IssueSource, C: Clock> {
    source: S,
    clock: C,
    cadence: BindingCadence,
    state: WorkspaceState,
    last_query: Option<Instant>,
}

impl<S: IssueSource, C: Clock> BindWorkspace<S, C> {
    pub fn new(source: S, clock: C, cadence: BindingCadence, id: WorkspaceId) -> Self {
        Self {
            source,
            clock,
            cadence,
            state: WorkspaceState::unresolved(id),
            last_query: None,
        }
    }

    pub fn from_state(source: S, clock: C, cadence: BindingCadence, state: WorkspaceState) -> Self {
        Self {
            source,
            clock,
            cadence,
            state,
            last_query: None,
        }
    }

    pub fn current(&self) -> WorkspaceState {
        self.state.clone()
    }

    pub fn execute(&mut self) -> WorkspaceState {
        if self.is_due() {
            self.last_query = Some(self.clock.now());
            self.state.warning = self.read().err();
        }

        self.state.clone()
    }

    fn is_due(&self) -> bool {
        match self.state.binding {
            WorkspaceBinding::Bound(_) => false,
            WorkspaceBinding::Unbound => self
                .last_query
                .is_none_or(|last| self.clock.now() >= last + self.cadence.interval()),
        }
    }

    fn read(&mut self) -> Result<(), IssuesUnread> {
        let repo = self.resolved_repo()?;
        let issues = self.source.latest_open(&repo, self.cadence.limit())?;
        if let Some(issue) = issues
            .iter()
            .find(|issue| WorkspaceMarker::ends(issue.body(), &self.state.id))
        {
            self.state.binding = WorkspaceBinding::Bound(issue.number());
            self.state.title = Some(issue.title().to_string());
        }

        Ok(())
    }

    fn resolved_repo(&mut self) -> Result<String, IssuesUnread> {
        match &self.state.repo {
            WorkspaceRepo::Known(repo) => Ok(repo.clone()),
            WorkspaceRepo::Unknown => {
                let repo = self.source.repo_of_directory()?;
                self.state.repo = WorkspaceRepo::Known(repo.clone());

                Ok(repo)
            }
        }
    }
}
