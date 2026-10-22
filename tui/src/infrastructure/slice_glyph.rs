use ratatui::style::{Color, Style};
use ratatui::text::Span;

use crate::domain::attention::Attention;
use crate::domain::closure::Closure;
use crate::domain::slice_row::SliceRow;

pub struct SliceGlyph;

impl SliceGlyph {
    const SPINNER: [&'static str; 4] = ["◐", "◓", "◑", "◒"];
    const SPINNER_FRAME_MILLIS: u64 = 150;
    pub const GONE: &'static str = "●";

    pub fn of(row: &SliceRow, now: u64) -> Span<'static> {
        let closure = row.latest().closure();
        let symbol = match closure {
            Closure::InProgress if row.process_is_gone() => Self::GONE,
            Closure::InProgress => Self::spinner(now),
            Closure::Pending => "○",
            Closure::AwaitingMerge => "◆",
            Closure::Blocked(_) => "✕",
            Closure::Aborted(_) => "⊘",
            Closure::Merged => "✓",
        };

        Span::styled(symbol, Self::style_of(closure))
    }

    pub fn spinner(now: u64) -> &'static str {
        let frame = usize::try_from(now / Self::SPINNER_FRAME_MILLIS).unwrap_or(0) % Self::SPINNER.len();

        Self::SPINNER[frame]
    }

    pub fn style_of(closure: Closure) -> Style {
        Style::new().fg(match closure {
            Closure::InProgress => Color::Cyan,
            Closure::Pending => Color::DarkGray,
            Closure::AwaitingMerge => Color::Yellow,
            Closure::Blocked(_) | Closure::Aborted(_) => Color::Red,
            Closure::Merged => Color::Green,
        })
    }

    pub fn heading_style(attention: Attention) -> Style {
        Style::new().fg(match attention {
            Attention::NeedsYou => Color::Yellow,
            Attention::Running => Color::Cyan,
            Attention::Pending => Color::DarkGray,
            Attention::Finished => Color::Green,
        })
    }

    pub fn warning() -> Style {
        Style::new().fg(Color::Yellow)
    }

    pub fn alarm() -> Style {
        Style::new().fg(Color::Red)
    }

    pub fn quiet() -> Style {
        Style::new().fg(Color::DarkGray)
    }
}
