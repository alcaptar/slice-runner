use ratatui::Frame;
use ratatui::layout::Rect;
use ratatui::style::{Color, Style};
use ratatui::text::Line;
use ratatui::widgets::Paragraph;

use crate::application::queries::bind_workspace::WorkspaceState;
use crate::domain::workspace_binding::WorkspaceBinding;
use crate::domain::workspace_repo::WorkspaceRepo;

pub struct WorkspaceHeader;

impl WorkspaceHeader {
    pub const HEIGHT: u16 = 3;

    pub fn render(frame: &mut Frame, area: Rect, state: &WorkspaceState) {
        let repo = match state.repo() {
            WorkspaceRepo::Known(repo) => repo.as_str().to_string(),
            WorkspaceRepo::Unknown => "repo unknown".to_string(),
        };
        let feature = match state.binding() {
            WorkspaceBinding::Unbound => "this workspace has no feature yet".to_string(),
            WorkspaceBinding::Bound(parent) => format!("feature #{parent}"),
        };
        let warning = state
            .warning()
            .map(|warning| Line::styled(warning.to_string(), Style::new().fg(Color::Red)))
            .unwrap_or_default();

        frame.render_widget(
            Paragraph::new(vec![
                Line::from(format!("{repo} · {feature}")),
                Line::styled(
                    format!("workspace {}", state.id().as_str()),
                    Style::new().fg(Color::DarkGray),
                ),
                warning,
            ]),
            area,
        );
    }
}
