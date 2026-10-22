use std::path::PathBuf;

use crate::domain::session_launch::SessionLaunch;
use crate::domain::workspace_ids::WorkspaceIds;

pub struct StartClaudeSessionParams {
    directory: PathBuf,
}

impl StartClaudeSessionParams {
    pub fn in_directory(directory: PathBuf) -> Self {
        Self { directory }
    }
}

pub struct StartClaudeSession<I: WorkspaceIds> {
    ids: I,
}

impl<I: WorkspaceIds> StartClaudeSession<I> {
    pub fn new(ids: I) -> Self {
        Self { ids }
    }

    pub fn execute(&mut self, params: StartClaudeSessionParams) -> SessionLaunch {
        let id = self.ids.next();
        let argv = ["claude", "--session-id", id.as_str(), "/slice-spec"]
            .map(str::to_string)
            .to_vec();

        SessionLaunch::for_workspace(id, argv, params.directory)
    }
}
