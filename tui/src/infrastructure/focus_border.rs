use ratatui::style::{Color, Style};

pub struct FocusBorder;

impl FocusBorder {
    const FOCUSED: Color = Color::Cyan;

    pub fn style(focused: bool) -> Style {
        if focused {
            Style::new().fg(Self::FOCUSED)
        } else {
            Style::new()
        }
    }
}
