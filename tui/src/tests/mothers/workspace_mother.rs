use std::time::Duration;

use crate::application::queries::bind_workspace::{BindWorkspace, WorkspaceState};
use crate::application::queries::watch_slices::WatchedBoard;
use crate::domain::binding_cadence::BindingCadence;
use crate::domain::open_issue::OpenIssue;
use crate::domain::workspace_id::WorkspaceId;
use crate::tests::doubles::{ScriptedIssueSource, SteppedClock};

pub struct WorkspaceMother;

impl WorkspaceMother {
    pub const UUID: &'static str = "0b9a6f0e-6f3c-4a54-9d0e-3b1f6f0c2a11";
    pub const OTHER_UUID: &'static str = "7c1d2e3f-4a5b-4c6d-8e7f-9a0b1c2d3e4f";
    pub const REPO: &'static str = "alcaptar/demo-workspace";
    pub const INTERVAL: Duration = Duration::from_secs(5);
    pub const LIMIT: usize = 20;
    pub const PARENT_TITLE: &'static str = "las slices dejan de abrir transacciones";

    pub fn id() -> WorkspaceId {
        WorkspaceId::parse(Self::UUID).unwrap()
    }

    pub fn cadence() -> BindingCadence {
        BindingCadence::new(Self::INTERVAL, Self::LIMIT)
    }

    pub fn marker_of(uuid: &str) -> String {
        format!("<!-- slice-runner:workspace {uuid} -->")
    }

    pub fn unrelated_issue(number: u64) -> OpenIssue {
        OpenIssue::new(
            number,
            "Una issue cualquiera\n\nsin marca de workspace\n",
            "Una issue cualquiera",
        )
    }

    pub fn parent_marked_with(number: u64, uuid: &str) -> OpenIssue {
        OpenIssue::new(
            number,
            &format!("## Intencion\n\nalgo\n\n{}\n", Self::marker_of(uuid)),
            Self::PARENT_TITLE,
        )
    }

    pub fn parent_of_this_workspace(number: u64) -> OpenIssue {
        Self::parent_marked_with(number, Self::UUID)
    }

    pub fn unbound() -> WorkspaceState {
        WorkspaceState::unresolved(Self::id())
    }

    pub fn body_marked_with(uuid: &str) -> String {
        format!("## Intencion\n\nalgo\n\n{}\n", Self::marker_of(uuid))
    }

    pub fn body_without_marker() -> String {
        "## Intencion\n\nalgo\n".to_string()
    }

    pub fn bound_to(parent: u64) -> WorkspaceState {
        let (source, _) = ScriptedIssueSource::answering(
            vec![Ok(Self::REPO.to_string())],
            vec![Ok(vec![Self::parent_of_this_workspace(parent)])],
        );

        BindWorkspace::new(source, SteppedClock::standing_still(), Self::cadence(), Self::id()).execute()
    }

    pub fn showing(watched: &WatchedBoard, parent: u64) -> WatchedBoard {
        watched.shown_for(&Self::bound_to(parent))
    }
}
