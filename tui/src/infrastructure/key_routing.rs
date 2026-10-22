use crossterm::event::{KeyCode, KeyEvent, KeyEventKind, KeyModifiers};
use vt100::Screen;

use crate::infrastructure::key_bytes::KeyBytes;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Order {
    Quit,
    Previous,
    Next,
    Open,
    Close,
    OpenComparison,
    Nothing,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Focus {
    Claude,
    Board,
}

impl Focus {
    pub fn toggled(self) -> Self {
        match self {
            Self::Claude => Self::Board,
            Self::Board => Self::Claude,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Routed {
    ToClaude(Vec<u8>),
    Board(Order),
    ToggleFocus,
    Ignored,
}

pub struct KeyRouting;

impl KeyRouting {
    const CONTROL_BACKSLASH: [KeyCode; 2] = [KeyCode::Char('4'), KeyCode::Char('\\')];
    const TOGGLE_FOCUS: KeyCode = KeyCode::Char('q');
    const BINDINGS: [(KeyCode, Order); 8] = [
        (KeyCode::Char('q'), Order::Quit),
        (KeyCode::Up, Order::Previous),
        (KeyCode::Char('k'), Order::Previous),
        (KeyCode::Down, Order::Next),
        (KeyCode::Char('j'), Order::Next),
        (KeyCode::Enter, Order::Open),
        (KeyCode::Esc, Order::Close),
        (KeyCode::Char('v'), Order::OpenComparison),
    ];

    pub fn route(focus: Focus, key: KeyEvent, screen: &Screen) -> Routed {
        if key.kind != KeyEventKind::Press {
            return Routed::Ignored;
        }
        let control = key.modifiers.contains(KeyModifiers::CONTROL);
        if control && key.code == Self::TOGGLE_FOCUS {
            return Routed::ToggleFocus;
        }
        if control && Self::CONTROL_BACKSLASH.contains(&key.code) {
            return Routed::Ignored;
        }

        match focus {
            Focus::Claude => Routed::ToClaude(KeyBytes::of(key, screen)),
            Focus::Board => Routed::Board(Self::order_of(key)),
        }
    }

    fn order_of(key: KeyEvent) -> Order {
        if key.code == KeyCode::Char('c') && key.modifiers.contains(KeyModifiers::CONTROL) {
            return Order::Quit;
        }

        Self::BINDINGS
            .iter()
            .find(|(code, _)| *code == key.code)
            .map_or(Order::Nothing, |(_, order)| *order)
    }
}
