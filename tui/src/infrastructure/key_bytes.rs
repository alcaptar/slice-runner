use crossterm::event::{KeyCode, KeyEvent, KeyModifiers};
use vt100::Screen;

pub struct KeyBytes;

impl KeyBytes {
    const PASTE_START: &'static [u8] = b"\x1b[200~";
    const PASTE_END: &'static [u8] = b"\x1b[201~";
    const CONTROL_MASK: u8 = 0x1f;
    const LINE_KILL: u8 = 0x15;
    const LINE_FEED: u8 = 0x0a;
    const ESCAPE: &'static [u8] = b"\x1b";

    pub fn of(key: KeyEvent, screen: &Screen) -> Vec<u8> {
        if let Some(bytes) = Self::chorded(key) {
            return bytes;
        }
        let bytes = Self::unmodified(key, screen);
        if key.modifiers.contains(KeyModifiers::ALT) && !bytes.is_empty() {
            return [Self::ESCAPE, bytes.as_slice()].concat();
        }

        bytes
    }

    fn chorded(key: KeyEvent) -> Option<Vec<u8>> {
        if key.code == KeyCode::Backspace && key.modifiers.contains(KeyModifiers::SUPER) {
            return Some(vec![Self::LINE_KILL]);
        }
        if key.code == KeyCode::Enter && key.modifiers.contains(KeyModifiers::SHIFT) {
            return Some(vec![Self::LINE_FEED]);
        }

        None
    }

    fn unmodified(key: KeyEvent, screen: &Screen) -> Vec<u8> {
        match key.code {
            KeyCode::Esc => b"\x1b".to_vec(),
            KeyCode::Enter => b"\r".to_vec(),
            KeyCode::Tab => b"\t".to_vec(),
            KeyCode::Backspace => vec![0x7f],
            KeyCode::Up => Self::arrow(b'A', screen),
            KeyCode::Down => Self::arrow(b'B', screen),
            KeyCode::Right => Self::arrow(b'C', screen),
            KeyCode::Left => Self::arrow(b'D', screen),
            KeyCode::Home => Self::arrow(b'H', screen),
            KeyCode::End => Self::arrow(b'F', screen),
            KeyCode::BackTab => b"\x1b[Z".to_vec(),
            KeyCode::Insert => b"\x1b[2~".to_vec(),
            KeyCode::Delete => b"\x1b[3~".to_vec(),
            KeyCode::PageUp => b"\x1b[5~".to_vec(),
            KeyCode::PageDown => b"\x1b[6~".to_vec(),
            KeyCode::F(number) => Self::function(number),
            KeyCode::Char(character) => Self::character(character, key.modifiers),
            KeyCode::Null
            | KeyCode::CapsLock
            | KeyCode::ScrollLock
            | KeyCode::NumLock
            | KeyCode::PrintScreen
            | KeyCode::Pause
            | KeyCode::Menu
            | KeyCode::KeypadBegin
            | KeyCode::Media(_)
            | KeyCode::Modifier(_) => Vec::new(),
        }
    }

    pub fn of_paste(text: &str, screen: &Screen) -> Vec<u8> {
        if screen.bracketed_paste() {
            return [Self::PASTE_START, text.as_bytes(), Self::PASTE_END].concat();
        }

        text.replace("\r\n", "\r").replace('\n', "\r").into_bytes()
    }

    fn arrow(letter: u8, screen: &Screen) -> Vec<u8> {
        let introducer = if screen.application_cursor() { b'O' } else { b'[' };

        vec![0x1b, introducer, letter]
    }

    fn function(number: u8) -> Vec<u8> {
        let sequence: &[u8] = match number {
            1 => b"\x1bOP",
            2 => b"\x1bOQ",
            3 => b"\x1bOR",
            4 => b"\x1bOS",
            5 => b"\x1b[15~",
            6 => b"\x1b[17~",
            7 => b"\x1b[18~",
            8 => b"\x1b[19~",
            9 => b"\x1b[20~",
            10 => b"\x1b[21~",
            11 => b"\x1b[23~",
            12 => b"\x1b[24~",
            _ => b"",
        };

        sequence.to_vec()
    }

    fn character(character: char, modifiers: KeyModifiers) -> Vec<u8> {
        if modifiers.contains(KeyModifiers::CONTROL) && character.is_ascii_alphabetic() {
            return vec![character.to_ascii_lowercase() as u8 & Self::CONTROL_MASK];
        }

        character.to_string().into_bytes()
    }
}
