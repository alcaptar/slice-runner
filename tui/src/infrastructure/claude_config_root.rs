use std::ffi::OsString;
use std::path::PathBuf;

pub struct ClaudeConfigRoot;

impl ClaudeConfigRoot {
    const VARIABLE: &'static str = "CLAUDE_CONFIG_DIR";
    const HOME_VARIABLE: &'static str = "HOME";
    const DEFAULT_FOLDER: &'static str = ".claude";

    pub fn resolved() -> Option<PathBuf> {
        Self::present(std::env::var_os(Self::VARIABLE))
            .map(PathBuf::from)
            .or_else(|| {
                Self::present(std::env::var_os(Self::HOME_VARIABLE))
                    .map(|home| PathBuf::from(home).join(Self::DEFAULT_FOLDER))
            })
    }

    fn present(value: Option<OsString>) -> Option<OsString> {
        value.filter(|text| !text.is_empty())
    }
}
