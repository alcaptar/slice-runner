use crate::domain::closing_reason::ClosingReason;
use crate::domain::closure::Closure;
use crate::domain::rounds::Counter;
use crate::domain::step::Step;
use crate::domain::transition::Transition;

pub struct Narration;

impl Narration {
    pub fn of(transition: &Transition, earlier: Option<&Transition>) -> String {
        let sentence = match transition.closure() {
            Closure::Pending => "registrada".to_string(),
            Closure::Merged => "✓ mergeada".to_string(),
            Closure::AwaitingMerge => "espera el merge".to_string(),
            Closure::Blocked(reason) => Self::blocked(transition, reason),
            Closure::Aborted(reason) => format!("⊘ abortada: {}", reason.label()),
            Closure::InProgress => Self::working(transition, earlier),
        };
        if transition.round_without_changes() {
            return format!("{sentence}, sin cambios");
        }

        sentence
    }

    fn blocked(transition: &Transition, reason: ClosingReason) -> String {
        let spent = reason
            .spends()
            .is_some_and(|counter| transition.rounds().of(counter).is_spent());
        let tail = if spent { ", sin vueltas que queden" } else { "" };

        format!("✕ bloqueada: {}{tail}", reason.label())
    }

    fn working(transition: &Transition, earlier: Option<&Transition>) -> String {
        let round = transition.rounds().implementation_round();
        let Some(step) = transition.step() else {
            return "en curso".to_string();
        };
        match step {
            Step::Implement => {
                let cause = earlier
                    .and_then(|earlier| transition.rounds().grown_since(earlier.rounds()))
                    .filter(|counter| counter.sends_the_work_back())
                    .map_or("", Self::cause_of);
                format!("{cause}implementa, vuelta {round}")
            }
            Step::RunControls => format!("corre los controles, vuelta {round}"),
            Step::Verify => format!("el juez revisa, vuelta {round}"),
            Step::MountWorktree => "monta el worktree".to_string(),
            Step::Understand => "entiende la slice".to_string(),
            Step::OpenPullRequest => "abre la pull request".to_string(),
            Step::AwaitCi => "espera la integración continua".to_string(),
            Step::CatchUp => "se pone al día con la base".to_string(),
            Step::AwaitMerge => "espera el merge".to_string(),
        }
    }

    fn cause_of(counter: Counter) -> &'static str {
        match counter {
            Counter::Controls => "controles en rojo: ",
            Counter::Hygiene => "higiene rechazada: ",
            Counter::Judge => "el juez la devuelve: ",
            Counter::Ci => "ci en rojo: ",
            Counter::CiIndeterminate | Counter::CatchUp => "",
        }
    }
}
