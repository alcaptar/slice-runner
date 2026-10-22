use std::io::{Read, Write};
use std::sync::{Arc, Mutex, MutexGuard, PoisonError};
use std::thread;

use vt100::Screen;

use crate::domain::clock::Clock;
use crate::domain::errors::SessionNotLaunched;
use crate::domain::pane_size::PaneSize;
use crate::domain::session_launch::SessionLaunch;
use crate::infrastructure::child_launcher::RunningChild;
use crate::infrastructure::frame_holding_terminal::FrameHoldingTerminal;
use crate::infrastructure::pty_launcher::{PtyLauncher, PtyResizer};

pub struct EndlessPtySession {
    resizer: Box<dyn PtyResizer>,
    writer: Box<dyn Write + Send>,
    child: Box<dyn RunningChild>,
    parser: Arc<Mutex<FrameHoldingTerminal>>,
}

impl EndlessPtySession {
    const READ_CHUNK: usize = 8192;
    const SCROLLBACK: usize = 0;

    pub fn spawn(
        launcher: &dyn PtyLauncher,
        launch: &SessionLaunch,
        size: PaneSize,
        clock: impl Clock + 'static,
    ) -> Result<Self, SessionNotLaunched> {
        if launch.argv().is_empty() {
            return Err(Self::not_launched("empty command"));
        }
        let (reader, writer, resizer, child) = launcher
            .launched(launch.argv(), launch.directory(), launch.environment(), size)
            .map_err(|error| Self::not_launched(&error.to_string()))?
            .into_parts();
        let parser = Arc::new(Mutex::new(FrameHoldingTerminal::new(
            size.rows(),
            size.columns(),
            Self::SCROLLBACK,
            clock,
        )));
        Self::start_reading(reader, Arc::clone(&parser));

        Ok(Self {
            resizer,
            writer,
            child,
            parser,
        })
    }

    pub fn write(&mut self, bytes: &[u8]) {
        self.writer.write_all(bytes).ok();
        self.writer.flush().ok();
    }

    pub fn resize(&mut self, size: PaneSize) {
        self.resizer.resize(size).ok();
        self.parser().resize(size.rows(), size.columns());
    }

    pub fn has_ended(&mut self) -> bool {
        !matches!(self.child.try_wait(), Ok(None))
    }

    pub fn with_screen<R>(&self, read: impl FnOnce(&Screen) -> R) -> R {
        read(self.parser().live())
    }

    pub fn with_painted_screen<R>(&self, read: impl FnOnce(&Screen) -> R) -> R {
        read(self.parser().painted())
    }

    fn start_reading(mut reader: Box<dyn Read + Send>, parser: Arc<Mutex<FrameHoldingTerminal>>) {
        thread::spawn(move || {
            let mut chunk = [0u8; Self::READ_CHUNK];
            while let Ok(read) = reader.read(&mut chunk) {
                if read == 0 {
                    return;
                }
                parser
                    .lock()
                    .unwrap_or_else(PoisonError::into_inner)
                    .process(&chunk[..read]);
            }
        });
    }

    fn parser(&self) -> MutexGuard<'_, FrameHoldingTerminal> {
        self.parser.lock().unwrap_or_else(PoisonError::into_inner)
    }

    fn not_launched(reason: &str) -> SessionNotLaunched {
        SessionNotLaunched {
            reason: reason.to_string(),
        }
    }
}

impl Drop for EndlessPtySession {
    fn drop(&mut self) {
        self.child.kill().ok();
        self.child.wait().ok();
    }
}
