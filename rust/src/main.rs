use std::{
    ffi::OsString,
    path::{Path, PathBuf},
};

#[cfg(target_os = "macos")]
use std::{
    fs::{self, OpenOptions},
    io::Write,
    os::unix::fs::{PermissionsExt, symlink},
    process::Command,
};

use prioris::config::Config;

#[derive(Debug, Clone, PartialEq, Eq)]
enum Action {
    Run,
    SelfTest,
    RuntimeSmoke,
    Version,
    LlmSmoke(PathBuf),
    Help,
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct Cli {
    action: Action,
    config_path: PathBuf,
    config_explicit: bool,
    no_gui: bool,
}

fn main() {
    if let Err(error) = try_main() {
        eprintln!("PRIORIS failed to start: {error:#}");
        report_startup_error(&error);
        std::process::exit(1);
    }
}

fn try_main() -> anyhow::Result<()> {
    let cli = parse_arguments(std::env::args_os().skip(1))?;
    match cli.action {
        Action::SelfTest => {
            prioris::self_test()?;
            println!("PRIORIS Rust self-test: OK");
            Ok(())
        }
        Action::RuntimeSmoke => runtime_smoke(cli.config_path, cli.config_explicit),
        Action::Version => {
            println!("prioris {}", env!("CARGO_PKG_VERSION"));
            Ok(())
        }
        Action::LlmSmoke(model) => llm_smoke(model),
        Action::Help => {
            print_help();
            Ok(())
        }
        Action::Run => run_application(cli.config_path, cli.config_explicit, cli.no_gui),
    }
}

fn run_application(
    config_path: PathBuf,
    config_explicit: bool,
    no_gui: bool,
) -> anyhow::Result<()> {
    let config_path = prepare_macos_runtime(config_path, config_explicit)?;
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

#[cfg(target_os = "macos")]
fn macos_bundle_resources_dir(executable: &Path) -> Option<PathBuf> {
    let macos = executable.parent()?;
    if macos.file_name()? != "MacOS" {
        return None;
    }
    let contents = macos.parent()?;
    if contents.file_name()? != "Contents" {
        return None;
    }
    let application = contents.parent()?;
    if application.extension()? != "app" {
        return None;
    }
    Some(contents.join("Resources"))
}

#[cfg(target_os = "macos")]
fn prepare_macos_runtime(config_path: PathBuf, config_explicit: bool) -> anyhow::Result<PathBuf> {
    if config_explicit {
        return Ok(config_path);
    }
    let Some(resources) = macos_bundle_resources_dir(&std::env::current_exe()?) else {
        return Ok(config_path);
    };
    let support = macos_application_support_dir()?;
    initialize_macos_application_data(&resources, &support)?;
    std::env::set_current_dir(&support)?;
    Ok(support.join("config.toml"))
}

#[cfg(not(target_os = "macos"))]
fn prepare_macos_runtime(config_path: PathBuf, _config_explicit: bool) -> anyhow::Result<PathBuf> {
    Ok(config_path)
}

#[cfg(target_os = "macos")]
fn macos_application_support_dir() -> anyhow::Result<PathBuf> {
    if let Some(directory) = std::env::var_os("PRIORIS_DATA_DIR") {
        return Ok(PathBuf::from(directory));
    }
    let home = std::env::var_os("HOME").ok_or_else(|| anyhow::anyhow!("HOME is not defined"))?;
    Ok(PathBuf::from(home)
        .join("Library")
        .join("Application Support")
        .join("PRIORIS"))
}

#[cfg(target_os = "macos")]
fn initialize_macos_application_data(resources: &Path, support: &Path) -> anyhow::Result<()> {
    anyhow::ensure!(
        resources.is_dir(),
        "missing app resources: {}",
        resources.display()
    );
    fs::create_dir_all(support)?;
    let config_path = support.join("config.toml");
    copy_file_if_missing(&resources.join("config.toml"), &config_path)?;
    fs::set_permissions(&config_path, fs::Permissions::from_mode(0o600))?;
    copy_directory_if_missing(
        &resources.join("ObsidianVault"),
        &support.join("ObsidianVault"),
    )?;
    link_bundled_models(&resources.join("models"), &support.join("models"))?;
    Ok(())
}

#[cfg(target_os = "macos")]
fn copy_file_if_missing(source: &Path, destination: &Path) -> anyhow::Result<()> {
    if destination.exists() {
        return Ok(());
    }
    anyhow::ensure!(
        source.is_file(),
        "missing bundled file: {}",
        source.display()
    );
    fs::copy(source, destination)?;
    Ok(())
}

#[cfg(target_os = "macos")]
fn copy_directory_if_missing(source: &Path, destination: &Path) -> anyhow::Result<()> {
    anyhow::ensure!(
        source.is_dir(),
        "missing bundled directory: {}",
        source.display()
    );
    fs::create_dir_all(destination)?;
    for entry in fs::read_dir(source)? {
        let entry = entry?;
        let source_path = entry.path();
        let destination_path = destination.join(entry.file_name());
        if entry.file_type()?.is_dir() {
            copy_directory_if_missing(&source_path, &destination_path)?;
        } else {
            copy_file_if_missing(&source_path, &destination_path)?;
        }
    }
    Ok(())
}

#[cfg(target_os = "macos")]
fn link_bundled_models(source: &Path, destination: &Path) -> anyhow::Result<()> {
    anyhow::ensure!(
        source.is_dir(),
        "missing bundled models: {}",
        source.display()
    );
    fs::create_dir_all(destination)?;
    for entry in fs::read_dir(source)? {
        let entry = entry?;
        if !entry.file_type()?.is_file() {
            continue;
        }
        let source_path = entry.path();
        let destination_path = destination.join(entry.file_name());
        if destination_path.symlink_metadata().is_ok() {
            if destination_path.read_link().ok().as_deref() == Some(source_path.as_path()) {
                continue;
            }
            if destination_path
                .symlink_metadata()?
                .file_type()
                .is_symlink()
            {
                fs::remove_file(&destination_path)?;
            } else {
                continue;
            }
        }
        symlink(&source_path, &destination_path)?;
    }
    Ok(())
}

#[cfg(target_os = "macos")]
fn report_startup_error(error: &anyhow::Error) {
    let details = format!("{error:#}");
    let log_path = startup_log_path();
    if let Some(parent) = log_path.parent() {
        let _ = fs::create_dir_all(parent);
    }
    if let Ok(mut log) = OpenOptions::new().create(true).append(true).open(&log_path) {
        let _ = writeln!(
            log,
            "{} | PRIORIS {} | {details}",
            chrono::Local::now().to_rfc3339(),
            env!("CARGO_PKG_VERSION")
        );
    }

    if std::env::current_exe()
        .ok()
        .as_deref()
        .and_then(macos_bundle_resources_dir)
        .is_none()
    {
        return;
    }
    let message = format!(
        "PRIORIS n'a pas pu démarrer.\n\n{details}\n\nJournal : {}",
        log_path.display()
    );
    let script = format!(
        "display alert \"PRIORIS\" message {} as critical buttons {{\"OK\"}} default button \"OK\"",
        apple_script_string(&message)
    );
    let _ = Command::new("/usr/bin/osascript")
        .args(["-e", &script])
        .status();
}

#[cfg(not(target_os = "macos"))]
fn report_startup_error(_error: &anyhow::Error) {}

#[cfg(target_os = "macos")]
fn startup_log_path() -> PathBuf {
    std::env::var_os("HOME").map_or_else(
        || PathBuf::from("prioris-startup.log"),
        |home| {
            PathBuf::from(home)
                .join("Library")
                .join("Logs")
                .join("PRIORIS")
                .join("prioris.log")
        },
    )
}

#[cfg(target_os = "macos")]
fn apple_script_string(value: &str) -> String {
    format!(
        "\"{}\"",
        value
            .replace('\\', "\\\\")
            .replace('"', "\\\"")
            .replace('\n', "\\n")
    )
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
        let challenge = service.interpret_challenge(
            "Manger",
            "P1",
            "Pourquoi aucune action immédiate n'est-elle nécessaire ?",
            "La question comporte une information fausse.",
        )?;
        anyhow::ensure!(
            challenge.outcome == prioris::llm::ChallengeOutcome::PremiseFalse,
            "the embedded model did not preserve a challenged premise"
        );
        let binary = service.interpret_challenge(
            "Manager",
            "P1",
            "Y a-t-il une pression sociale ?",
            "non",
        )?;
        anyhow::ensure!(
            binary.axis.is_none() && binary.uncertainty == prioris::core::Uncertainty::Certain,
            "a short no must be accepted without an invented score"
        );
        let mirror = service.interpret_option(
            "Si tu attendais une semaine, que se passerait-il ?",
            &[
                ("Un vrai problème".to_owned(), "0".to_owned()),
                ("Rien de grave, en fait".to_owned(), "1".to_owned()),
                ("Je ne sais pas".to_owned(), "2".to_owned()),
            ],
            "je meurt car j'ai besoin de manger pour vivre",
        )?;
        anyhow::ensure!(
            mirror.value == "0" && mirror.uncertainty == prioris::core::Uncertainty::Certain,
            "a clear vital consequence must select the strongest mirror option"
        );
        println!(
            "PRIORIS Rust embedded LLM: OK ({latency} ms, IMP={}, false premise, short no and mirror accepted)",
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

fn runtime_smoke(config_path: PathBuf, config_explicit: bool) -> anyhow::Result<()> {
    let config_path = prepare_macos_runtime(config_path, config_explicit)?;
    let config = Config::load(&config_path)?;
    let working_directory = std::env::current_dir()?;
    let vault = absolute_from(&working_directory, &config.obsidian.vault_path);
    let model = absolute_from(&working_directory, &config.llm.model);
    anyhow::ensure!(config_path.is_file(), "runtime config was not initialized");
    anyhow::ensure!(vault.is_dir(), "runtime vault was not initialized");
    anyhow::ensure!(model.is_file(), "runtime model was not initialized");
    println!("PRIORIS Rust bundle runtime: OK");
    Ok(())
}

fn absolute_from(base: &Path, path: &Path) -> PathBuf {
    if path.is_absolute() {
        path.to_path_buf()
    } else {
        base.join(path)
    }
}

fn parse_arguments(arguments: impl IntoIterator<Item = OsString>) -> anyhow::Result<Cli> {
    let mut arguments = arguments.into_iter();
    let mut cli = Cli {
        action: Action::Run,
        config_path: "config.toml".into(),
        config_explicit: false,
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
                cli.config_explicit = true;
            }
            "--no-gui" | "--headless" => cli.no_gui = true,
            "--self-test" => cli.action = Action::SelfTest,
            "--runtime-smoke" => cli.action = Action::RuntimeSmoke,
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
                cli.config_explicit = true;
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
        assert!(parsed.config_explicit);
    }

    #[test]
    fn positional_config_remains_supported() {
        let parsed = parse_arguments([OsString::from("custom.toml")]).unwrap();
        assert_eq!(parsed.config_path, PathBuf::from("custom.toml"));
        assert_eq!(parsed.action, Action::Run);
        assert!(parsed.config_explicit);
    }

    #[test]
    fn default_config_is_not_explicit() {
        let parsed = parse_arguments([]).unwrap();
        assert_eq!(parsed.config_path, PathBuf::from("config.toml"));
        assert!(!parsed.config_explicit);
    }

    #[test]
    fn parses_internal_runtime_smoke_action() {
        let parsed = parse_arguments([OsString::from("--runtime-smoke")]).unwrap();
        assert_eq!(parsed.action, Action::RuntimeSmoke);
        assert!(!parsed.config_explicit);
    }

    #[cfg(target_os = "macos")]
    #[test]
    fn finds_resources_directory_inside_macos_app() {
        let executable = Path::new(
            "/Applications/prioris-rust-v0.2.5-macos-arm64/PRIORIS.app/Contents/MacOS/prioris",
        );
        assert_eq!(
            macos_bundle_resources_dir(executable),
            Some(PathBuf::from(
                "/Applications/prioris-rust-v0.2.5-macos-arm64/PRIORIS.app/Contents/Resources"
            ))
        );
        assert_eq!(macos_bundle_resources_dir(Path::new("/tmp/prioris")), None);
    }

    #[cfg(target_os = "macos")]
    #[test]
    fn initializes_writable_macos_data_without_overwriting_it() {
        let root = tempfile::tempdir().unwrap();
        let resources = root.path().join("Resources");
        let support = root.path().join("Application Support/PRIORIS");
        fs::create_dir_all(resources.join("models")).unwrap();
        fs::create_dir_all(resources.join("ObsidianVault/PRIORIS")).unwrap();
        fs::write(resources.join("config.toml"), "initial").unwrap();
        fs::write(resources.join("ObsidianVault/index.md"), "vault").unwrap();
        fs::write(resources.join("models/model.gguf"), "model").unwrap();

        initialize_macos_application_data(&resources, &support).unwrap();
        fs::write(support.join("config.toml"), "custom").unwrap();
        initialize_macos_application_data(&resources, &support).unwrap();

        assert_eq!(
            fs::read_to_string(support.join("config.toml")).unwrap(),
            "custom"
        );
        assert_eq!(
            fs::metadata(support.join("config.toml"))
                .unwrap()
                .permissions()
                .mode()
                & 0o777,
            0o600
        );
        assert_eq!(
            fs::read_to_string(support.join("ObsidianVault/index.md")).unwrap(),
            "vault"
        );
        assert_eq!(
            support.join("models/model.gguf").read_link().unwrap(),
            resources.join("models/model.gguf")
        );
    }
}
