//! Hikari — spike B0.0, processus CONTRÔLEUR (épreuve b : survie + relance).
//!
//! Lance le moteur dans un PROCESSUS SÉPARÉ (ADR-013) et observe sa vie. Si le moteur
//! meurt sans finir (planté, tué), le contrôleur — processus distinct — SURVIT : il le
//! détecte, le relance une fois, et le DIT. Le silence serait le vrai défaut (leçon
//! `adressage par identité`, un « ok » menteur coûte une journée).
//!
//! C'est l'ADR-001 (isolation des pannes) rendu observable : le moteur peut mourir,
//! l'application non.
//!
//! Code JETABLE (régime spike §9bis).

use std::env;
use std::io::{BufRead, BufReader};
use std::path::PathBuf;
use std::process::{Command, ExitStatus, Stdio};

use anyhow::{Context, Result, bail};

/// Le binaire moteur est le voisin du contrôleur dans le même dossier `target/<profil>/`.
fn engine_path() -> Result<PathBuf> {
    let exe = env::current_exe().context("current_exe")?;
    let dir = exe.parent().context("dossier du binaire")?;
    let name = if cfg!(windows) {
        "hikari-engine.exe"
    } else {
        "hikari-engine"
    };
    Ok(dir.join(name))
}

/// Lance le moteur une fois, relaie sa sortie ligne à ligne, rend son code de sortie.
fn run_engine_once(engine: &PathBuf, secs: &str) -> Result<ExitStatus> {
    let mut child = Command::new(engine)
        .arg(secs)
        .stdout(Stdio::piped())
        .spawn()
        .with_context(|| format!("échec du lancement de {}", engine.display()))?;

    let stdout = child.stdout.take().context("stdout du moteur absent")?;
    for line in BufReader::new(stdout).lines() {
        println!("CTRL: [moteur] {}", line?);
    }
    child.wait().context("attente du moteur")
}

fn main() -> Result<()> {
    let secs = env::args().nth(1).unwrap_or_else(|| "5".into());
    let engine = engine_path()?;
    let max_relaunch = 1usize;
    let mut relaunched = 0usize;

    loop {
        println!(
            "CTRL: lancement du moteur (processus séparé) : {}",
            engine.display()
        );
        let status = run_engine_once(&engine, &secs)?;

        // Sortie 0 = le moteur a fini sa diffusion normalement.
        if status.success() {
            println!("CTRL: moteur terminé normalement ({status})");
            return Ok(());
        }

        // Sinon : le moteur est mort sans finir. Le contrôleur, lui, tourne toujours.
        println!("CTRL: /!\\ MOTEUR MORT sans finir (code {status}) — le controleur a SURVECU");
        if relaunched < max_relaunch {
            relaunched += 1;
            println!("CTRL: relance isolee {relaunched}/{max_relaunch}...");
            continue;
        }
        bail!("moteur mort et relances epuisees");
    }
}
