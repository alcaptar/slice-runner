use crate::domain::comparison_opening::ComparisonOpening;
use crate::domain::slice_key::SliceKey;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SliceDetail {
    key: SliceKey,
    opening_failed: bool,
}

impl SliceDetail {
    pub fn key(&self) -> &SliceKey {
        &self.key
    }

    pub fn opening_failed(&self) -> bool {
        self.opening_failed
    }

    pub fn after(self, opening: ComparisonOpening) -> Self {
        match opening {
            ComparisonOpening::Failed => Self {
                opening_failed: true,
                ..self
            },
            ComparisonOpening::Opened => Self {
                opening_failed: false,
                ..self
            },
            ComparisonOpening::Unavailable => self,
        }
    }
}

pub struct ReadSliceDetail;

impl ReadSliceDetail {
    pub fn execute(key: SliceKey) -> SliceDetail {
        SliceDetail {
            key,
            opening_failed: false,
        }
    }
}
