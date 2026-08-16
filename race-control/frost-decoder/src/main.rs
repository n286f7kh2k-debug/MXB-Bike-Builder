mod cfg;
mod edf;

use flate2::{write::GzEncoder, Compression};
use serde::Serialize;
use std::{
    collections::HashMap,
    env, fs,
    fs::File,
    io::BufWriter,
    path::{Path, PathBuf},
};

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct NodeOut {
    name: String,
    positions: Vec<f32>,
    uvs: Vec<f32>,
    normals: Vec<f32>,
    indices: Vec<u32>,
    submeshes: Vec<edf::Submesh>,
    texture: Option<String>,
    materials: Vec<Option<usize>>,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct DecodeOut {
    format: &'static str,
    mode: String,
    nodes: Vec<NodeOut>,
}

fn usage() -> ! {
    eprintln!(
        "usage: mxb_asset_decoder <bike|rider|gear> <output.json.gz> <geom-or--> [setup-root] <edf> [edf ...]"
    );
    std::process::exit(2)
}

fn main() {
    if let Err(err) = run() {
        eprintln!("{err}");
        std::process::exit(1);
    }
}

fn run() -> Result<(), String> {
    let args: Vec<String> = env::args().collect();
    if args.len() < 5 {
        usage();
    }

    let mode = args[1].to_ascii_lowercase();
    if !matches!(mode.as_str(), "bike" | "rider" | "gear") {
        return Err(format!("unsupported mode: {}", args[1]));
    }

    let output = &args[2];
    let geom = &args[3];

    // New calls may pass the setup root explicitly. Existing Race Day Live v1.0.4/1.0.5
    // calls put the first EDF here; in that case the Process WorkingDirectory is already the
    // bike root, so preserve compatibility and use it as the setup root automatically.
    let explicit_root = args
        .get(4)
        .filter(|v| v.as_str() == "-" || Path::new(v.as_str()).is_dir());
    let (setup_root, source_start) = if let Some(root) = explicit_root {
        (root.clone(), 5usize)
    } else {
        (
            env::current_dir()
                .map_err(|e| format!("resolve bike working directory: {e}"))?
                .to_string_lossy()
                .into_owned(),
            4usize,
        )
    };
    if args.len() <= source_start {
        usage();
    }
    let sources = &args[source_start..];

    let mut nodes = if mode == "bike" {
        decode_bike(&setup_root, sources)?
    } else {
        decode_simple(&mode, sources)?
    };

    if nodes.is_empty() {
        return Err("no renderable EDF geometry was decoded".into());
    }

    if mode == "bike" && geom != "-" && Path::new(geom).is_file() {
        let bytes = fs::read(geom).map_err(|e| format!("read {geom}: {e}"))?;
        let _ = edf::assemble_bike(&mut nodes, &bytes);
    }
    edf::to_right_handed(&mut nodes);

    let nodes = nodes
        .into_iter()
        .map(|n| NodeOut {
            name: n.name,
            positions: n.positions,
            uvs: n.uvs,
            normals: n.normals,
            indices: n.indices,
            submeshes: n.submeshes,
            texture: n.texture,
            materials: n.materials,
        })
        .collect();

    // Keep the existing payload contract so the hot-swappable v1.x profile viewer accepts
    // this improved decoder without a shell restart or EXE replacement.
    let decoded = DecodeOut {
        format: "MXB-RDL-EDF-1",
        mode,
        nodes,
    };

    let file = File::create(output).map_err(|e| format!("create {output}: {e}"))?;
    let writer = BufWriter::new(file);
    let mut gzip = GzEncoder::new(writer, Compression::fast());
    serde_json::to_writer(&mut gzip, &decoded).map_err(|e| format!("serialize decode: {e}"))?;
    gzip.finish().map_err(|e| format!("finish {output}: {e}"))?;
    Ok(())
}

fn decode_simple(mode: &str, sources: &[String]) -> Result<Vec<edf::EdfNode>, String> {
    let mut nodes = Vec::new();
    for source in sources {
        let bytes = fs::read(source).map_err(|e| format!("read {source}: {e}"))?;
        let mut parsed = if mode == "gear" {
            edf::parse_gear(&bytes)
        } else {
            edf::parse(&bytes)
        };
        nodes.append(&mut parsed);
    }
    Ok(nodes)
}

/// Decode a bike the way the game/Frost resolves it: use only the live model set at the bike
/// root when one exists, follow gfx.cfg -> HRC -> level0 scene/node, then assemble by .geom.
fn decode_bike(setup_root: &str, sources: &[String]) -> Result<Vec<edf::EdfNode>, String> {
    let root = Path::new(setup_root);

    // Race Day Live v1.0.5 recursively supplied parked FrostMod Models too. Frost does not:
    // if the bike root contains a loose EDF, that is the active set and parked variants are
    // ignored. Prefer EDFs whose immediate parent is the setup root whenever any exist.
    let direct: Vec<&String> = if root.is_dir() {
        sources
            .iter()
            .filter(|s| {
                Path::new(s)
                    .parent()
                    .is_some_and(|parent| same_path(parent, root))
            })
            .collect()
    } else {
        Vec::new()
    };
    let selected: Vec<&String> = if direct.is_empty() {
        sources.iter().collect()
    } else {
        direct
    };

    let mut edfs: HashMap<String, (PathBuf, Vec<u8>)> = HashMap::new();
    for source in selected {
        let path = PathBuf::from(source);
        let bytes = fs::read(&path).map_err(|e| format!("read {source}: {e}"))?;
        let name = path
            .file_name()
            .and_then(|n| n.to_str())
            .unwrap_or(source)
            .to_ascii_lowercase();
        edfs.entry(name).or_insert((path, bytes));
    }

    if edfs.is_empty() {
        return Err("the bike bundle contains no EDF files".into());
    }

    let mut nodes = Vec::new();
    let mut resolved_scenes: Vec<(String, Vec<String>)> = Vec::new();

    if root.is_dir() {
        let hrcs = read_hrcs(root);
        if let Some(gfx_bytes) = read_named(root, "gfx.cfg") {
            let gfx = cfg::parse_gfx(&gfx_bytes);
            for part in cfg::GFX_PARTS {
                let Some(gp) = gfx.get(part) else { continue };
                let Some(hrc_file) = gp.hrc.as_deref() else { continue };
                let hrc_name = base_name(hrc_file);
                let Some(hrc_bytes) = hrcs.get(&hrc_name) else { continue };
                let parsed = cfg::parse(hrc_bytes);
                let stem = Path::new(&hrc_name)
                    .file_stem()
                    .and_then(|s| s.to_str())
                    .unwrap_or(part);
                let Some(level0) = cfg::hrc_level0(&parsed, stem) else { continue };
                let scene = cfg::hrc_level0_scene(&parsed)
                    .map(|s| base_name(&s))
                    .unwrap_or_else(|| "model.edf".to_string());
                push_scene(&mut resolved_scenes, scene, level0);
            }
        }

        if resolved_scenes.is_empty() {
            let mut names: Vec<_> = hrcs.keys().cloned().collect();
            names.sort();
            for hrc_name in names {
                let Some(hrc_bytes) = hrcs.get(&hrc_name) else { continue };
                let parsed = cfg::parse(hrc_bytes);
                let stem = Path::new(&hrc_name)
                    .file_stem()
                    .and_then(|s| s.to_str())
                    .unwrap_or("model");
                let Some(level0) = cfg::hrc_level0(&parsed, stem) else { continue };
                let scene = cfg::hrc_level0_scene(&parsed)
                    .map(|s| base_name(&s))
                    .unwrap_or_else(|| "model.edf".to_string());
                push_scene(&mut resolved_scenes, scene, level0);
            }
        }
    }

    for (scene, level0) in &resolved_scenes {
        let Some((_, bytes)) = edfs.get(scene) else { continue };
        let mut parsed = edf::parse_with_levels(bytes, level0);
        nodes.append(&mut parsed);
    }

    // Exact Frost fallback: model.edf by convention, otherwise shortest non-shadow EDF.
    if nodes.is_empty() {
        if let Some((_, bytes)) = base_edf(&edfs) {
            nodes = edf::parse(bytes);
        }
    }

    if nodes.is_empty() {
        let mut details: Vec<String> = edfs
            .iter()
            .map(|(name, (path, bytes))| {
                let magic = if bytes.len() >= 4 {
                    format!("{:02x}{:02x}{:02x}{:02x}", bytes[0], bytes[1], bytes[2], bytes[3])
                } else {
                    "short".to_string()
                };
                format!("{} ({} bytes, magic {}, {})", name, bytes.len(), magic, path.display())
            })
            .collect();
        details.sort();
        let scenes = if resolved_scenes.is_empty() {
            "none".to_string()
        } else {
            resolved_scenes
                .iter()
                .map(|(scene, names)| format!("{} => {}", scene, names.join(",")))
                .collect::<Vec<_>>()
                .join("; ")
        };
        return Err(format!(
            "no renderable EDF geometry was decoded; HRC scenes: {scenes}; EDF inputs: {}",
            details.join(" | ")
        ));
    }

    Ok(nodes)
}

fn same_path(a: &Path, b: &Path) -> bool {
    match (fs::canonicalize(a), fs::canonicalize(b)) {
        (Ok(a), Ok(b)) => a == b,
        _ => a
            .to_string_lossy()
            .eq_ignore_ascii_case(&b.to_string_lossy()),
    }
}

fn read_hrcs(root: &Path) -> HashMap<String, Vec<u8>> {
    let mut out = HashMap::new();
    let Ok(rd) = fs::read_dir(root) else { return out };
    for entry in rd.flatten() {
        let path = entry.path();
        if !path.is_file() || !path.extension().is_some_and(|e| e.eq_ignore_ascii_case("hrc")) {
            continue;
        }
        let Some(name) = path.file_name().and_then(|n| n.to_str()) else { continue };
        if let Ok(bytes) = fs::read(&path) {
            out.insert(name.to_ascii_lowercase(), bytes);
        }
    }
    out
}

fn read_named(root: &Path, wanted: &str) -> Option<Vec<u8>> {
    let rd = fs::read_dir(root).ok()?;
    for entry in rd.flatten() {
        let path = entry.path();
        let Some(name) = path.file_name().and_then(|n| n.to_str()) else { continue };
        if path.is_file() && name.eq_ignore_ascii_case(wanted) {
            return fs::read(path).ok();
        }
    }
    None
}

fn push_scene(scenes: &mut Vec<(String, Vec<String>)>, scene: String, level0: String) {
    if let Some((_, names)) = scenes.iter_mut().find(|(file, _)| file.eq_ignore_ascii_case(&scene)) {
        if !names.iter().any(|n| n.eq_ignore_ascii_case(&level0)) {
            names.push(level0);
        }
    } else {
        scenes.push((scene.to_ascii_lowercase(), vec![level0]));
    }
}

fn base_name(value: &str) -> String {
    value
        .replace('\\', "/")
        .rsplit('/')
        .next()
        .unwrap_or(value)
        .to_ascii_lowercase()
}

fn base_edf<'a>(
    edfs: &'a HashMap<String, (PathBuf, Vec<u8>)>,
) -> Option<&'a (PathBuf, Vec<u8>)> {
    if let Some(model) = edfs.get("model.edf") {
        return Some(model);
    }
    edfs.iter()
        .filter(|(name, _)| {
            let n = name.to_ascii_lowercase();
            !n.ends_with("_s.edf") && !n.contains("shadow")
        })
        .min_by_key(|(name, _)| (name.len(), (*name).clone()))
        .map(|(_, value)| value)
}
