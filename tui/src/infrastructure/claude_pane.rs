use ratatui::Frame;
use ratatui::layout::Rect;
use ratatui::widgets::Block;
use tui_term::widget::PseudoTerminal;

use crate::infrastructure::endless_pty_session::EndlessPtySession;
use crate::infrastructure::focus_border::FocusBorder;

pub struct ClaudePane;

impl ClaudePane {
    pub fn render(frame: &mut Frame, area: Rect, session: &mut EndlessPtySession, focused: bool) {
        let title = if session.has_ended() {
            "claude session ended · ctrl+q focus"
        } else {
            "claude · ctrl+q focus"
        };
        let block = Block::bordered().title(title).border_style(FocusBorder::style(focused));
        session.with_painted_screen(|screen| frame.render_widget(PseudoTerminal::new(screen).block(block), area));
    }
}
