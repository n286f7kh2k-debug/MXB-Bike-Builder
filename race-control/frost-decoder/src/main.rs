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
        "usage: mxb_asset_decoder <bike|rider|gear> <output.json.gz> <geom-or--> <setup-root-or--> <edf> [edf ...]"
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
    if args.len() < 6 {
        usage();
    }

    let mode = args[1].to_ascii_lowercase();
    if !matches!(mode.as_str(), "bike" | "rider" | "gear") {
        return Err(format!("unsupported mode: {}", args[1]));
    }

    let output = &args[2];
    let geom = &args[3];
    let setup_root = &args[4];
    let sources = &args[5..];

    let mut nodes = if mode == "bike" {
        decode_bike(setup_root, sources)?
    } else {
        decode_simple(&mode, sources)?
    };

    if nodes.is_empty() {
        return Err("no renderable EDF geometry was decoded".into());
    }

    // Frost assembles bike parts in the game's authored frame, then converts the complete
    // result to the right-handed Y-up frame used by its viewer.
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

    let decoded = DecodeOut {
        format: "MXB-RDL-EDF-2",
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

/// Decode a bike the same way MX Bikes/Frost resolves it: gfx.cfg chooses each part's HRC,
/// the HRC level0 block chooses the scene EDF and node name, and only those level0 nodes are
/// rendered. This matters for OEM EDFs whose node names do not survive the generic heuristic.
fn decode_bike(setup_root: &str, sources: &[String]) -> Result<Vec<edf::EdfNode>, String> {
    let mut edfs: HashMap<String, (PathBuf, Vec<u8>)> = HashMap::new();
    for source in sources {
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

    if setup_root != "-" {
        let root = Path::new(setup_root);
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

            // Some mods have valid HRCs but an unusual/incomplete gfx.cfg. Frost's HRC chain is
            // still authoritative, so use every root HRC as a safe second path when gfx resolved
            // nothing rather than falling back to a filename guess immediately.
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
    }

    for (scene, level0) in &resolved_scenes {
        let Some((_, bytes)) = edfs.get(scene) else { continue };
        let mut parsed = edf::parse_with_levels(bytes, level0);
        nodes.append(&mut parsed);
    }

    // Exact Frost fallback: model.edf by convention, else the shortest non-shadow EDF.
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
