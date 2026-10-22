use std::io::{self, Write, stdout};

use crossterm::event::{DisableBracketedPaste, EnableBracketedPaste};
use crossterm::execute;
use ratatui::DefaultTerminal;

pub struct TerminalSession {
    terminal: DefaultTerminal,
}

impl TerminalSession {
    const MOUSE_OPEN: &'static [u8] = b"\x1b[?1000h\x1b[?1002h\x1b[?1006h";
    const MOUSE_CLOSE: &'static [u8] = b"\x1b[?1006l\x1b[?1002l\x1b[?1000l";

    const KEYBOARD_PROTOCOL_OPEN: &'static [u8] = b"\x1b[>1u";
    const KEYBOARD_PROTOCOL_CLOSE: &'static [u8] = b"\x1b[<1u";

    pub fn open() -> io::Result<Self> {
        let terminal = ratatui::try_init()?;
        if let Err(error) = Self::write_open_sequence(&mut stdout()) {
            ratatui::restore();
            return Err(error);
        }

        Ok(Self { terminal })
    }

    pub fn write_open_sequence(out: &mut impl Write) -> io::Result<()> {
        execute!(out, EnableBracketedPaste)?;
        out.write_all(Self::MOUSE_OPEN)?;
        out.write_all(Self::KEYBOARD_PROTOCOL_OPEN)?;

        out.flush()
    }

    pub fn write_close_sequence(out: &mut impl Write) -> io::Result<()> {
        out.write_all(Self::KEYBOARD_PROTOCOL_CLOSE)?;
        out.write_all(Self::MOUSE_CLOSE)?;
        execute!(out, DisableBracketedPaste)?;

        out.flush()
    }

    pub fn terminal(&mut self) -> &mut DefaultTerminal {
        &mut self.terminal
    }
}

impl Drop for TerminalSession {
    fn drop(&mut self) {
        Self::write_close_sequence(&mut stdout()).ok();
        ratatui::restore();
    }
}
