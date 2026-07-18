use std::{ffi::OsString, path::PathBuf};

use prioris::config::Config;

#[derive(Debug, Clone, PartialEq, Eq)]
enum Action {
    Run,
    SelfTest,
    Version,
    LlmSmoke(PathBuf),
    Help,
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct Cli {
    action: Action,
    config_path: PathBuf,
    no_gui: bool,
}

fn main() -> anyhow::Result<()> {
    let cli = parse_arguments(std::env::args_os().skip(1))?;
    match cli.action {
        Action::SelfTest => {
            prioris::self_test()?;
            println!("PRIORIS Rust self-test: OK");
            Ok(())
        }
        Action::Version => {
            println!("prioris {}", env!("CARGO_PKG_VERSION"));
            Ok(())
        }
        Action::LlmSmoke(model) => llm_smoke(model),
        Action::Help => {
            print_help();
            Ok(())
        }
        Action::Run => run_application(cli.config_path, cli.no_gui),
    }
}

fn run_application(config_path: PathBuf, no_gui: bool) -> anyhow::Result<()> {
    let config = Config::load(&config_path)?;
    #[cfg(any(feature = "gui", feature = "telegram"))]
    let llm = prioris::llm::LlmService::new(config.llm.clone());

    if no_gui {
        if config.telegram.token.trim().is_empty() {
            anyhow::bail!("--no-gui requires a configured Telegram token");
        }
        #[cfg(feature = "telegram")]
        return tokio::runtime::Runtime::new()?.block_on(prioris::telegram::run(config, llm));
        #[cfg(not(feature = "telegram"))]
        anyhow::bail!("this binary was built without Telegram support");
    }

    #[cfg(feature = "gui")]
    {
        #[cfg(feature = "telegram")]
        if !config.telegram.token.trim().is_empty() {
            let telegram_config = config.clone();
            let telegram_llm = llm.clone();
            std::thread::Builder::new()
                .name("prioris-telegram".to_owned())
                .spawn(move || match tokio::runtime::Runtime::new() {
                    Ok(runtime) => {
                        if let Err(error) =
                            runtime.block_on(prioris::telegram::run(telegram_config, telegram_llm))
                        {
                            eprintln!("Telegram stopped: {error}");
                        }
                    }
                    Err(error) => eprintln!("Telegram runtime failed: {error}"),
                })?;
        }
        prioris::gui::run(config, config_path, llm)
    }

    #[cfg(all(not(feature = "gui"), feature = "telegram"))]
    {
        if config.telegram.token.trim().is_empty() {
            anyhow::bail!("this build has no GUI and Telegram is not configured");
        }
        tokio::runtime::Runtime::new()?.block_on(prioris::telegram::run(config, llm))
    }

    #[cfg(all(not(feature = "gui"), not(feature = "telegram")))]
    anyhow::bail!("this binary was built without GUI and Telegram support")
}

fn llm_smoke(model: PathBuf) -> anyhow::Result<()> {
    #[cfg(feature = "embedded-llm")]
    {
        use prioris::config::LlmConfig;

        let service = prioris::llm::LlmService::new(LlmConfig {
            enabled: true,
            provider: "local_gguf".to_owned(),
            model,
            ..LlmConfig::default()
        });
        let latency = service.health_check()?;
        let interpreted = service.interpret_axis(
            prioris::core::Axis::IMP,
            prioris::core::Axis::IMP.question_fr(),
            "Une différence majeure et clairement mesurable.",
        )?;
        println!(
            "PRIORIS Rust embedded LLM: OK ({latency} ms, IMP={})",
            interpreted.value
        );
        Ok(())
    }
    #[cfg(not(feature = "embedded-llm"))]
    {
        let _ = model;
        anyhow::bail!("this binary was built without embedded LLM support")
    }
}

fn parse_arguments(arguments: impl IntoIterator<Item = OsString>) -> anyhow::Result<Cli> {
    let mut arguments = arguments.into_iter();
    let mut cli = Cli {
        action: Action::Run,
        config_path: "config.toml".into(),
        no_gui: false,
    };
    let mut positional_config = false;

    while let Some(argument) = arguments.next() {
        match argument.to_string_lossy().as_ref() {
            "--config" => {
                cli.config_path = arguments
                    .next()
                    .map(PathBuf::from)
                    .ok_or_else(|| anyhow::anyhow!("--config requires a path"))?;
                positional_config = true;
            }
            "--no-gui" | "--headless" => cli.no_gui = true,
            "--self-test" => cli.action = Action::SelfTest,
            "--version" => cli.action = Action::Version,
            "--help" | "-h" => cli.action = Action::Help,
            "--llm-smoke" => {
                let model = arguments
                    .next()
                    .map(PathBuf::from)
                    .ok_or_else(|| anyhow::anyhow!("--llm-smoke requires a GGUF path"))?;
                cli.action = Action::LlmSmoke(model);
            }
            value if value.starts_with('-') => anyhow::bail!("unknown argument: {value}"),
            _ if !positional_config && cli.action == Action::Run => {
                cli.config_path = PathBuf::from(argument);
                positional_config = true;
            }
            value => anyhow::bail!("unexpected argument: {value}"),
        }
    }
    Ok(cli)
}

fn print_help() {
    println!(
        "PRIORIS Rust\n\nUsage:\n  prioris [--config PATH] [--no-gui]\n  prioris --self-test\n  prioris --llm-smoke MODEL.gguf\n\nOptions:\n  --config PATH  Configuration file (default: config.toml)\n  --no-gui       Run Telegram only; requires a configured token\n  --headless     Alias for --no-gui\n  --help         Show this help"
    );
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_headless_and_config_in_any_order() {
        let parsed = parse_arguments([
            OsString::from("--no-gui"),
            OsString::from("--config"),
            OsString::from("settings.toml"),
        ])
        .unwrap();
        assert!(parsed.no_gui);
        assert_eq!(parsed.config_path, PathBuf::from("settings.toml"));
    }

    #[test]
    fn positional_config_remains_supported() {
        let parsed = parse_arguments([OsString::from("custom.toml")]).unwrap();
        assert_eq!(parsed.config_path, PathBuf::from("custom.toml"));
        assert_eq!(parsed.action, Action::Run);
    }
}
