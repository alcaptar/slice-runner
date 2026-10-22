use serde_json::{Map, Value};

use crate::domain::activity_line::{ActivityLine, Actor};
use crate::domain::closing_reason::ClosingReason;
use crate::domain::closure::Closure;
use crate::domain::errors::FollowLineRejected;
use crate::domain::follow_entry::FollowEntry;
use crate::domain::follow_line::FollowLine;
use crate::domain::parent::Parent;
use crate::domain::rounds::{Round, Rounds};
use crate::domain::slice_key::SliceKey;
use crate::domain::slice_subject::SliceSubject;
use crate::domain::spend::Spend;
use crate::domain::standing::Standing;
use crate::domain::step::Step;
use crate::domain::transition::Transition;

pub struct FollowLinePayload<'a> {
    fields: &'a Map<String, Value>,
}

impl<'a> FollowLinePayload<'a> {
    const VERSION: u64 = 2;
    const ROUND_KEYS: [&'static str; 6] = ["controls", "hygiene", "judge", "ci", "ci_indeterminate", "catch_up"];

    pub fn delivery(raw: &str) -> Result<FollowEntry, FollowLineRejected> {
        match serde_json::from_str::<Value>(raw) {
            Ok(Value::Object(fields)) => FollowLinePayload { fields: &fields }.to_domain(),
            Ok(_) | Err(_) => Err(FollowLineRejected::NotJson { line: raw.to_string() }),
        }
    }

    fn to_domain(&self) -> Result<FollowEntry, FollowLineRejected> {
        match self.optional_number("version")?.unwrap_or(1) {
            Self::VERSION => match self.required_text("kind")? {
                "transition" => self.transition().map(FollowEntry::Transition),
                "activity" => self.activity().map(FollowEntry::Activity),
                kind => Err(FollowLineRejected::UnknownKind { kind: kind.to_string() }),
            },
            version => Err(FollowLineRejected::UnsupportedVersion { version }),
        }
    }

    fn transition(&self) -> Result<FollowLine, FollowLineRejected> {
        let subject = SliceSubject::new(
            self.required_text("repo")?,
            self.required_number("issue")?,
            self.required_text("slice_id")?,
            self.parent()?,
            self.optional_text("name")?,
        );
        let mut transition = Transition::new(
            self.required_number("ts")?,
            self.closure()?,
            self.step()?,
            self.rounds()?,
            Spend::new(self.required_float("cost_usd")?, self.required_float("budget_usd")?),
        );
        if self.optional_flag("round_without_changes")? {
            transition = transition.without_changes();
        }
        if let Some(number) = self.optional_number("pull_request")? {
            transition = transition.with_pull_request(number);
        }
        if let Some(path) = self.optional_text("comparison")? {
            transition = transition.with_comparison(path);
        }
        if let Some(pid) = self.optional_number("pid")? {
            transition = transition.with_pid(u32::try_from(pid).map_err(|_| Self::wrong("pid", "not a process id"))?);
        }

        Ok(FollowLine::new(subject, transition))
    }

    fn activity(&self) -> Result<ActivityLine, FollowLineRejected> {
        let actor =
            Actor::parse(self.required_text("actor")?).ok_or_else(|| Self::wrong("actor", "not a known actor"))?;

        Ok(ActivityLine::new(
            SliceKey::new(self.required_text("repo")?, self.required_number("issue")?),
            self.required_number("ts")?,
            actor,
            self.required_text("tool")?,
            self.required_text("target")?,
        ))
    }

    fn closure(&self) -> Result<Closure, FollowLineRejected> {
        let standing = Standing::parse(self.required_text("standing")?)
            .ok_or_else(|| Self::wrong("standing", "not a known standing"))?;
        let reason = match self.optional_text("reason")? {
            Some(text) => Some(ClosingReason::parse(text).ok_or_else(|| Self::wrong("reason", "not a known reason"))?),
            None => None,
        };

        Closure::of(standing, reason).ok_or_else(|| Self::wrong("reason", "does not belong with the standing"))
    }

    fn step(&self) -> Result<Option<Step>, FollowLineRejected> {
        match self.optional_text("step")? {
            Some(text) => Ok(Some(
                Step::parse(text).ok_or_else(|| Self::wrong("step", "not a known step"))?,
            )),
            None => Ok(None),
        }
    }

    fn rounds(&self) -> Result<Rounds, FollowLineRejected> {
        let rounds = self
            .fields
            .get("rounds")
            .ok_or_else(|| Self::wrong("rounds", "required key is missing"))?
            .as_object()
            .ok_or_else(|| Self::wrong("rounds", "expected an object"))?;
        let [controls, hygiene, judge, ci, ci_indeterminate, catch_up] = Self::ROUND_KEYS;

        Ok(Rounds::new(
            Self::round(rounds, controls)?,
            Self::round(rounds, hygiene)?,
            Self::round(rounds, judge)?,
            Self::round(rounds, ci)?,
            Self::round(rounds, ci_indeterminate)?,
            Self::round(rounds, catch_up)?,
        ))
    }

    fn round(rounds: &Map<String, Value>, key: &str) -> Result<Round, FollowLineRejected> {
        let round = rounds
            .get(key)
            .and_then(Value::as_object)
            .ok_or_else(|| Self::wrong(key, "expected an object with used and limit"))?;
        let number = |field: &str| {
            round
                .get(field)
                .and_then(Value::as_u64)
                .ok_or_else(|| Self::wrong(key, "expected whole numbers in used and limit"))
        };

        Ok(Round::new(number("used")?, number("limit")?))
    }

    fn parent(&self) -> Result<Parent, FollowLineRejected> {
        Ok(match self.optional_number("parent")? {
            Some(issue) => Parent::Issue(issue),
            None => Parent::Absent,
        })
    }

    fn required_text(&self, key: &str) -> Result<&'a str, FollowLineRejected> {
        self.optional_text(key)?
            .ok_or_else(|| Self::wrong(key, "required key is missing"))
    }

    fn optional_text(&self, key: &str) -> Result<Option<&'a str>, FollowLineRejected> {
        match self.fields.get(key) {
            None => Ok(None),
            Some(value) => value
                .as_str()
                .map(Some)
                .ok_or_else(|| Self::wrong(key, "expected a string")),
        }
    }

    fn required_number(&self, key: &str) -> Result<u64, FollowLineRejected> {
        self.optional_number(key)?
            .ok_or_else(|| Self::wrong(key, "required key is missing"))
    }

    fn optional_number(&self, key: &str) -> Result<Option<u64>, FollowLineRejected> {
        match self.fields.get(key) {
            None => Ok(None),
            Some(value) => value
                .as_u64()
                .map(Some)
                .ok_or_else(|| Self::wrong(key, "expected a whole number")),
        }
    }

    fn required_float(&self, key: &str) -> Result<f64, FollowLineRejected> {
        self.fields
            .get(key)
            .ok_or_else(|| Self::wrong(key, "required key is missing"))?
            .as_f64()
            .ok_or_else(|| Self::wrong(key, "expected a number"))
    }

    fn optional_flag(&self, key: &str) -> Result<bool, FollowLineRejected> {
        match self.fields.get(key) {
            None => Ok(false),
            Some(value) => value
                .as_bool()
                .ok_or_else(|| Self::wrong(key, "expected true or false")),
        }
    }

    fn wrong(key: &str, reason: &str) -> FollowLineRejected {
        FollowLineRejected::WrongValue {
            key: key.to_string(),
            reason: reason.to_string(),
        }
    }
}
