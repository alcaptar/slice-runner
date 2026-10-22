use crate::domain::errors::WorkspaceIdRejected;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WorkspaceId {
    text: String,
}

impl WorkspaceId {
    const GROUP_LENGTHS: [usize; 5] = [8, 4, 4, 4, 12];

    pub fn parse(text: &str) -> Result<Self, WorkspaceIdRejected> {
        let groups: Vec<&str> = text.split('-').collect();
        let well_formed = groups.len() == Self::GROUP_LENGTHS.len()
            && groups
                .iter()
                .zip(Self::GROUP_LENGTHS)
                .all(|(group, length)| group.len() == length && group.chars().all(|digit| digit.is_ascii_hexdigit()));
        if !well_formed {
            return Err(WorkspaceIdRejected { text: text.to_string() });
        }

        Ok(Self {
            text: text.to_ascii_lowercase(),
        })
    }

    pub fn as_str(&self) -> &str {
        &self.text
    }
}
