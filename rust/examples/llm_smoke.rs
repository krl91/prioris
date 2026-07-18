#[cfg(feature = "embedded-llm")]
fn main() -> anyhow::Result<()> {
    use std::path::PathBuf;

    use prioris::{config::LlmConfig, llm::LlmService};

    let model = std::env::args_os()
        .nth(1)
        .map(PathBuf::from)
        .ok_or_else(|| anyhow::anyhow!("usage: llm_smoke <model.gguf>"))?;
    let config = LlmConfig {
        enabled: true,
        provider: "local_gguf".to_owned(),
        model,
        ..LlmConfig::default()
    };
    let service = LlmService::new(config);
    let latency = service.health_check()?;
    println!("embedded GGUF inference is ready ({latency} ms)");
    Ok(())
}

#[cfg(not(feature = "embedded-llm"))]
fn main() {
    eprintln!("build this example with --features embedded-llm");
    std::process::exit(2);
}
