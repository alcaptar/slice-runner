#[derive(Debug, Clone, PartialEq, Eq)]
pub struct IssueText {
    body: String,
    title: String,
}

impl IssueText {
    pub fn new(body: &str, title: &str) -> Self {
        Self {
            body: body.to_string(),
            title: title.to_string(),
        }
    }

    pub fn body(&self) -> &str {
        &self.body
    }

    pub fn title(&self) -> &str {
        &self.title
    }
}
