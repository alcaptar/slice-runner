use ratatui::Frame;
use ratatui::layout::Rect;
use ratatui::style::{Color, Style};
use ratatui::text::Line;
use ratatui::widgets::Paragraph;

use crate::domain::update_availability::UpdateAvailability;

pub struct UpdateNoticeView;

impl UpdateNoticeView {
    const COMMAND: &'static str = "slice-runner update";

    pub fn height_of(availability: &UpdateAvailability) -> u16 {
        match availability {
            UpdateAvailability::Absent => 0,
            UpdateAvailability::Newer(_)
            | UpdateAvailability::Updating(_)
            | UpdateAvailability::Installed(_)
            | UpdateAvailability::Failed { .. } => 1,
        }
    }

    fn line_of(availability: &UpdateAvailability) -> Option<(String, Color)> {
        match availability {
            UpdateAvailability::Absent => None,
            UpdateAvailability::Newer(version) => Some((
                format!(" version {version} disponible · {}", Self::COMMAND),
                Color::Yellow,
            )),
            UpdateAvailability::Updating(version) => Some((format!(" actualizando a {version}..."), Color::Yellow)),
            UpdateAvailability::Installed(version) => {
                Some((format!(" {version} instalada · reabre para usarla"), Color::Green))
            }
            UpdateAvailability::Failed { version, reason } => Some((
                format!(" no se pudo actualizar a {version}: {reason} · {}", Self::COMMAND),
                Color::Red,
            )),
        }
    }

    pub fn render(frame: &mut Frame, area: Rect, availability: &UpdateAvailability) {
        if let Some((text, color)) = Self::line_of(availability) {
            frame.render_widget(Paragraph::new(Line::styled(text, Style::new().fg(color))), area);
        }
    }
}
