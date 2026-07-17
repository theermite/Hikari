//! Hikari — spike B0.0, processus CONTRÔLEUR.
//!
//! Lance le moteur dans un PROCESSUS SÉPARÉ (ADR-013) et observe sa sortie. C'est la
//! forme prouvée par league_record : un moteur qui ne partage pas notre fil ne peut pas
//! geler notre interface, et il peut mourir sans nous emporter.
//!
//! Étape 1 (ici) : lancer, relayer les lignes d'état, rapporter le code de sortie.
//! Étape 2 (épreuve b) : TUER le moteur en pleine diffusion → prouver que le contrôleur
//! survit, détecte la mort, relance, et le DIT. Le silence serait le vrai défaut.
//!
//! Code JETABLE (régime spike §9bis).

use std::env;
use std::io::{BufRead, BufReader};
use std::path::PathBuf;
use std::process::{Command, Stdio};

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

fn main() -> Result<()> {
    // Durée transmise telle quelle au moteur (défaut 5 s).
    let secs = env::args().nth(1).unwrap_or_else(|| "5".into());

    let engine = engine_path()?;
    println!(
        "CTRL: lancement du moteur (processus séparé) : {}",
        engine.display()
    );

    let mut child = Command::new(&engine)
        .arg(&secs)
        .stdout(Stdio::piped())
        .spawn()
        .with_context(|| format!("échec du lancement de {}", engine.display()))?;

    // Relayer chaque ligne d'état du moteur, préfixée, pour tracer l'IPC.
    let stdout = child.stdout.take().context("stdout du moteur absent")?;
    for line in BufReader::new(stdout).lines() {
        println!("CTRL: [moteur] {}", line?);
    }

    let status = child.wait().context("attente du moteur")?;
    println!("CTRL: moteur terminé avec {status}");
    if !status.success() {
        bail!("le moteur a échoué");
    }
    Ok(())
}
