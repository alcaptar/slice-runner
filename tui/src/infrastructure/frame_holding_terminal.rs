use std::time::{Duration, Instant};

use vt100::{Callbacks, Parser, Screen};

use crate::domain::clock::Clock;

pub struct FrameHoldingTerminal {
    parser: Parser<FrameMarks>,
}

impl FrameHoldingTerminal {
    pub fn new(rows: u16, columns: u16, scrollback: usize, clock: impl Clock + 'static) -> Self {
        Self {
            parser: Parser::new_with_callbacks(rows, columns, scrollback, FrameMarks::new(Box::new(clock))),
        }
    }

    pub fn process(&mut self, bytes: &[u8]) {
        self.parser.process(bytes);
    }

    pub fn resize(&mut self, rows: u16, columns: u16) {
        self.parser.callbacks_mut().release();
        self.parser.screen_mut().set_size(rows, columns);
    }

    pub fn live(&self) -> &Screen {
        self.parser.screen()
    }

    pub fn painted(&self) -> &Screen {
        self.parser.callbacks().held().unwrap_or_else(|| self.live())
    }
}

struct FrameMarks {
    clock: Box<dyn Clock>,
    open: Option<OpenFrame>,
}

struct OpenFrame {
    screen: Screen,
    opened_at: Instant,
}

impl FrameMarks {
    const SYNCHRONIZED_OUTPUT: u16 = 2026;
    const HOLD_LIMIT: Duration = Duration::from_millis(200);

    fn new(clock: Box<dyn Clock>) -> Self {
        Self { clock, open: None }
    }

    fn release(&mut self) {
        self.open = None;
    }

    fn held(&self) -> Option<&Screen> {
        self.open
            .as_ref()
            .filter(|frame| self.clock.now().saturating_duration_since(frame.opened_at) < Self::HOLD_LIMIT)
            .map(|frame| &frame.screen)
    }

    fn concerns_synchronized_output(params: &[&[u16]]) -> bool {
        params.iter().any(|param| *param == [Self::SYNCHRONIZED_OUTPUT])
    }
}

impl Callbacks for FrameMarks {
    fn unhandled_csi(&mut self, screen: &mut Screen, i1: Option<u8>, _i2: Option<u8>, params: &[&[u16]], c: char) {
        if i1 != Some(b'?') || !Self::concerns_synchronized_output(params) {
            return;
        }
        match c {
            'h' if self.open.is_none() => {
                self.open = Some(OpenFrame {
                    screen: screen.clone(),
                    opened_at: self.clock.now(),
                });
            }
            'l' => self.release(),
            _ => {}
        }
    }
}
