use std::io::{self, Read};
use std::path::Path;

use portable_pty::{Child, CommandBuilder, MasterPty, PtySize, native_pty_system};

use crate::domain::pane_size::PaneSize;
use crate::infrastructure::child_launcher::{ChildExit, RunningChild};
use crate::infrastructure::pty_launcher::{LaunchedPty, PtyLauncher, PtyResizer};

pub struct OsPtyLauncher;

impl OsPtyLauncher {
    fn pty_size(size: PaneSize) -> PtySize {
        PtySize {
            rows: size.rows(),
            cols: size.columns(),
            pixel_width: 0,
            pixel_height: 0,
        }
    }

    fn io_error(error: &impl ToString) -> io::Error {
        io::Error::other(error.to_string())
    }
}

impl PtyLauncher for OsPtyLauncher {
    fn launched(
        &self,
        argv: &[String],
        directory: &Path,
        environment: &[(String, String)],
        size: PaneSize,
    ) -> io::Result<LaunchedPty> {
        let (program, arguments) = argv
            .split_first()
            .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidInput, "empty command"))?;
        let pair = native_pty_system()
            .openpty(Self::pty_size(size))
            .map_err(|error| Self::io_error(&error))?;
        let reader = pair.master.try_clone_reader().map_err(|error| Self::io_error(&error))?;
        let writer = pair.master.take_writer().map_err(|error| Self::io_error(&error))?;
        let mut builder = CommandBuilder::new(program);
        builder.args(arguments);
        builder.cwd(directory);
        for (name, value) in environment {
            builder.env(name, value);
        }
        let child = pair
            .slave
            .spawn_command(builder)
            .map_err(|error| Self::io_error(&error))?;
        drop(pair.slave);

        Ok(LaunchedPty::new(
            reader,
            writer,
            Box::new(OsPtyMaster { master: pair.master }),
            Box::new(OsPtyChild { child }),
        ))
    }
}

struct OsPtyMaster {
    master: Box<dyn MasterPty + Send>,
}

impl PtyResizer for OsPtyMaster {
    fn resize(&mut self, size: PaneSize) -> io::Result<()> {
        self.master
            .resize(OsPtyLauncher::pty_size(size))
            .map_err(|error| OsPtyLauncher::io_error(&error))
    }
}

struct OsPtyChild {
    child: Box<dyn Child + Send>,
}

impl OsPtyChild {
    fn exit_of(status: &portable_pty::ExitStatus) -> ChildExit {
        i32::try_from(status.exit_code()).map_or(ChildExit::Signal, ChildExit::Code)
    }
}

impl RunningChild for OsPtyChild {
    fn try_wait(&mut self) -> io::Result<Option<ChildExit>> {
        self.child.try_wait().map(|status| status.as_ref().map(Self::exit_of))
    }

    fn kill(&mut self) -> io::Result<()> {
        self.child.kill()
    }

    fn wait(&mut self) -> io::Result<ChildExit> {
        self.child.wait().map(|status| Self::exit_of(&status))
    }

    fn take_stdout(&mut self) -> Option<Box<dyn Read + Send>> {
        None
    }

    fn take_stderr(&mut self) -> Option<Box<dyn Read + Send>> {
        None
    }
}
