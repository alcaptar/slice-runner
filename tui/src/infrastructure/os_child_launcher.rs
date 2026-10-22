use std::fs::File;
use std::io::{self, Read};
use std::process::{Child, Command, ExitStatus, Stdio};

use crate::infrastructure::child_launcher::{ChildExit, ChildLauncher, Input, Launch, RunningChild, Stream};

pub struct OsChildLauncher;

impl OsChildLauncher {
    pub fn command_of(argv: &[String], options: &Launch) -> io::Result<Command> {
        let (program, arguments) = argv
            .split_first()
            .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidInput, "empty command"))?;
        let mut command = Command::new(program);
        command
            .args(arguments)
            .stdin(Self::stdin_of(options.stdin()))
            .stdout(Self::stdio_of(options.stdout())?)
            .stderr(Self::stdio_of(options.stderr())?);

        Ok(command)
    }

    fn stdin_of(input: Input) -> Stdio {
        match input {
            Input::Empty => Stdio::null(),
        }
    }

    fn stdio_of(stream: &Stream) -> io::Result<Stdio> {
        match stream {
            Stream::Read => Ok(Stdio::piped()),
            Stream::Discard => Ok(Stdio::null()),
            Stream::File(path) => File::create(path).map(Stdio::from),
        }
    }
}

impl ChildLauncher for OsChildLauncher {
    fn launched(&self, argv: &[String], options: &Launch) -> Result<Box<dyn RunningChild>, io::Error> {
        let child = Self::command_of(argv, options)?.spawn()?;

        Ok(Box::new(OsChild::new(child)))
    }
}

pub struct OsChild {
    child: Child,
}

impl OsChild {
    pub fn new(child: Child) -> Self {
        Self { child }
    }

    pub fn id(&self) -> u32 {
        self.child.id()
    }

    fn exit_of(status: ExitStatus) -> ChildExit {
        status.code().map_or(ChildExit::Signal, ChildExit::Code)
    }
}

impl RunningChild for OsChild {
    fn try_wait(&mut self) -> io::Result<Option<ChildExit>> {
        self.child.try_wait().map(|status| status.map(Self::exit_of))
    }

    fn kill(&mut self) -> io::Result<()> {
        self.child.kill()
    }

    fn wait(&mut self) -> io::Result<ChildExit> {
        self.child.wait().map(Self::exit_of)
    }

    fn take_stdout(&mut self) -> Option<Box<dyn Read + Send>> {
        self.child
            .stdout
            .take()
            .map(|stream| Box::new(stream) as Box<dyn Read + Send>)
    }

    fn take_stderr(&mut self) -> Option<Box<dyn Read + Send>> {
        self.child
            .stderr
            .take()
            .map(|stream| Box::new(stream) as Box<dyn Read + Send>)
    }
}
