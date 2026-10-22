use crate::domain::errors::FollowLineRejected;
use crate::domain::follow_entry::FollowEntry;
use crate::domain::follow_line::FollowLine;
use crate::domain::transition::Transition;
use crate::infrastructure::follow_line_payload::FollowLinePayload;

pub struct RawTransition;

impl RawTransition {
    pub const ROUNDS: &'static str = r#""rounds":{"controls":{"used":1,"limit":2},"hygiene":{"used":0,"limit":2},"judge":{"used":0,"limit":2},"ci":{"used":0,"limit":1},"ci_indeterminate":{"used":0,"limit":10},"catch_up":{"used":0,"limit":3}}"#;

    pub fn with(standing_and_more: &str) -> String {
        format!(
            r#"{{"version":2,"kind":"transition","ts":1767268800000,"repo":"alcaptar/demo-workspace","issue":150,"slice_id":"slice-05","cost_usd":4.5,"budget_usd":50.0,{},{standing_and_more}}}"#,
            Self::ROUNDS
        )
    }

    pub fn blocked_by_controls() -> String {
        Self::with(r#""standing":"blocked","reason":"controls","step":"run-controls","pid":48213"#)
    }

    pub fn activity() -> String {
        r#"{"version":2,"kind":"activity","ts":1767268920000,"repo":"alcaptar/demo-workspace","issue":150,"slice_id":"slice-05","actor":"judge","tool":"Read","target":"src/x.py"}"#.to_string()
    }

    pub fn rejected_key(raw: &str) -> String {
        let rejected = FollowLinePayload::delivery(raw).unwrap_err();
        let FollowLineRejected::WrongValue { key, .. } = rejected else {
            panic!("expected a wrong value, got {rejected:?}");
        };
        key
    }

    pub fn transition_of(raw: &str) -> (FollowLine, Transition) {
        match FollowLinePayload::delivery(raw).unwrap() {
            FollowEntry::Transition(line) => {
                let transition = line.clone().into_parts().1;
                (line, transition)
            }
            FollowEntry::Activity(activity) => panic!("expected a transition, got {activity:?}"),
        }
    }
}

mod a_version_2_transition {
    use crate::domain::closing_reason::ClosingReason;
    use crate::domain::closure::Closure;
    use crate::domain::rounds::Counter;
    use crate::domain::step::Step;
    use crate::tests::infrastructure::follow_line_payload::RawTransition;

    #[test]
    fn carries_its_moment_closure_step_rounds_spend_and_process() {
        let (line, transition) = RawTransition::transition_of(&RawTransition::blocked_by_controls());

        assert_eq!(line.issue(), 150);
        assert_eq!(transition.at(), 1_767_268_800_000);
        assert_eq!(transition.closure(), Closure::Blocked(ClosingReason::Controls));
        assert_eq!(transition.step(), Some(Step::RunControls));
        assert_eq!(transition.rounds().of(Counter::Controls).used(), 1);
        assert_eq!(transition.rounds().of(Counter::CiIndeterminate).limit(), 10);
        assert!((transition.spend().cost_usd() - 4.5).abs() < f64::EPSILON);
        assert_eq!(transition.pid(), Some(48213));
        assert_eq!(transition.pull_request(), None);
        assert!(!transition.round_without_changes());
    }

    #[test]
    fn carries_its_pull_request_and_a_round_without_changes() {
        let (_, transition) = RawTransition::transition_of(&RawTransition::with(
            r#""standing":"in-progress","step":"implement","pull_request":151,"round_without_changes":true"#,
        ));

        assert_eq!(transition.pull_request(), Some(151));
        assert!(transition.round_without_changes());
    }

    #[test]
    fn carries_the_path_of_its_comparison_and_leaves_it_absent_when_the_key_is_missing() {
        let (_, with) = RawTransition::transition_of(&RawTransition::with(
            r#""standing":"awaiting-merge","step":"await-merge","comparison":"/work/.design-captures/comparison.html""#,
        ));
        let (_, without) = RawTransition::transition_of(&RawTransition::with(r#""standing":"pending""#));

        assert_eq!(with.comparison(), Some("/work/.design-captures/comparison.html"));
        assert_eq!(without.comparison(), None);
    }

    #[test]
    fn a_pending_one_has_no_step() {
        let (_, transition) = RawTransition::transition_of(&RawTransition::with(r#""standing":"pending""#));

        assert_eq!(transition.closure(), Closure::Pending);
        assert_eq!(transition.step(), None);
    }
}

mod a_version_2_activity {
    use crate::domain::activity_line::Actor;
    use crate::domain::follow_entry::FollowEntry;
    use crate::domain::slice_key::SliceKey;
    use crate::infrastructure::follow_line_payload::FollowLinePayload;
    use crate::tests::infrastructure::follow_line_payload::RawTransition;
    use crate::tests::mothers::follow_line_mother::FollowLineMother;

    #[test]
    fn carries_who_does_what_on_which_slice() {
        let FollowEntry::Activity(activity) = FollowLinePayload::delivery(&RawTransition::activity()).unwrap() else {
            panic!("expected an activity line");
        };

        assert_eq!(activity.key(), &SliceKey::new(FollowLineMother::REPO, 150));
        assert_eq!(activity.actor(), Actor::Judge);
        assert_eq!(activity.tool(), "Read");
        assert_eq!(activity.target(), "src/x.py");
    }
}

mod a_line_the_interface_rejects {
    use crate::domain::errors::FollowLineRejected;
    use crate::infrastructure::follow_line_payload::FollowLinePayload;
    use crate::tests::infrastructure::follow_line_payload::RawTransition;

    #[test]
    fn names_the_reason_of_a_blocked_one_without_reason() {
        assert_eq!(
            RawTransition::rejected_key(&RawTransition::with(r#""standing":"blocked","step":"verify""#)),
            "reason"
        );
    }

    #[test]
    fn names_an_unknown_standing() {
        assert_eq!(
            RawTransition::rejected_key(&RawTransition::with(r#""standing":"sleeping""#)),
            "standing"
        );
    }

    #[test]
    fn names_a_round_without_used_and_limit() {
        let raw = RawTransition::with(r#""standing":"pending""#)
            .replace(r#""ci":{"used":0,"limit":1}"#, r#""ci":{"used":0}"#);

        assert_eq!(RawTransition::rejected_key(&raw), "ci");
    }

    #[test]
    fn names_a_known_optional_key_with_the_wrong_type() {
        assert_eq!(
            RawTransition::rejected_key(&RawTransition::with(r#""standing":"pending","parent":"140""#)),
            "parent"
        );
    }

    #[test]
    fn rejects_a_version_1_line_naming_its_version() {
        let raw = r#"{"version":1,"repo":"alcaptar/demo-workspace","issue":150,"slice_id":"slice-05","step":"run-controls","status":"advancing"}"#;

        assert_eq!(
            FollowLinePayload::delivery(raw).unwrap_err(),
            FollowLineRejected::UnsupportedVersion { version: 1 }
        );
    }

    #[test]
    fn rejects_an_unknown_kind_naming_it() {
        assert_eq!(
            FollowLinePayload::delivery(r#"{"version":2,"kind":"heartbeat"}"#).unwrap_err(),
            FollowLineRejected::UnknownKind {
                kind: "heartbeat".to_string()
            }
        );
    }

    #[test]
    fn rejects_a_line_that_is_not_a_json_object_with_the_text_it_carried() {
        assert_eq!(
            FollowLinePayload::delivery("Traceback (most recent call last)").unwrap_err(),
            FollowLineRejected::NotJson {
                line: "Traceback (most recent call last)".to_string()
            }
        );
    }
}
