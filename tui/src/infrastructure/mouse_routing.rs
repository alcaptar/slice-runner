use crossterm::event::{MouseButton, MouseEvent, MouseEventKind};
use ratatui::layout::{Position, Rect};
use vt100::Screen;

use crate::domain::slice_key::SliceKey;
use crate::infrastructure::key_routing::Focus;
use crate::infrastructure::mouse_bytes::MouseBytes;
use crate::infrastructure::slice_areas::SliceAreas;
use crate::infrastructure::split_screen::SplitScreen;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum MouseEffect {
    ToClaude(Vec<u8>),
    Open(SliceKey),
    Nothing,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct MouseAction {
    focus: Option<Focus>,
    effect: MouseEffect,
}

impl MouseAction {
    pub fn new(focus: Option<Focus>, effect: MouseEffect) -> Self {
        Self { focus, effect }
    }

    pub fn focus(&self) -> Option<Focus> {
        self.focus
    }

    pub fn effect(&self) -> &MouseEffect {
        &self.effect
    }
}

pub struct MouseRouting;

impl MouseRouting {
    pub fn route(
        event: MouseEvent,
        window: Rect,
        mouse: &mut MouseBytes,
        screen: &Screen,
        slices: &SliceAreas,
    ) -> MouseAction {
        let (claude_area, board_area) = SplitScreen::areas(window);
        let bytes = mouse.of(event, claude_area, screen);
        let effect = if bytes.is_empty() {
            Self::opening(event, slices)
        } else {
            MouseEffect::ToClaude(bytes)
        };

        MouseAction::new(Self::focus_of(event, claude_area, board_area), effect)
    }

    fn opening(event: MouseEvent, slices: &SliceAreas) -> MouseEffect {
        if event.kind != MouseEventKind::Down(MouseButton::Left) {
            return MouseEffect::Nothing;
        }

        slices
            .at(event.column, event.row)
            .map_or(MouseEffect::Nothing, |key| MouseEffect::Open(key.clone()))
    }

    fn focus_of(event: MouseEvent, claude_area: Rect, board_area: Rect) -> Option<Focus> {
        if event.kind != MouseEventKind::Down(MouseButton::Left) {
            return None;
        }
        let point = Position::new(event.column, event.row);
        if claude_area.contains(point) {
            return Some(Focus::Claude);
        }

        board_area.contains(point).then_some(Focus::Board)
    }
}
