mod the_open_issues_payload {
    use crate::domain::errors::IssuesUnread;
    use crate::domain::open_issue::OpenIssue;
    use crate::infrastructure::open_issues_payload::OpenIssuesPayload;

    #[test]
    fn turns_the_literal_answer_of_gh_into_issues_in_the_same_order() {
        let raw = r#"[{"body":"uno\n\n<!-- m -->","number":9,"title":"Nueve"},{"body":"","number":7,"title":""}]"#;

        assert_eq!(
            OpenIssuesPayload::parsed(raw),
            Ok(vec![
                OpenIssue::new(9, "uno\n\n<!-- m -->", "Nueve"),
                OpenIssue::new(7, "", "")
            ])
        );
    }

    #[test]
    fn an_empty_list_is_no_issues() {
        assert_eq!(OpenIssuesPayload::parsed("[]"), Ok(vec![]));
    }

    #[test]
    fn text_that_is_not_json_is_not_json() {
        assert!(matches!(
            OpenIssuesPayload::parsed("gh: not logged in"),
            Err(IssuesUnread::NotJson { .. })
        ));
    }

    #[test]
    fn json_that_is_not_a_list_is_not_json_of_the_contract() {
        assert!(matches!(
            OpenIssuesPayload::parsed(r#"{"number":9}"#),
            Err(IssuesUnread::NotJson { .. })
        ));
    }

    #[test]
    fn a_number_that_is_not_a_whole_number_is_a_wrong_value() {
        let raw = r#"[{"body":"x","number":"nine","title":"y"}]"#;

        assert!(matches!(
            OpenIssuesPayload::parsed(raw),
            Err(IssuesUnread::WrongValue { key, .. }) if key == "number"
        ));
    }

    #[test]
    fn a_missing_body_is_a_wrong_value() {
        assert!(matches!(
            OpenIssuesPayload::parsed(r#"[{"number":9,"title":"y"}]"#),
            Err(IssuesUnread::WrongValue { key, .. }) if key == "body"
        ));
    }

    #[test]
    fn a_missing_title_is_a_wrong_value() {
        assert!(matches!(
            OpenIssuesPayload::parsed(r#"[{"number":9,"body":"x"}]"#),
            Err(IssuesUnread::WrongValue { key, .. }) if key == "title"
        ));
    }

    #[test]
    fn a_title_that_is_not_a_string_is_a_wrong_value() {
        assert!(matches!(
            OpenIssuesPayload::parsed(r#"[{"number":9,"body":"x","title":3}]"#),
            Err(IssuesUnread::WrongValue { key, .. }) if key == "title"
        ));
    }

    #[test]
    fn a_key_that_was_not_asked_for_is_a_wrong_value() {
        let raw = r#"[{"body":"x","number":9,"title":"y","labels":[]}]"#;

        assert!(matches!(
            OpenIssuesPayload::parsed(raw),
            Err(IssuesUnread::WrongValue { key, .. }) if key == "labels"
        ));
    }
}

mod the_repo_view_payload {
    use crate::domain::errors::IssuesUnread;
    use crate::infrastructure::repo_view_payload::RepoViewPayload;

    #[test]
    fn gives_the_name_with_owner_of_the_literal_answer_of_gh() {
        assert_eq!(
            RepoViewPayload::parsed(r#"{"nameWithOwner":"alcaptar/demo-workspace"}"#),
            Ok("alcaptar/demo-workspace".to_string())
        );
    }

    #[test]
    fn text_that_is_not_json_is_not_json() {
        assert!(matches!(
            RepoViewPayload::parsed("nope"),
            Err(IssuesUnread::NotJson { .. })
        ));
    }

    #[test]
    fn a_name_that_is_not_a_string_is_a_wrong_value() {
        assert!(matches!(
            RepoViewPayload::parsed(r#"{"nameWithOwner":3}"#),
            Err(IssuesUnread::WrongValue { key, .. }) if key == "nameWithOwner"
        ));
    }

    #[test]
    fn a_key_that_was_not_asked_for_is_a_wrong_value() {
        assert!(matches!(
            RepoViewPayload::parsed(r#"{"nameWithOwner":"a/b","url":"x"}"#),
            Err(IssuesUnread::WrongValue { key, .. }) if key == "url"
        ));
    }
}
