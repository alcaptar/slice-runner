use std::sync::Arc;
use std::time::Duration;

use crate::domain::clock::Clock;
use crate::domain::update_availability::UpdateAvailability;
use crate::domain::update_check::UpdateCheck;
use crate::infrastructure::bounded_run::BoundedRun;
use crate::infrastructure::child_launcher::{ChildExit, ChildLauncher, Input, Launch, Stream};

pub struct BoundedUpdateCheckProcess {
    run: BoundedRun,
}

impl BoundedUpdateCheckProcess {
    const ARGUMENTS: [&'static str; 2] = ["update", "--check"];

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

    fn output_of(&self) -> Option<String> {
        let output = self
            .run
            .run(
                &Self::ARGUMENTS,
                &Launch::new(Input::Empty, Stream::Read, Stream::Discard),
            )
            .ok()?;

        (output.exit() == ChildExit::Code(0)).then(|| output.stdout().to_string())
    }

    fn parsed(output: &str) -> UpdateAvailability {
        match output.strip_suffix('\n') {
            Some(version) if !version.is_empty() && !version.contains(char::is_whitespace) => {
                UpdateAvailability::Newer(version.to_string())
            }
            Some(_) | None => UpdateAvailability::Absent,
        }
    }
}

impl UpdateCheck for BoundedUpdateCheckProcess {
    fn availability(&mut self) -> UpdateAvailability {
        self.output_of()
            .map_or(UpdateAvailability::Absent, |output| Self::parsed(&output))
    }
}
