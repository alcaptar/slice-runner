use crate::application::queries::bind_workspace::WorkspaceState;
use crate::domain::errors::FollowLineRejected;
use crate::domain::follow_source::FollowSource;
use crate::domain::process_probe::ProcessProbe;
use crate::domain::slice_board::SliceBoard;
use crate::domain::workspace_repo::WorkspaceRepo;

#[derive(Debug, Clone, PartialEq)]
pub struct WatchedBoard {
    board: SliceBoard,
    rejection: Option<FollowLineRejected>,
    title: Option<String>,
}

impl WatchedBoard {
    pub fn board(&self) -> &SliceBoard {
        &self.board
    }

    pub fn rejection(&self) -> Option<&FollowLineRejected> {
        self.rejection.as_ref()
    }

    pub fn title(&self) -> Option<&str> {
        self.title.as_deref()
    }

    pub fn shown_for(&self, state: &WorkspaceState) -> Self {
        let board = match state.repo() {
            WorkspaceRepo::Known(repo) => self.board.shown_for(repo, state.binding()),
            WorkspaceRepo::Unknown => SliceBoard::empty(),
        };

        Self {
            board,
            rejection: self.rejection.clone(),
            title: state.title().map(str::to_string),
        }
    }

    pub fn into_board(self) -> SliceBoard {
        self.board
    }
}

pub struct WatchSlices<S: FollowSource, P: ProcessProbe> {
    source: S,
    probe: P,
    rejection: Option<FollowLineRejected>,
}

impl<S: FollowSource, P: ProcessProbe> WatchSlices<S, P> {
    pub fn new(source: S, probe: P) -> Self {
        Self {
            source,
            probe,
            rejection: None,
        }
    }

    pub fn execute(&mut self, board: SliceBoard) -> WatchedBoard {
        let mut board = board;
        for delivery in self.source.pending() {
            match delivery {
                Ok(entry) => {
                    board = board.with_entry(entry);
                    self.rejection = None;
                }
                Err(rejection) => self.rejection = Some(rejection),
            }
        }

        WatchedBoard {
            board: board.probed(&self.probe),
            rejection: self.rejection.clone(),
            title: None,
        }
    }
}
