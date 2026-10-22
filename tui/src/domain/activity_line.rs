use crate::domain::slice_key::SliceKey;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Actor {
    Implementer,
    Judge,
    Controls,
}

impl Actor {
    pub fn parse(text: &str) -> Option<Self> {
        match text {
            "implementer" => Some(Self::Implementer),
            "judge" => Some(Self::Judge),
            "controls" => Some(Self::Controls),
            _ => None,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ActivityLine {
    key: SliceKey,
    at: u64,
    actor: Actor,
    tool: String,
    target: String,
}

impl ActivityLine {
    pub fn new(key: SliceKey, at: u64, actor: Actor, tool: &str, target: &str) -> Self {
        Self {
            key,
            at,
            actor,
            tool: tool.to_string(),
            target: target.to_string(),
        }
    }

    pub fn key(&self) -> &SliceKey {
        &self.key
    }

    pub fn at(&self) -> u64 {
        self.at
    }

    pub fn actor(&self) -> Actor {
        self.actor
    }

    pub fn tool(&self) -> &str {
        &self.tool
    }

    pub fn target(&self) -> &str {
        &self.target
    }
}
