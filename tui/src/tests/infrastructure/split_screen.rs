mod the_split_screen {
    use ratatui::layout::Rect;

    use crate::domain::pane_size::PaneSize;
    use crate::infrastructure::split_screen::SplitScreen;

    #[test]
    fn gives_the_left_half_to_claude_and_the_right_half_to_the_board() {
        let (claude, board) = SplitScreen::areas(Rect::new(0, 0, 100, 30));

        assert_eq!(claude, Rect::new(0, 0, 50, 30));
        assert_eq!(board, Rect::new(50, 0, 50, 30));
    }

    #[test]
    fn the_pane_size_is_the_left_area_without_its_border() {
        assert_eq!(SplitScreen::pane_size(Rect::new(0, 0, 100, 30)), PaneSize::new(28, 48));
    }

    #[test]
    fn a_tiny_window_gives_a_pane_of_zero_and_never_underflows() {
        assert_eq!(SplitScreen::pane_size(Rect::new(0, 0, 1, 1)), PaneSize::new(0, 0));
    }
}

mod the_pty_the_split_gives_to_claude {
    use ratatui::layout::Rect;

    use crate::domain::pane_size::PaneSize;
    use crate::infrastructure::endless_pty_session::EndlessPtySession;
    use crate::infrastructure::split_screen::SplitScreen;
    use crate::tests::doubles::{PtyCall, ScriptedPtyLauncher, SteppedClock};
    use crate::tests::infrastructure::endless_pty_session::Launches;

    #[test]
    fn opens_with_the_rows_and_columns_of_the_left_pane_and_gets_the_new_ones_after_a_resize() {
        let (launcher, probe) = ScriptedPtyLauncher::printing("");
        let mut session = EndlessPtySession::spawn(
            &launcher,
            &Launches::claude(),
            SplitScreen::pane_size(Rect::new(0, 0, 100, 30)),
            SteppedClock::standing_still(),
        )
        .unwrap();

        session.resize(SplitScreen::pane_size(Rect::new(0, 0, 80, 20)));

        let sizes: Vec<PaneSize> = probe
            .calls()
            .into_iter()
            .map(|call| match call {
                PtyCall::Launched { size, .. } | PtyCall::Resized(size) => size,
            })
            .collect();
        assert_eq!(sizes, [PaneSize::new(28, 48), PaneSize::new(18, 38)]);
    }
}
