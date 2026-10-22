use std::io::{self, Read, Write};
use std::path::Path;

use crate::domain::pane_size::PaneSize;
use crate::infrastructure::child_launcher::RunningChild;

pub type PtyReader = Box<dyn Read + Send>;
pub type PtyWriter = Box<dyn Write + Send>;
pub type PtyChild = Box<dyn RunningChild>;

pub trait PtyResizer: Send {
    fn resize(&mut self, size: PaneSize) -> io::Result<()>;
}

pub struct LaunchedPty {
    reader: PtyReader,
    writer: PtyWriter,
    resizer: Box<dyn PtyResizer>,
    child: PtyChild,
}

impl LaunchedPty {
    pub fn new(reader: PtyReader, writer: PtyWriter, resizer: Box<dyn PtyResizer>, child: PtyChild) -> Self {
        Self {
            reader,
            writer,
            resizer,
            child,
        }
    }

    pub fn into_parts(self) -> (PtyReader, PtyWriter, Box<dyn PtyResizer>, PtyChild) {
        (self.reader, self.writer, self.resizer, self.child)
    }
}

pub trait PtyLauncher {
    fn launched(
        &self,
        argv: &[String],
        directory: &Path,
        environment: &[(String, String)],
        size: PaneSize,
    ) -> io::Result<LaunchedPty>;
}
