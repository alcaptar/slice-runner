use std::collections::BTreeMap;

use crate::domain::activity_line::ActivityLine;
use crate::domain::attention::Attention;
use crate::domain::follow_entry::FollowEntry;
use crate::domain::follow_line::FollowLine;
use crate::domain::liveness::Liveness;
use crate::domain::parent::Parent;
use crate::domain::process_probe::ProcessProbe;
use crate::domain::slice_key::SliceKey;
use crate::domain::slice_row::SliceRow;
use crate::domain::workspace_binding::WorkspaceBinding;

#[derive(Debug, Clone, PartialEq)]
pub struct FeatureGroup {
    repo: String,
    parent: Parent,
    rows: Vec<SliceRow>,
}

impl FeatureGroup {
    pub fn repo(&self) -> &str {
        &self.repo
    }

    pub fn parent(&self) -> Parent {
        self.parent
    }

    pub fn rows(&self) -> &[SliceRow] {
        &self.rows
    }

    pub fn slices(&self) -> usize {
        self.rows.len()
    }

    pub fn spent_usd(&self) -> f64 {
        self.rows.iter().map(|row| row.latest().spend().cost_usd()).sum()
    }

    pub fn needing_you(&self) -> usize {
        self.rows_in(Attention::NeedsYou).len()
    }

    pub fn rows_in(&self, attention: Attention) -> Vec<&SliceRow> {
        self.rows.iter().filter(|row| row.attention() == attention).collect()
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct SliceBoard {
    rows: Vec<SliceRow>,
}

impl SliceBoard {
    pub fn empty() -> Self {
        Self { rows: Vec::new() }
    }

    pub fn with_entry(self, entry: FollowEntry) -> Self {
        match entry {
            FollowEntry::Transition(line) => self.with_line(line),
            FollowEntry::Activity(line) => self.with_activity(line),
        }
    }

    pub fn with_line(mut self, line: FollowLine) -> Self {
        match self.rows.iter().position(|row| row.is_the_slice_of(&line)) {
            Some(index) => self.rows[index] = self.rows[index].with_line(line),
            None => self.rows.push(SliceRow::first(line)),
        }

        self
    }

    fn with_activity(mut self, line: ActivityLine) -> Self {
        if let Some(index) = self.rows.iter().position(|row| row.key() == line.key()) {
            self.rows[index] = self.rows[index].with_activity(line);
        }

        self
    }

    pub fn probed(self, probe: &impl ProcessProbe) -> Self {
        Self {
            rows: self
                .rows
                .iter()
                .map(|row| match (row.is_running(), row.pid()) {
                    (true, Some(pid)) => row.with_liveness(probe.liveness_of(pid)),
                    (true | false, None) | (false, Some(_)) => row.with_liveness(Liveness::Unchecked),
                })
                .collect(),
        }
    }

    pub fn shown_for(&self, repo: &str, binding: WorkspaceBinding) -> Self {
        Self {
            rows: self
                .rows
                .iter()
                .filter(|row| binding.admits(row, repo))
                .cloned()
                .collect(),
        }
    }

    pub fn row(&self, key: &SliceKey) -> Option<&SliceRow> {
        self.rows.iter().find(|row| row.key() == key)
    }

    pub fn after(&self, current: Option<&SliceKey>) -> Option<SliceKey> {
        let keys = self.keys_in_painted_order();
        match Self::position_of(&keys, current) {
            Some(index) => keys.get(index + 1).or_else(|| keys.get(index)).cloned(),
            None => keys.first().cloned(),
        }
    }

    pub fn before(&self, current: Option<&SliceKey>) -> Option<SliceKey> {
        let keys = self.keys_in_painted_order();
        match Self::position_of(&keys, current) {
            Some(index) => keys.get(index.saturating_sub(1)).cloned(),
            None => keys.first().cloned(),
        }
    }

    fn keys_in_painted_order(&self) -> Vec<SliceKey> {
        self.groups()
            .iter()
            .flat_map(|group| group.rows().iter().map(|row| row.key().clone()).collect::<Vec<_>>())
            .collect()
    }

    fn position_of(keys: &[SliceKey], current: Option<&SliceKey>) -> Option<usize> {
        current.and_then(|current| keys.iter().position(|key| key == current))
    }

    pub fn groups(&self) -> Vec<FeatureGroup> {
        let mut grouped: BTreeMap<(String, Parent), Vec<SliceRow>> = BTreeMap::new();
        for row in &self.rows {
            grouped
                .entry((row.repo().to_string(), row.parent()))
                .or_default()
                .push(row.clone());
        }

        grouped
            .into_iter()
            .map(|((repo, parent), mut rows)| {
                rows.sort_by(|left, right| {
                    (left.attention(), left.subject().slice_id()).cmp(&(right.attention(), right.subject().slice_id()))
                });
                FeatureGroup { repo, parent, rows }
            })
            .collect()
    }
}
