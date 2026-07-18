use std::{
    fs,
    path::{Path, PathBuf},
};

use serde::{Deserialize, Serialize};
use thiserror::Error;

#[derive(Debug, Error)]
pub enum ConfigError {
    #[error("cannot read {path}: {source}")]
    Read {
        path: PathBuf,
        source: std::io::Error,
    },
    #[error("invalid TOML in {path}: {source}")]
    Parse {
        path: PathBuf,
        source: toml::de::Error,
    },
    #[error("cannot serialize configuration: {0}")]
    Serialize(#[from] toml::ser::Error),
    #[error("cannot write {path}: {source}")]
    Write {
        path: PathBuf,
        source: std::io::Error,
    },
}

#[derive(Debug, Clone, Deserialize, Serialize, Default, PartialEq, Eq)]
#[serde(default)]
pub struct Config {
    pub telegram: TelegramConfig,
    pub database: DatabaseConfig,
    pub ui: UiConfig,
    pub obsidian: ObsidianConfig,
    pub llm: LlmConfig,
}

impl Config {
    pub fn load(path: impl AsRef<Path>) -> Result<Self, ConfigError> {
        let path = path.as_ref();
        let text = fs::read_to_string(path).map_err(|source| ConfigError::Read {
            path: path.to_path_buf(),
            source,
        })?;
        toml::from_str(&text).map_err(|source| ConfigError::Parse {
            path: path.to_path_buf(),
            source,
        })
    }

    pub fn save(&self, path: impl AsRef<Path>) -> Result<(), ConfigError> {
        let path = path.as_ref();
        if let Some(parent) = path.parent().filter(|value| !value.as_os_str().is_empty()) {
            fs::create_dir_all(parent).map_err(|source| ConfigError::Write {
                path: parent.to_path_buf(),
                source,
            })?;
        }
        let text = toml::to_string_pretty(self)?;
        fs::write(path, text).map_err(|source| ConfigError::Write {
            path: path.to_path_buf(),
            source,
        })?;
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;

            fs::set_permissions(path, fs::Permissions::from_mode(0o600)).map_err(|source| {
                ConfigError::Write {
                    path: path.to_path_buf(),
                    source,
                }
            })?;
        }
        Ok(())
    }
}

#[derive(Debug, Clone, Deserialize, Serialize, Default, PartialEq, Eq)]
#[serde(default)]
pub struct TelegramConfig {
    pub token: String,
}

#[derive(Debug, Clone, Deserialize, Serialize, PartialEq, Eq)]
#[serde(default)]
pub struct DatabaseConfig {
    pub path: PathBuf,
}

impl Default for DatabaseConfig {
    fn default() -> Self {
        Self {
            path: "prioris.db".into(),
        }
    }
}

#[derive(Debug, Clone, Deserialize, Serialize, PartialEq, Eq)]
#[serde(default)]
pub struct UiConfig {
    pub language: String,
}

impl Default for UiConfig {
    fn default() -> Self {
        Self {
            language: "fr".to_owned(),
        }
    }
}

#[derive(Debug, Clone, Deserialize, Serialize, PartialEq, Eq)]
#[serde(default)]
pub struct ObsidianConfig {
    pub vault_path: PathBuf,
    pub prioris_dir: String,
}

impl Default for ObsidianConfig {
    fn default() -> Self {
        Self {
            vault_path: PathBuf::new(),
            prioris_dir: "PRIORIS".to_owned(),
        }
    }
}

#[derive(Debug, Clone, Deserialize, Serialize, PartialEq, Eq)]
#[serde(default)]
pub struct LlmConfig {
    pub enabled: bool,
    pub provider: String,
    pub model: PathBuf,
    pub api_key: String,
    pub api_key_env: String,
    pub base_url: String,
    pub timeout_s: u64,
    pub max_tokens: usize,
    pub keep_warm: bool,
}

impl Default for LlmConfig {
    fn default() -> Self {
        Self {
            enabled: false,
            provider: "prioris".to_owned(),
            model: "models/Ministral-3-3B-Instruct-2512-Q4_K_M.gguf".into(),
            api_key: String::new(),
            api_key_env: String::new(),
            base_url: String::new(),
            timeout_s: 120,
            max_tokens: 512,
            keep_warm: true,
        }
    }
}

impl LlmConfig {
    pub fn effective_api_key(&self) -> String {
        if self.api_key_env.is_empty() {
            self.api_key.clone()
        } else {
            std::env::var(&self.api_key_env).unwrap_or_else(|_| self.api_key.clone())
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn configuration_round_trip_preserves_all_sections() {
        let directory = tempfile::tempdir().unwrap();
        let path = directory.path().join("config.toml");
        let mut config = Config::default();
        config.telegram.token = "telegram-secret".to_owned();
        config.obsidian.vault_path = "ObsidianVault".into();
        config.llm.enabled = true;
        config.llm.provider = "local_gguf".to_owned();

        config.save(&path).unwrap();

        assert_eq!(Config::load(&path).unwrap(), config);
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;

            assert_eq!(
                fs::metadata(path).unwrap().permissions().mode() & 0o777,
                0o600
            );
        }
    }
}
