mod the_issue_body_payload {
    use crate::domain::errors::IssuesUnread;
    use crate::domain::issue_text::IssueText;
    use crate::infrastructure::issue_body_payload::IssueBodyPayload;

    #[test]
    fn gives_the_body_and_the_title_of_the_literal_answer_of_gh() {
        assert_eq!(
            IssueBodyPayload::parsed(r#"{"body":"uno\n\n<!-- m -->","title":"Las slices"}"#),
            Ok(IssueText::new("uno\n\n<!-- m -->", "Las slices"))
        );
    }

    #[test]
    fn text_that_is_not_json_is_not_json() {
        assert!(matches!(
            IssueBodyPayload::parsed("nope"),
            Err(IssuesUnread::NotJson { .. })
        ));
    }

    #[test]
    fn a_body_that_is_not_a_string_is_a_wrong_value() {
        assert!(matches!(
            IssueBodyPayload::parsed(r#"{"body":3,"title":"y"}"#),
            Err(IssuesUnread::WrongValue { key, .. }) if key == "body"
        ));
    }

    #[test]
    fn a_title_that_is_not_a_string_is_a_wrong_value() {
        assert!(matches!(
            IssueBodyPayload::parsed(r#"{"body":"x","title":3}"#),
            Err(IssuesUnread::WrongValue { key, .. }) if key == "title"
        ));
    }

    #[test]
    fn a_missing_title_is_a_wrong_value() {
        assert!(matches!(
            IssueBodyPayload::parsed(r#"{"body":"x"}"#),
            Err(IssuesUnread::WrongValue { key, .. }) if key == "title"
        ));
    }

    #[test]
    fn a_key_that_was_not_asked_for_is_a_wrong_value() {
        assert!(matches!(
            IssueBodyPayload::parsed(r#"{"body":"x","title":"y","labels":[]}"#),
            Err(IssuesUnread::WrongValue { key, .. }) if key == "labels"
        ));
    }
}
