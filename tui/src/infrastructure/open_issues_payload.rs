use serde_json::{Map, Value};

use crate::domain::errors::IssuesUnread;
use crate::domain::open_issue::OpenIssue;

pub struct OpenIssuesPayload;

impl OpenIssuesPayload {
    pub const KEYS: [&'static str; 3] = ["number", "body", "title"];

    pub fn parsed(raw: &str) -> Result<Vec<OpenIssue>, IssuesUnread> {
        match serde_json::from_str::<Value>(raw) {
            Ok(Value::Array(items)) => items.iter().map(Self::issue_of).collect(),
            Ok(_) | Err(_) => Err(IssuesUnread::NotJson {
                output: raw.to_string(),
            }),
        }
    }

    fn issue_of(item: &Value) -> Result<OpenIssue, IssuesUnread> {
        let Value::Object(fields) = item else {
            return Err(Self::wrong("item", "expected an object"));
        };
        Self::reject_unknown(fields)?;
        let number = fields
            .get("number")
            .and_then(Value::as_u64)
            .ok_or_else(|| Self::wrong("number", "expected a whole number"))?;
        let body = fields
            .get("body")
            .and_then(Value::as_str)
            .ok_or_else(|| Self::wrong("body", "expected a string"))?;

        let title = fields
            .get("title")
            .and_then(Value::as_str)
            .ok_or_else(|| Self::wrong("title", "expected a string"))?;

        Ok(OpenIssue::new(number, body, title))
    }

    fn reject_unknown(fields: &Map<String, Value>) -> Result<(), IssuesUnread> {
        match fields.keys().find(|key| !Self::KEYS.contains(&key.as_str())) {
            Some(key) => Err(Self::wrong(key, "unknown key")),
            None => Ok(()),
        }
    }

    fn wrong(key: &str, reason: &str) -> IssuesUnread {
        IssuesUnread::WrongValue {
            key: key.to_string(),
            reason: reason.to_string(),
        }
    }
}
