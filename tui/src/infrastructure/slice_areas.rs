use ratatui::layout::{Position, Rect};

use crate::domain::slice_key::SliceKey;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SliceAreas {
    rows: Vec<(SliceKey, Rect)>,
}

impl SliceAreas {
    pub fn new(rows: Vec<(SliceKey, Rect)>) -> Self {
        Self { rows }
    }

    pub fn empty() -> Self {
        Self::new(Vec::new())
    }

    pub fn at(&self, column: u16, row: u16) -> Option<&SliceKey> {
        let point = Position::new(column, row);

        self.rows
            .iter()
            .find(|(_, area)| area.contains(point))
            .map(|(key, _)| key)
    }
}
