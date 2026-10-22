use std::path::PathBuf;

use serde_json::Value;

pub struct LineContract {
    pub examples: Vec<serde_json::Map<String, Value>>,
}

impl LineContract {
    pub fn on_disk(file: &str) -> Self {
        let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("..")
            .join("contract")
            .join(file);
        let document: Value = serde_json::from_str(&std::fs::read_to_string(path).unwrap()).unwrap();
        let examples = document["examples"]
            .as_array()
            .unwrap()
            .iter()
            .map(|example| example.as_object().unwrap().clone())
            .collect();

        Self { examples }
    }

    pub fn raw(example: &serde_json::Map<String, Value>) -> String {
        Value::Object(example.clone()).to_string()
    }
}

pub struct MarkerContract {
    pub template: String,
    pub examples: Vec<String>,
}

impl MarkerContract {
    pub fn on_disk() -> Self {
        let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("..")
            .join("contract")
            .join("workspace-marker.json");
        let document: Value = serde_json::from_str(&std::fs::read_to_string(path).unwrap()).unwrap();
        let examples = document["examples"]
            .as_array()
            .unwrap()
            .iter()
            .map(|example| example.as_str().unwrap().to_string())
            .collect();

        Self {
            template: document["marker"].as_str().unwrap().to_string(),
            examples,
        }
    }

    pub fn workspace_of(&self, example: &str) -> crate::domain::workspace_id::WorkspaceId {
        let (opening, closing) = self.template.split_once("<uuid>").unwrap();
        let uuid = example.strip_prefix(opening).unwrap().strip_suffix(closing).unwrap();

        crate::domain::workspace_id::WorkspaceId::parse(uuid).unwrap()
    }
}

mod the_follow_line_version_2_contract {
    use crate::domain::follow_entry::FollowEntry;
    use crate::infrastructure::follow_line_payload::FollowLinePayload;
    use crate::tests::infrastructure::contract::LineContract;

    #[test]
    fn every_example_is_delivered_as_its_own_kind() {
        let contract = LineContract::on_disk("follow-line-v2.json");

        assert!(!contract.examples.is_empty());
        for example in &contract.examples {
            let delivery = FollowLinePayload::delivery(&LineContract::raw(example));
            match (example["kind"].as_str().unwrap(), &delivery) {
                ("transition", Ok(FollowEntry::Transition(_))) | ("activity", Ok(FollowEntry::Activity(_))) => {}
                (kind, other) => panic!("an example of kind {kind} was delivered as {other:?}"),
            }
        }
    }

    #[test]
    fn the_blocked_and_aborted_examples_carry_the_label_of_github() {
        let contract = LineContract::on_disk("follow-line-v2.json");

        let labels: Vec<String> = contract
            .examples
            .iter()
            .filter(|example| example["kind"] == "transition")
            .filter(|example| example["standing"] == "blocked" || example["standing"] == "aborted")
            .map(
                |example| match FollowLinePayload::delivery(&LineContract::raw(example)).unwrap() {
                    FollowEntry::Transition(line) => line.into_parts().1.closure().label(),
                    FollowEntry::Activity(activity) => panic!("{activity:?}"),
                },
            )
            .collect();

        assert_eq!(
            labels,
            vec![
                "bloqueada: controles",
                "bloqueada: juez",
                "bloqueada: ci roja",
                "bloqueada: ci indeterminada",
                "bloqueada: conflicto",
                "bloqueada: worktree",
                "abortada: presupuesto",
                "abortada: llamada no medida",
            ]
        );
    }
}
