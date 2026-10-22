use std::path::{Path, PathBuf};

use crate::domain::workspace_id::WorkspaceId;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SessionLaunch {
    workspace: WorkspaceId,
    argv: Vec<String>,
    directory: PathBuf,
    environment: Vec<(String, String)>,
}

impl SessionLaunch {
    const WORKSPACE_VARIABLE: &'static str = "SLICE_RUNNER_WORKSPACE";

    pub fn for_workspace(workspace: WorkspaceId, argv: Vec<String>, directory: PathBuf) -> Self {
        let environment = vec![(Self::WORKSPACE_VARIABLE.to_string(), workspace.as_str().to_string())];

        Self::new(workspace, argv, directory, environment)
    }

    pub fn new(
        workspace: WorkspaceId,
        argv: Vec<String>,
        directory: PathBuf,
        environment: Vec<(String, String)>,
    ) -> Self {
        Self {
            workspace,
            argv,
            directory,
            environment,
        }
    }

    pub fn workspace(&self) -> &WorkspaceId {
        &self.workspace
    }

    pub fn argv(&self) -> &[String] {
        &self.argv
    }

    pub fn directory(&self) -> &Path {
        &self.directory
    }

    pub fn environment(&self) -> &[(String, String)] {
        &self.environment
    }
}
