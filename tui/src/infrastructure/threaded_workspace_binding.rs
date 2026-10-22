use std::sync::mpsc::{self, Receiver};
use std::thread;
use std::time::Duration;

use crate::application::queries::bind_workspace::{BindWorkspace, WorkspaceState};
use crate::domain::clock::Clock;
use crate::domain::issue_source::IssueSource;
use crate::domain::workspace_binding::WorkspaceBinding;

pub struct ThreadedWorkspaceBinding {
    states: Receiver<WorkspaceState>,
    last: WorkspaceState,
}

impl ThreadedWorkspaceBinding {
    pub fn start<S: IssueSource + 'static, C: Clock + 'static>(mut bind: BindWorkspace<S, C>, pace: Duration) -> Self {
        let (sender, states) = mpsc::channel();
        let last = bind.current();
        thread::spawn(move || {
            loop {
                let state = bind.execute();
                let bound = state.binding() != WorkspaceBinding::Unbound;
                if sender.send(state).is_err() || bound {
                    break;
                }
                thread::sleep(pace);
            }
        });

        Self { states, last }
    }

    pub fn latest(&mut self) -> WorkspaceState {
        if let Some(state) = self.states.try_iter().last() {
            self.last = state;
        }

        self.last.clone()
    }
}
