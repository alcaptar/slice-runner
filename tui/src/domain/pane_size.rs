#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct PaneSize {
    rows: u16,
    columns: u16,
}

impl PaneSize {
    pub fn new(rows: u16, columns: u16) -> Self {
        Self { rows, columns }
    }

    pub fn rows(self) -> u16 {
        self.rows
    }

    pub fn columns(self) -> u16 {
        self.columns
    }
}
