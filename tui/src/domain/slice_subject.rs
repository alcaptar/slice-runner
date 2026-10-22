use crate::domain::parent::Parent;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SliceSubject {
    repo: String,
    issue: u64,
    slice_id: String,
    parent: Parent,
    name: Option<String>,
}

impl SliceSubject {
    pub fn new(repo: &str, issue: u64, slice_id: &str, parent: Parent, name: Option<&str>) -> Self {
        Self {
            repo: repo.to_string(),
            issue,
            slice_id: slice_id.to_string(),
            parent,
            name: name.map(str::to_string),
        }
    }

    pub fn repo(&self) -> &str {
        &self.repo
    }

    pub fn issue(&self) -> u64 {
        self.issue
    }

    pub fn slice_id(&self) -> &str {
        &self.slice_id
    }

    pub fn parent(&self) -> Parent {
        self.parent
    }

    pub fn name(&self) -> Option<&str> {
        self.name.as_deref()
    }

    pub fn number(&self) -> &str {
        self.slice_id.rsplit('-').next().unwrap_or(&self.slice_id)
    }

    pub fn known_over(&self, earlier: &Self) -> Self {
        Self {
            parent: self.parent.or_known(earlier.parent),
            name: self.name.clone().or_else(|| earlier.name.clone()),
            ..self.clone()
        }
    }
}
