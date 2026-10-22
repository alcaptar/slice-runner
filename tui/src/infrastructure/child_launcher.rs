use std::io::{self, Read};
use std::path::PathBuf;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Input {
    Empty,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Stream {
    Read,
    Discard,
    File(PathBuf),
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Launch {
    stdin: Input,
    stdout: Stream,
    stderr: Stream,
}

impl Launch {
    pub fn new(stdin: Input, stdout: Stream, stderr: Stream) -> Self {
        Self { stdin, stdout, stderr }
    }

    pub fn stdin(&self) -> Input {
        self.stdin
    }

    pub fn stdout(&self) -> &Stream {
        &self.stdout
    }

    pub fn stderr(&self) -> &Stream {
        &self.stderr
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ChildExit {
    Code(i32),
    Signal,
}

pub trait RunningChild: Send {
    fn try_wait(&mut self) -> io::Result<Option<ChildExit>>;
    fn kill(&mut self) -> io::Result<()>;
    fn wait(&mut self) -> io::Result<ChildExit>;
    fn take_stdout(&mut self) -> Option<Box<dyn Read + Send>>;
    fn take_stderr(&mut self) -> Option<Box<dyn Read + Send>>;
}

pub trait ChildLauncher: Send + Sync {
    fn launched(&self, argv: &[String], options: &Launch) -> Result<Box<dyn RunningChild>, io::Error>;
}
