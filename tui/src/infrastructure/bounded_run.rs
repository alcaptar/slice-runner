use std::io::Read;
use std::sync::Arc;
use std::thread::{self, JoinHandle};
use std::time::Duration;

use crate::domain::clock::Clock;
use crate::infrastructure::child_launcher::{ChildExit, ChildLauncher, Launch, RunningChild};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RunOutput {
    exit: ChildExit,
    stdout: String,
    stderr: String,
}

impl RunOutput {
    pub fn exit(&self) -> ChildExit {
        self.exit
    }

    pub fn stdout(&self) -> &str {
        &self.stdout
    }

    pub fn stderr(&self) -> &str {
        &self.stderr
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum RunFailure {
    NotLaunched { reason: String },
    TimedOut,
    Failed { reason: String },
}

pub struct BoundedRun {
    program: Vec<String>,
    launcher: Arc<dyn ChildLauncher>,
    clock: Box<dyn Clock>,
    budget: Duration,
}

impl BoundedRun {
    const POLL: Duration = Duration::from_millis(10);

    pub fn new(
        program: Vec<String>,
        launcher: Arc<dyn ChildLauncher>,
        clock: impl Clock + 'static,
        budget: Duration,
    ) -> Self {
        Self {
            program,
            launcher,
            clock: Box::new(clock),
            budget,
        }
    }

    pub fn budget(&self) -> Duration {
        self.budget
    }

    pub fn run(&self, arguments: &[&str], launch: &Launch) -> Result<RunOutput, RunFailure> {
        let argv: Vec<String> = self
            .program
            .iter()
            .cloned()
            .chain(arguments.iter().map(ToString::to_string))
            .collect();
        let mut child = self
            .launcher
            .launched(&argv, launch)
            .map_err(|error| RunFailure::NotLaunched {
                reason: error.to_string(),
            })?;
        let stdout = Self::drained(child.take_stdout());
        let stderr = Self::drained(child.take_stderr());
        let deadline = self.clock.now() + self.budget;
        loop {
            match child.try_wait() {
                Ok(Some(exit)) => {
                    return Ok(RunOutput {
                        exit,
                        stdout: stdout.join().unwrap_or_default(),
                        stderr: stderr.join().unwrap_or_default(),
                    });
                }
                Ok(None) if self.clock.now() < deadline => thread::sleep(Self::POLL),
                Ok(None) => {
                    Self::abandoned(child.as_mut());
                    return Err(RunFailure::TimedOut);
                }
                Err(error) => {
                    Self::abandoned(child.as_mut());
                    return Err(RunFailure::Failed {
                        reason: error.to_string(),
                    });
                }
            }
        }
    }

    fn drained(stream: Option<Box<dyn Read + Send>>) -> JoinHandle<String> {
        thread::spawn(move || {
            let mut bytes = Vec::new();
            if let Some(mut stream) = stream {
                stream.read_to_end(&mut bytes).ok();
            }

            String::from_utf8_lossy(&bytes).into_owned()
        })
    }

    fn abandoned(child: &mut dyn RunningChild) {
        child.kill().ok();
        child.wait().ok();
    }
}
