mod application;
mod domain;
mod infrastructure;
#[cfg(test)]
mod tests;

use std::process::ExitCode;

use crate::infrastructure::cli::Cli;

fn main() -> ExitCode {
    Cli::main()
}
