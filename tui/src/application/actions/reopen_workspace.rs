use std::path::PathBuf;

use crate::application::queries::bind_workspace::WorkspaceState;
use crate::domain::errors::WorkspaceNotReopened;
use crate::domain::issue_source::IssueSource;
use crate::domain::session_launch::SessionLaunch;
use crate::domain::session_transcripts::SessionTranscripts;
use crate::domain::workspace_id::WorkspaceId;
use crate::domain::workspace_marker::WorkspaceMarker;

pub struct ReopenWorkspaceParams {
    directory: PathBuf,
    parent: u64,
}

impl ReopenWorkspaceParams {
    pub fn new(directory: PathBuf, parent: u64) -> Self {
        Self { directory, parent }
    }
}

pub struct ReopenedWorkspace {
    launch: SessionLaunch,
    state: WorkspaceState,
}

impl ReopenedWorkspace {
    pub fn launch(&self) -> &SessionLaunch {
        &self.launch
    }

    pub fn into_state(self) -> WorkspaceState {
        self.state
    }
}

pub struct ReopenWorkspace<S: IssueSource, T: SessionTranscripts> {
    source: S,
    transcripts: T,
}

impl<S: IssueSource, T: SessionTranscripts> ReopenWorkspace<S, T> {
    pub fn new(source: S, transcripts: T) -> Self {
        Self { source, transcripts }
    }

    pub fn execute(&mut self, params: ReopenWorkspaceParams) -> Result<ReopenedWorkspace, WorkspaceNotReopened> {
        let repo = self.source.repo_of_directory()?;
        let text = self.source.body_of(&repo, params.parent)?;
        let id = WorkspaceMarker::id_in(text.body()).ok_or(WorkspaceNotReopened::Unmarked { parent: params.parent })?;
        let argv = self.argv_for(&params.directory, &id);

        Ok(ReopenedWorkspace {
            launch: SessionLaunch::for_workspace(id.clone(), argv, params.directory),
            state: WorkspaceState::bound(repo, id, params.parent, text.title()),
        })
    }

    fn argv_for(&self, directory: &std::path::Path, id: &WorkspaceId) -> Vec<String> {
        let flag = if self.transcripts.exists(directory, id) {
            "--resume"
        } else {
            "--session-id"
        };

        ["claude", flag, id.as_str()].map(str::to_string).to_vec()
    }
}
