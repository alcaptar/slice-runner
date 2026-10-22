use crate::application::queries::read_slice_detail::SliceDetail;
use crate::domain::comparison_opener::ComparisonOpener;
use crate::domain::comparison_opening::ComparisonOpening;
use crate::domain::slice_board::SliceBoard;

pub struct OpenComparison<O: ComparisonOpener> {
    opener: O,
}

impl<O: ComparisonOpener> OpenComparison<O> {
    pub fn new(opener: O) -> Self {
        Self { opener }
    }

    pub fn execute(&mut self, board: &SliceBoard, detail: Option<&SliceDetail>) -> ComparisonOpening {
        let Some(path) = detail
            .and_then(|detail| board.row(detail.key()))
            .and_then(|row| row.comparison())
        else {
            return ComparisonOpening::Unavailable;
        };

        match self.opener.open(path) {
            Ok(()) => ComparisonOpening::Opened,
            Err(_) => ComparisonOpening::Failed,
        }
    }
}
