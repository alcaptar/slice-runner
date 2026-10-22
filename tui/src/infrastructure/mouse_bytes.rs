use crossterm::event::{MouseButton, MouseEvent, MouseEventKind};
use ratatui::layout::{Position, Rect};
use ratatui::widgets::Block;
use vt100::{MouseProtocolEncoding, MouseProtocolMode, Screen};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Report {
    Press,
    Drag,
    Release,
    WheelUp,
    WheelDown,
}

impl Report {
    fn of(kind: MouseEventKind) -> Option<Self> {
        match kind {
            MouseEventKind::Down(MouseButton::Left) => Some(Self::Press),
            MouseEventKind::Drag(MouseButton::Left) => Some(Self::Drag),
            MouseEventKind::Up(MouseButton::Left) => Some(Self::Release),
            MouseEventKind::ScrollUp => Some(Self::WheelUp),
            MouseEventKind::ScrollDown => Some(Self::WheelDown),
            MouseEventKind::Down(MouseButton::Right | MouseButton::Middle)
            | MouseEventKind::Drag(MouseButton::Right | MouseButton::Middle)
            | MouseEventKind::Up(MouseButton::Right | MouseButton::Middle)
            | MouseEventKind::Moved
            | MouseEventKind::ScrollLeft
            | MouseEventKind::ScrollRight => None,
        }
    }

    fn button_code(self) -> u8 {
        match self {
            Self::Press | Self::Release => 0,
            Self::Drag => 32,
            Self::WheelUp => 64,
            Self::WheelDown => 65,
        }
    }

    fn terminator(self) -> char {
        match self {
            Self::Release => 'm',
            Self::Press | Self::Drag | Self::WheelUp | Self::WheelDown => 'M',
        }
    }

    fn is_asked_for_by(self, mode: MouseProtocolMode) -> bool {
        match mode {
            MouseProtocolMode::None | MouseProtocolMode::Press => false,
            MouseProtocolMode::PressRelease => self != Self::Drag,
            MouseProtocolMode::ButtonMotion | MouseProtocolMode::AnyMotion => true,
        }
    }
}

#[derive(Debug, Default)]
pub struct MouseBytes {
    pressed_inside: bool,
}

impl MouseBytes {
    pub fn of(&mut self, event: MouseEvent, panel: Rect, screen: &Screen) -> Vec<u8> {
        let Some(report) = Report::of(event.kind) else {
            return Vec::new();
        };
        let interior = Block::bordered().inner(panel);
        let inside = interior.contains(Position::new(event.column, event.row));
        if report == Report::Press {
            self.pressed_inside = inside;
        }
        let tracked = inside || self.pressed_inside;
        if report == Report::Release {
            self.pressed_inside = false;
        }
        let asked = report.is_asked_for_by(screen.mouse_protocol_mode())
            && screen.mouse_protocol_encoding() == MouseProtocolEncoding::Sgr;
        if !tracked || !asked || interior.is_empty() {
            return Vec::new();
        }
        let column = event.column.clamp(interior.left(), interior.right() - 1) - interior.left() + 1;
        let row = event.row.clamp(interior.top(), interior.bottom() - 1) - interior.top() + 1;

        format!("\x1b[<{};{column};{row}{}", report.button_code(), report.terminator()).into_bytes()
    }
}
