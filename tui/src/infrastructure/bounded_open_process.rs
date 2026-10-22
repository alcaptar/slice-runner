use std::sync::Arc;
use std::time::Duration;

use crate::domain::clock::Clock;
use crate::domain::comparison_opener::ComparisonOpener;
use crate::domain::errors::ComparisonNotOpened;
use crate::infrastructure::bounded_run::{BoundedRun, RunFailure, RunOutput};
use crate::infrastructure::child_launcher::{ChildExit, ChildLauncher, Input, Launch, Stream};

pub struct BoundedOpenProcess {
    run: BoundedRun,
}

impl BoundedOpenProcess {
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

    fn not_opened(&self, failure: RunFailure) -> ComparisonNotOpened {
        match failure {
            RunFailure::NotLaunched { reason } | RunFailure::Failed { reason } => Self::failed(&reason),
            RunFailure::TimedOut => ComparisonNotOpened::TimedOut {
                budget: self.run.budget(),
            },
        }
    }

    fn interpreted(output: &RunOutput) -> Result<(), ComparisonNotOpened> {
        match output.exit() {
            ChildExit::Code(0) => Ok(()),
            ChildExit::Code(code) if output.stderr().trim().is_empty() => {
                Err(Self::failed(&format!("exited with code {code}")))
            }
            ChildExit::Code(_) => Err(Self::failed(output.stderr().trim())),
            ChildExit::Signal => Err(Self::failed("terminated by a signal")),
        }
    }

    fn failed(reason: &str) -> ComparisonNotOpened {
        ComparisonNotOpened::CommandFailed {
            reason: reason.to_string(),
        }
    }
}

impl ComparisonOpener for BoundedOpenProcess {
    fn open(&mut self, path: &str) -> Result<(), ComparisonNotOpened> {
        self.run
            .run(&[path], &Launch::new(Input::Empty, Stream::Discard, Stream::Read))
            .map_err(|failure| self.not_opened(failure))
            .and_then(|output| Self::interpreted(&output))
    }
}
