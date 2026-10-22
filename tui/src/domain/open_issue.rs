#[derive(Debug, Clone, PartialEq, Eq)]
pub struct OpenIssue {
    number: u64,
    body: String,
    title: String,
}

impl OpenIssue {
    pub fn new(number: u64, body: &str, title: &str) -> Self {
        Self {
            number,
            body: body.to_string(),
            title: title.to_string(),
        }
    }

    pub fn number(&self) -> u64 {
        self.number
    }

    pub fn body(&self) -> &str {
        &self.body
    }

    pub fn title(&self) -> &str {
        &self.title
    }
}
