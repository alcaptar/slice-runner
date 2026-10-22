use std::io::{BufRead, BufReader};
use std::sync::mpsc::{Receiver, channel};
use std::thread;

use crate::domain::errors::FollowLineRejected;
use crate::domain::follow_entry::FollowEntry;
use crate::domain::follow_source::FollowSource;
use crate::infrastructure::child_launcher::{ChildLauncher, Input, Launch, RunningChild, Stream};
use crate::infrastructure::follow_line_payload::FollowLinePayload;

pub struct EndlessFollowProcess {
    child: Box<dyn RunningChild>,
    deliveries: Receiver<Result<FollowEntry, FollowLineRejected>>,
}

impl EndlessFollowProcess {
    pub fn spawn<S: AsRef<str>>(launcher: &dyn ChildLauncher, argv: &[S]) -> Result<Self, FollowLineRejected> {
        let argv: Vec<String> = argv.iter().map(|part| part.as_ref().to_string()).collect();
        let mut child = launcher
            .launched(&argv, &Launch::new(Input::Empty, Stream::Read, Stream::Discard))
            .map_err(|error| Self::not_launched(&error.to_string()))?;
        let Some(stdout) = child.take_stdout() else {
            child.kill().ok();
            child.wait().ok();
            return Err(Self::not_launched("no standard output"));
        };
        let (sender, deliveries) = channel();
        thread::spawn(move || {
            for line in BufReader::new(stdout).lines().map_while(Result::ok) {
                if sender.send(FollowLinePayload::delivery(&line)).is_err() {
                    return;
                }
            }
            sender.send(Err(FollowLineRejected::FollowEnded)).ok();
        });

        Ok(Self { child, deliveries })
    }

    fn not_launched(reason: &str) -> FollowLineRejected {
        FollowLineRejected::FollowNotLaunched {
            reason: reason.to_string(),
        }
    }
}

impl FollowSource for EndlessFollowProcess {
    fn pending(&mut self) -> Vec<Result<FollowEntry, FollowLineRejected>> {
        self.deliveries.try_iter().collect()
    }
}

impl Drop for EndlessFollowProcess {
    fn drop(&mut self) {
        self.child.kill().ok();
        self.child.wait().ok();
    }
}
