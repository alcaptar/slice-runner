use std::path::PathBuf;
use std::sync::Arc;
use std::sync::mpsc::{self, Receiver, TryRecvError};
use std::thread;
use std::time::Duration;

use uuid::Uuid;

use crate::domain::clock::Clock;
use crate::domain::program_update::ProgramUpdate;
use crate::domain::update_progress::UpdateProgress;
use crate::infrastructure::child_launcher::{ChildExit, ChildLauncher, Input, Launch, RunningChild, Stream};

enum Finish {
    Exited(ChildExit),
    TimedOut,
    NotLaunched(String),
}

struct Running {
    finish: Receiver<Finish>,
    error_file: PathBuf,
}

pub struct DetachedProgramUpdate {
    program: Vec<String>,
    launcher: Arc<dyn ChildLauncher>,
    clock: Arc<dyn Clock>,
    budget: Duration,
    directory: PathBuf,
    running: Option<Running>,
    settled: Option<UpdateProgress>,
}

impl DetachedProgramUpdate {
    const POLL: Duration = Duration::from_millis(10);
    const ARGUMENTS: [&'static str; 1] = ["update"];
    const LOST: &'static str = "se perdio el seguimiento del proceso";

    pub fn new(
        program: Vec<String>,
        launcher: Arc<dyn ChildLauncher>,
        clock: impl Clock + 'static,
        budget: Duration,
        directory: PathBuf,
    ) -> Self {
        Self {
            program,
            launcher,
            clock: Arc::new(clock),
            budget,
            directory,
            running: None,
            settled: None,
        }
    }

    fn abandoned(child: &mut dyn RunningChild) {
        child.kill().ok();
        child.wait().ok();
    }

    fn finish_of(mut child: Box<dyn RunningChild>, clock: &dyn Clock, budget: Duration) -> Finish {
        let deadline = clock.now() + budget;
        loop {
            match child.try_wait() {
                Ok(Some(exit)) => return Finish::Exited(exit),
                Ok(None) if clock.now() < deadline => thread::sleep(Self::POLL),
                Ok(None) | Err(_) => {
                    Self::abandoned(child.as_mut());
                    return Finish::TimedOut;
                }
            }
        }
    }

    fn last_line_of(error_file: &PathBuf) -> Option<String> {
        let text = std::fs::read_to_string(error_file).ok()?;

        text.lines()
            .map(str::trim)
            .rfind(|line| !line.is_empty())
            .map(ToString::to_string)
    }

    fn exit_reason(exit: ChildExit) -> String {
        match exit {
            ChildExit::Code(code) => format!("salio con {code}"),
            ChildExit::Signal => "salio sin codigo".to_string(),
        }
    }

    fn progress_of(&self, finish: Finish, error_file: &PathBuf) -> UpdateProgress {
        match finish {
            Finish::Exited(ChildExit::Code(0)) => UpdateProgress::Installed,
            Finish::Exited(exit) => {
                UpdateProgress::Failed(Self::last_line_of(error_file).unwrap_or_else(|| Self::exit_reason(exit)))
            }
            Finish::TimedOut => UpdateProgress::Failed(format!("no termino en {} s", self.budget.as_secs())),
            Finish::NotLaunched(reason) => UpdateProgress::Failed(reason),
        }
    }
}

impl ProgramUpdate for DetachedProgramUpdate {
    fn start(&mut self, _version: &str) {
        let error_path = self
            .directory
            .join(format!("slice-runner-update-{}.err", Uuid::new_v4()));
        let argv: Vec<String> = self
            .program
            .iter()
            .map(String::as_str)
            .chain(Self::ARGUMENTS)
            .map(ToString::to_string)
            .collect();
        let launch = Launch::new(Input::Empty, Stream::Discard, Stream::File(error_path.clone()));
        let (sender, finish) = mpsc::channel();
        let launcher = Arc::clone(&self.launcher);
        let clock = Arc::clone(&self.clock);
        let budget = self.budget;
        thread::spawn(move || {
            let finish = match launcher.launched(&argv, &launch) {
                Ok(child) => Self::finish_of(child, clock.as_ref(), budget),
                Err(error) => Finish::NotLaunched(error.to_string()),
            };
            sender.send(finish).ok();
        });
        self.running = Some(Running {
            finish,
            error_file: error_path,
        });
    }

    fn progress(&mut self) -> UpdateProgress {
        if let Some(settled) = &self.settled {
            return settled.clone();
        }
        let Some(running) = self.running.take() else {
            return UpdateProgress::Running;
        };
        let finish = match running.finish.try_recv() {
            Ok(finish) => finish,
            Err(TryRecvError::Empty) => {
                self.running = Some(running);
                return UpdateProgress::Running;
            }
            Err(TryRecvError::Disconnected) => Finish::NotLaunched(Self::LOST.to_string()),
        };
        let progress = self.progress_of(finish, &running.error_file);
        std::fs::remove_file(&running.error_file).ok();
        self.settled = Some(progress.clone());

        progress
    }
}
