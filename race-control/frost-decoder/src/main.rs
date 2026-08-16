mod edf;

use flate2::{write::GzEncoder, Compression};
use serde::Serialize;
use std::{env, fs, fs::File, io::BufWriter, path::Path};

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
    eprintln!("usage: mxb_asset_decoder <bike|rider|gear> <output.json.gz> <geom-or--> <edf> [edf ...]");
    std::process::exit(2);
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
    let sources = &args[4..];

    let mut nodes = Vec::new();
    for source in sources {
        let bytes = fs::read(source).map_err(|e| format!("read {source}: {e}"))?;
        let mut parsed = if mode == "gear" {
            edf::parse_gear(&bytes)
        } else {
            edf::parse(&bytes)
        };
        if parsed.is_empty() {
            log::warn!("no EDF nodes decoded from {source}");
        }
        nodes.append(&mut parsed);
    }
    if nodes.is_empty() {
        return Err("no renderable EDF geometry was decoded".into());
    }

    // Frost assembles bike parts in the game's authored frame, then converts the complete
    // result to the right-handed Y-up frame used by its viewer. Gear/rider parts use the
    // same handedness conversion after parsing.
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
