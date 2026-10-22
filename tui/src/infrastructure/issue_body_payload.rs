use serde_json::{Map, Value};

use crate::domain::errors::IssuesUnread;
use crate::domain::issue_text::IssueText;

pub struct IssueBodyPayload;

impl IssueBodyPayload {
    pub const KEYS: [&'static str; 2] = ["body", "title"];

    pub fn parsed(raw: &str) -> Result<IssueText, IssuesUnread> {
        let Ok(Value::Object(fields)) = serde_json::from_str::<Value>(raw) else {
            return Err(IssuesUnread::NotJson {
                output: raw.to_string(),
            });
        };
        if let Some(key) = fields.keys().find(|key| !Self::KEYS.contains(&key.as_str())) {
            return Err(Self::wrong(key, "unknown key"));
        }

        Ok(IssueText::new(
            &Self::text_of(&fields, "body")?,
            &Self::text_of(&fields, "title")?,
        ))
    }

    fn text_of(fields: &Map<String, Value>, key: &str) -> Result<String, IssuesUnread> {
        fields
            .get(key)
            .and_then(Value::as_str)
            .map(str::to_string)
            .ok_or_else(|| Self::wrong(key, "expected a string"))
    }

    fn wrong(key: &str, reason: &str) -> IssuesUnread {
        IssuesUnread::WrongValue {
            key: key.to_string(),
            reason: reason.to_string(),
        }
    }
}
