use ratatui::layout::{Constraint, Layout, Rect};
use ratatui::widgets::Block;

use crate::domain::pane_size::PaneSize;

pub struct SplitScreen;

impl SplitScreen {
    pub fn areas(window: Rect) -> (Rect, Rect) {
        let [claude, board] =
            Layout::horizontal([Constraint::Percentage(50), Constraint::Percentage(50)]).areas(window);

        (claude, board)
    }

    pub fn pane_size(window: Rect) -> PaneSize {
        let (claude, _) = Self::areas(window);
        let inside = Block::bordered().inner(claude);

        PaneSize::new(inside.height, inside.width)
    }
}
