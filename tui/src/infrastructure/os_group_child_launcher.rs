use std::io::{self, Read};
use std::os::unix::process::CommandExt;

use nix::sys::signal::{Signal, killpg};
use nix::unistd::Pid;

use crate::infrastructure::child_launcher::{ChildExit, ChildLauncher, Launch, RunningChild};
use crate::infrastructure::os_child_launcher::{OsChild, OsChildLauncher};

pub struct OsGroupChildLauncher;

impl ChildLauncher for OsGroupChildLauncher {
    fn launched(&self, argv: &[String], options: &Launch) -> Result<Box<dyn RunningChild>, io::Error> {
        let child = OsChildLauncher::command_of(argv, options)?.process_group(0).spawn()?;

        Ok(Box::new(OsGroupChild {
            child: OsChild::new(child),
        }))
    }
}

struct OsGroupChild {
    child: OsChild,
}

impl RunningChild for OsGroupChild {
    fn try_wait(&mut self) -> io::Result<Option<ChildExit>> {
        self.child.try_wait()
    }

    fn kill(&mut self) -> io::Result<()> {
        i32::try_from(self.child.id())
            .ok()
            .and_then(|id| killpg(Pid::from_raw(id), Signal::SIGKILL).ok());

        self.child.kill()
    }

    fn wait(&mut self) -> io::Result<ChildExit> {
        self.child.wait()
    }

    fn take_stdout(&mut self) -> Option<Box<dyn Read + Send>> {
        self.child.take_stdout()
    }

    fn take_stderr(&mut self) -> Option<Box<dyn Read + Send>> {
        self.child.take_stderr()
    }
}
