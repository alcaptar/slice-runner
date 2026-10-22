use crate::domain::workspace_id::WorkspaceId;

pub struct WorkspaceMarker;

impl WorkspaceMarker {
    const OPENING: &'static str = "<!-- slice-runner:workspace ";
    const CLOSING: &'static str = " -->";

    pub fn id_in(body: &str) -> Option<WorkspaceId> {
        let last_line = body.lines().rev().map(str::trim).find(|line| !line.is_empty())?;
        let text = last_line.strip_prefix(Self::OPENING)?.strip_suffix(Self::CLOSING)?;

        WorkspaceId::parse(text).ok()
    }

    pub fn ends(body: &str, id: &WorkspaceId) -> bool {
        Self::id_in(body).as_ref() == Some(id)
    }
}
