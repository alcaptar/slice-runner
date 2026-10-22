mod the_random_workspace_ids {
    use crate::domain::workspace_id::WorkspaceId;
    use crate::domain::workspace_ids::WorkspaceIds;
    use crate::infrastructure::random_workspace_ids::RandomWorkspaceIds;

    #[test]
    fn two_calls_give_two_different_values_shaped_like_a_uuid() {
        let mut ids = RandomWorkspaceIds;

        let first = ids.next();
        let second = ids.next();

        assert_ne!(first, second);
        assert!(WorkspaceId::parse(first.as_str()).is_ok());
        assert!(WorkspaceId::parse(second.as_str()).is_ok());
        assert_eq!(first.as_str().len(), 36);
    }
}
