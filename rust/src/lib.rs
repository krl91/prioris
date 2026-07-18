pub mod config;
pub mod core;
pub mod llm;
pub mod store;
pub mod vault;

#[cfg(feature = "gui")]
pub mod gui;

#[cfg(feature = "telegram")]
pub mod telegram;

pub fn self_test() -> anyhow::Result<()> {
    use std::collections::{HashMap, HashSet};

    use core::{Axis, Estimate, score};

    let store = store::Store::open(":memory:")?;
    let task_id = store.create_task("Self-test", "travail", None, "self-test", None)?;
    anyhow::ensure!(task_id > 0, "task creation failed");
    let axes = Axis::ALL
        .into_iter()
        .map(|axis| (axis, axis.median()))
        .collect::<HashMap<_, _>>();
    let result = score(
        &axes,
        Estimate::M15_30,
        None,
        &HashMap::new(),
        &HashSet::new(),
        "self-test",
        None,
    )?;
    anyhow::ensure!(
        (0.0..=100.0).contains(&result.global),
        "score outside expected range"
    );
    anyhow::ensure!(
        store.categories()?.len() >= 9,
        "default categories are missing"
    );
    Ok(())
}
