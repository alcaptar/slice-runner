use ratatui::Frame;
use ratatui::layout::Rect;
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, Paragraph};

use crate::application::queries::read_slice_detail::SliceDetail;
use crate::domain::activity_line::Actor;
use crate::domain::closure::Closure;
use crate::domain::elapsed::Elapsed;
use crate::domain::rounds::Counter;
use crate::domain::slice_row::SliceRow;
use crate::domain::step::Step;
use crate::infrastructure::focus_border::FocusBorder;
use crate::infrastructure::narration::Narration;
use crate::infrastructure::slice_glyph::SliceGlyph;

pub struct DetailView;

impl DetailView {
    const KEYS: &'static str = " esc volver · ctrl+q claude";
    const COMPARISON_KEYS: &'static str = " v comparación · esc volver · ctrl+q claude";
    const OPENING_FAILED: &'static str = " no se pudo abrir la comparación";
    const SHOWN_ACTIVITY: usize = 5;
    const KEPT_HISTORY: usize = 3;
    const PHASES: [(Step, &'static str); 7] = [
        (Step::MountWorktree, "mnt"),
        (Step::Implement, "imp"),
        (Step::RunControls, "ctl"),
        (Step::Verify, "ver"),
        (Step::OpenPullRequest, "pr"),
        (Step::AwaitCi, "ci"),
        (Step::AwaitMerge, "mrg"),
    ];
    const FIRST_COUNTERS: [Counter; 3] = [Counter::Controls, Counter::Hygiene, Counter::Judge];
    const LAST_COUNTERS: [Counter; 3] = [Counter::Ci, Counter::CiIndeterminate, Counter::CatchUp];

    pub fn render(frame: &mut Frame, area: Rect, row: &SliceRow, detail: &SliceDetail, now: u64, focused: bool) {
        let block = Block::bordered()
            .title(format!(" {} {} ", row.subject().number(), row.label()))
            .border_style(FocusBorder::style(focused));
        let inner = block.inner(area);
        let width = usize::from(inner.width);
        let room = usize::from(inner.height.saturating_sub(1));
        let bottom = Self::bottom_of(row, detail, width);
        let told = row.transitions().len();
        let head = Self::head_of(row, now);
        let space = room.saturating_sub(head.len() + bottom.len() + 1);
        let activity = Self::activity_fitting(row, now, space, told);
        let space = space.saturating_sub(activity.len());
        let skipped = told.saturating_sub(space);
        let mut lines = head;
        lines.extend(activity);
        lines.push(Line::from(" HISTORIA"));
        lines.extend(Self::history_of(row, now, width, skipped));
        lines.extend(bottom);
        frame.render_widget(Paragraph::new(lines).block(block), area);
        if inner.height > 0 {
            let keys_row = Rect::new(inner.x, inner.y + inner.height - 1, inner.width, 1);
            let keys = if row.comparison().is_some() {
                Self::COMPARISON_KEYS
            } else {
                Self::KEYS
            };
            frame.render_widget(Paragraph::new(keys), keys_row);
        }
    }

    fn head_of(row: &SliceRow, now: u64) -> Vec<Line<'static>> {
        vec![
            Self::headline_of(row, now),
            Self::times_of(row, now),
            Line::default(),
            Line::from(Self::phases_of(row)),
            Line::from(Self::counters_of(row, &Self::FIRST_COUNTERS)),
            Line::from(Self::counters_of(row, &Self::LAST_COUNTERS)),
            Line::default(),
        ]
    }

    fn activity_fitting(row: &SliceRow, now: u64, space: usize, history: usize) -> Vec<Line<'static>> {
        if !row.is_running() || row.activity().is_empty() {
            return Vec::new();
        }
        let framing = 2;
        let shown = Self::SHOWN_ACTIVITY.min(space.saturating_sub(framing + history.min(Self::KEPT_HISTORY)));
        if shown == 0 {
            return Vec::new();
        }
        let mut lines = Self::activity_of(row, now, shown);
        lines.push(Line::default());

        lines
    }

    fn headline_of(row: &SliceRow, now: u64) -> Line<'static> {
        let latest = row.latest();
        let closure = latest.closure();
        let mut spans = vec![
            Span::raw(" "),
            SliceGlyph::of(row, now),
            Span::raw(" "),
            Span::raw(closure.label()),
        ];
        if row.process_is_gone() {
            spans.push(Span::raw(" · "));
            spans.push(Span::styled("proceso muerto", SliceGlyph::alarm()));
        }
        if let (Some(step), false) = (latest.step(), closure == Closure::Merged) {
            spans.push(Span::raw(format!(" · {}", step.name())));
        }

        Line::from(spans)
    }

    fn times_of(row: &SliceRow, now: u64) -> Line<'static> {
        let latest = row.latest();
        let transitions = row.transitions();
        let mut parts = vec![Span::raw(format!(" hace {}", Elapsed::between(latest.at(), now)))];
        if let (Some(first), true) = (transitions.first(), transitions.len() > 1) {
            let end = if latest.closure().is_settled() {
                latest.at()
            } else {
                now
            };
            parts.push(Span::raw(format!(" · {} en total", Elapsed::between(first.at(), end))));
        }
        let spend = latest.spend();
        let amount = format!(" · ${:.2} de ${:.0}", spend.cost_usd(), spend.budget_usd());
        parts.push(if spend.nears_the_budget() {
            Span::styled(amount, SliceGlyph::warning())
        } else {
            Span::raw(amount)
        });
        if let Some(number) = row.pull_request() {
            parts.push(Span::raw(format!(" · pull request #{number}")));
        }

        Line::from(parts)
    }

    fn phases_of(row: &SliceRow) -> String {
        let latest = row.latest();
        let shown_step = latest.step().map(|step| match step {
            Step::CatchUp => Step::AwaitCi,
            Step::MountWorktree
            | Step::Understand
            | Step::Implement
            | Step::RunControls
            | Step::Verify
            | Step::OpenPullRequest
            | Step::AwaitCi
            | Step::AwaitMerge => step,
        });
        let current = Self::PHASES.iter().position(|(step, _)| shown_step == Some(*step));
        let phases: Vec<String> = Self::PHASES
            .iter()
            .enumerate()
            .map(|(index, (step, abbreviation))| {
                let visits = row
                    .transitions()
                    .iter()
                    .filter(|transition| {
                        transition.step() == Some(*step) && transition.closure() == Closure::InProgress
                    })
                    .count();
                let mark = if current == Some(index) {
                    Self::current_mark(latest.closure())
                } else if visits > 0 || current.is_some_and(|current| index < current) {
                    "■"
                } else {
                    "·"
                };
                format!("{abbreviation} {mark}{}", Self::superscript(visits))
            })
            .collect();

        format!(" {}", phases.join("  "))
    }

    fn current_mark(closure: Closure) -> &'static str {
        match closure {
            Closure::InProgress => "▶",
            Closure::AwaitingMerge => "◆",
            Closure::Blocked(_) | Closure::Aborted(_) => "✕",
            Closure::Merged => "✓",
            Closure::Pending => "·",
        }
    }

    fn superscript(visits: usize) -> &'static str {
        match visits {
            0 | 1 => "",
            2 => "²",
            3 => "³",
            4 => "⁴",
            5 => "⁵",
            6 => "⁶",
            7 => "⁷",
            8 => "⁸",
            9 => "⁹",
            _ => "⁺",
        }
    }

    fn counters_of(row: &SliceRow, counters: &[Counter]) -> String {
        let rounds = row.latest().rounds();
        let shown: Vec<String> = counters
            .iter()
            .map(|counter| {
                let round = rounds.of(*counter);
                format!("{} {}/{}", counter.label(), round.used(), round.limit())
            })
            .collect();

        format!(" {}", shown.join(" · "))
    }

    fn activity_of(row: &SliceRow, now: u64, shown: usize) -> Vec<Line<'static>> {
        let activity = row.activity();
        let Some(last) = activity.last() else {
            return Vec::new();
        };
        let heading = match last.actor() {
            Actor::Implementer => " QUÉ HACE EL IMPLEMENTADOR AHORA",
            Actor::Judge => " QUÉ HACE EL JUEZ AHORA",
            Actor::Controls => " QUÉ HACEN LOS CONTROLES AHORA",
        };
        let start = activity.len().saturating_sub(shown);
        let ages: Vec<String> = activity[start..]
            .iter()
            .map(|line| Elapsed::between(line.at(), now).to_string())
            .collect();
        let age_width = ages.iter().map(|age| age.chars().count()).max().unwrap_or(0);
        let mut lines = vec![Line::from(heading)];
        lines.extend(
            activity[start..].iter().zip(ages).map(|(line, age)| {
                Line::from(format!(" hace {age:<age_width$}  {:<5} {}", line.tool(), line.target()))
            }),
        );

        lines
    }

    fn history_of(row: &SliceRow, now: u64, width: usize, skipped: usize) -> Vec<Line<'static>> {
        let transitions = row.transitions();
        let running = row.is_running() && !row.process_is_gone();
        let shown: Vec<usize> = (skipped..transitions.len()).collect();
        let ages: Vec<String> = shown
            .iter()
            .map(|index| Elapsed::between(transitions[*index].at(), now).to_string())
            .collect();
        let durations: Vec<Option<String>> = shown
            .iter()
            .map(|index| {
                transitions
                    .get(index + 1)
                    .map(|later| Elapsed::between(transitions[*index].at(), later.at()).to_string())
            })
            .collect();
        let age_width = ages.iter().map(|age| age.chars().count()).max().unwrap_or(0);
        let duration_width = durations
            .iter()
            .flatten()
            .map(|duration| duration.chars().count())
            .max()
            .unwrap_or(0);
        let lead = " hace ".chars().count() + age_width + 2;
        let sentence_width = width.saturating_sub(lead + duration_width + 2);

        shown
            .iter()
            .zip(ages.iter().zip(durations.iter()))
            .map(|(index, (age, duration))| {
                let transition = transitions[*index];
                let earlier = index.checked_sub(1).and_then(|before| transitions.get(before)).copied();
                let mut sentence = Narration::of(transition, earlier);
                if duration.is_none() && running {
                    sentence = format!("{} {sentence}", SliceGlyph::spinner(now));
                }
                match duration {
                    Some(duration) => Line::from(format!(
                        " hace {age:<age_width$}  {:<sentence_width$} {duration:>duration_width$}",
                        Self::fitted(&sentence, sentence_width)
                    )),
                    None => Line::from(format!(
                        " hace {age:<age_width$}  {}",
                        Self::fitted(&sentence, width.saturating_sub(lead))
                    )),
                }
            })
            .collect()
    }

    fn fitted(text: &str, width: usize) -> String {
        if text.chars().count() <= width {
            return text.to_string();
        }
        if width == 0 {
            return String::new();
        }
        let kept: String = text.chars().take(width.saturating_sub(1)).collect();

        format!("{kept}…")
    }

    fn bottom_of(row: &SliceRow, detail: &SliceDetail, width: usize) -> Vec<Line<'static>> {
        let mut lines = Self::reopening_of(row, width);
        if detail.opening_failed() {
            lines.push(Line::from(Span::styled(Self::OPENING_FAILED, SliceGlyph::alarm())));
        }

        lines
    }

    fn reopening_of(row: &SliceRow, width: usize) -> Vec<Line<'static>> {
        match row.latest().closure() {
            Closure::Blocked(_) | Closure::Aborted(_) => {
                let command = format!(" slice-runner retry {} --repo {}", row.subject().issue(), row.repo());
                let instruction = " \"<instrucción>\"";
                let mut lines = vec![Line::default(), Line::from(" Para reabrirla:")];
                if command.chars().count() + instruction.chars().count() <= width {
                    lines.push(Line::from(format!("{command}{instruction}")));
                } else {
                    lines.push(Line::from(command));
                    lines.push(Line::from(format!("  {instruction}")));
                }
                lines
            }
            Closure::Pending | Closure::InProgress | Closure::AwaitingMerge | Closure::Merged => Vec::new(),
        }
    }
}
