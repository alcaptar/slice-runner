use serde_json::Value;

use crate::domain::errors::IssuesUnread;

pub struct RepoViewPayload;

impl RepoViewPayload {
    pub const KEY: &'static str = "nameWithOwner";

    pub fn parsed(raw: &str) -> Result<String, IssuesUnread> {
        let Ok(Value::Object(fields)) = serde_json::from_str::<Value>(raw) else {
            return Err(IssuesUnread::NotJson {
                output: raw.to_string(),
            });
        };
        if let Some(key) = fields.keys().find(|key| key.as_str() != Self::KEY) {
            return Err(Self::wrong(key, "unknown key"));
        }

        fields
            .get(Self::KEY)
            .and_then(Value::as_str)
            .map(str::to_string)
            .ok_or_else(|| Self::wrong(Self::KEY, "expected a string"))
    }

    fn wrong(key: &str, reason: &str) -> IssuesUnread {
        IssuesUnread::WrongValue {
            key: key.to_string(),
            reason: reason.to_string(),
        }
    }
}
