"""Blender background renderer for immutable CGB canonical ground-truth views."""

from __future__ import annotations

import argparse
from array import array
import hashlib
from pathlib import Path
import sys

TOOLS_ROOT = Path(__file__).resolve().parent
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

try:
    import bpy
    from mathutils import Vector
except ImportError:  # Allows --help/source inspection outside Blender.
    bpy = None
    Vector = None

from build_corpus import CORE10, SMOKE3
from common import GENERATIVE_ROOT, PROJECT_ROOT, VALIDATION_ROOT, read_json, sha256_file, stable_hash, write_json


def _arguments() -> argparse.Namespace:
    values = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", type=Path, default=PROJECT_ROOT / ".validation-assets" / "dataset")
    parser.add_argument("--output-root", type=Path, default=VALIDATION_ROOT / "reference-renders")
    parser.add_argument("--subset", choices=("smoke3", "core10", "full27"), default="smoke3")
    parser.add_argument("--determinism-check", action="store_true")
    return parser.parse_args(values)


def _clear_scene() -> None:
    for item in tuple(bpy.data.objects):
        bpy.data.objects.remove(item, do_unlink=True)
    for item in tuple(bpy.data.materials):
        if item.users == 0:
            bpy.data.materials.remove(item)


def _import_mesh(path: Path):
    before = set(bpy.data.objects)
    suffix = path.suffix.lower()
    if suffix == ".stl":
        bpy.ops.wm.stl_import(filepath=str(path))
    elif suffix == ".obj":
        bpy.ops.wm.obj_import(filepath=str(path))
    elif suffix == ".ply":
        bpy.ops.wm.ply_import(filepath=str(path))
    else:
        raise ValueError(f"Unsupported reference source format: {suffix}")
    imported = [item for item in bpy.data.objects if item not in before and item.type == "MESH"]
    if len(imported) != 1:
        raise RuntimeError(f"Expected one imported mesh, found {len(imported)}")
    return imported[0]


def _render_copy(source, config: dict[str, object]):
    source.hide_render = True
    rendered = source.copy()
    rendered.data = source.data.copy()
    rendered.name = f"{source.name}_CGB_RenderCopy"
    bpy.context.scene.collection.objects.link(rendered)
    rendered.hide_render = False
    coordinates = [vertex.co.copy() for vertex in rendered.data.vertices]
    minimum = Vector(tuple(min(value[axis] for value in coordinates) for axis in range(3)))
    maximum = Vector(tuple(max(value[axis] for value in coordinates) for axis in range(3)))
    center = (minimum + maximum) * 0.5
    maximum_dimension = max(maximum[axis] - minimum[axis] for axis in range(3))
    if maximum_dimension <= 0:
        raise ValueError("Reference source has zero dimensions.")
    for vertex in rendered.data.vertices:
        vertex.co -= center
    rendered.location = (0.0, 0.0, 0.0)
    rendered.rotation_euler = (0.0, 0.0, 0.0)
    rendered.scale = (2.0 / maximum_dimension,) * 3
    material = bpy.data.materials.new("CGB_Clay")
    material.diffuse_color = tuple(config["clay_rgba"])
    material.use_nodes = True
    material.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = tuple(config["clay_rgba"])
    rendered.data.materials.clear()
    rendered.data.materials.append(material)
    return rendered


def _configure_scene(config: dict[str, object]):
    scene = bpy.context.scene
    scene.render.engine = str(config["engine"])
    scene.render.resolution_x, scene.render.resolution_y = map(int, config["resolution"])
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = bool(config["transparent"])
    scene.render.image_settings.file_format = str(config["file_format"])
    scene.render.image_settings.color_mode = "RGBA"
    scene.view_settings.look = "None"
    scene.view_settings.view_transform = str(config["color_management"])
    world = bpy.data.worlds.new("CGB_Neutral_World") if scene.world is None else scene.world
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = tuple(config["background_rgba"])
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.45
    camera_data = bpy.data.cameras.new("CGB_Camera")
    camera_data.lens = float(config["camera_lens_mm"])
    camera = bpy.data.objects.new("CGB_Camera", camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    for name, location, energy, size in (
        ("CGB_Key", (-3.2, -4.0, 4.5), 900.0, 4.0),
        ("CGB_Fill", (4.0, -1.5, 2.0), 500.0, 3.0),
        ("CGB_Rim", (0.0, 3.5, 4.0), 700.0, 3.0),
    ):
        data = bpy.data.lights.new(name, "AREA")
        data.energy, data.shape, data.size = energy, "DISK", size
        light = bpy.data.objects.new(name, data)
        light.location = location
        light.rotation_euler = ((Vector((0.0, 0.0, 0.0)) - light.location).to_track_quat("-Z", "Y")).to_euler()
        scene.collection.objects.link(light)
    return scene, camera


def _render_view(scene, camera, case_directory: Path, view: str, location: list[float]) -> dict[str, object]:
    camera.location = tuple(location)
    camera.rotation_euler = ((Vector((0.0, 0.0, 0.0)) - camera.location).to_track_quat("-Z", "Y")).to_euler()
    output = case_directory / f"{view}.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(output)
    bpy.ops.render.render(write_still=True)
    image = bpy.data.images.load(str(output), check_existing=False)
    try:
        values = array("f", [0.0]) * len(image.pixels)
        image.pixels.foreach_get(values)
    finally:
        bpy.data.images.remove(image)
    pixels = bytes(max(0, min(255, round(value * 255.0))) for value in values)
    background = pixels[:4]
    foreground_pixels = sum(
        pixels[index:index + 4] != background for index in range(0, len(pixels), 4)
    )
    if foreground_pixels == 0:
        raise RuntimeError(f"Reference render is blank: {view}")
    return {
        "path": output.as_posix(),
        "sha256": hashlib.sha256(pixels).hexdigest(),
        "hash_basis": "DECODED_RGBA8_PIXELS",
        "file_sha256": sha256_file(output),
        "bytes": output.stat().st_size,
        "foreground_pixels": foreground_pixels,
        "foreground_fraction": foreground_pixels / (len(pixels) // 4),
    }


def render(args: argparse.Namespace) -> dict[str, object]:
    if bpy is None:
        raise RuntimeError("This renderer must run inside Blender.")
    config = read_json(GENERATIVE_ROOT / "render_config.json")
    config_hash = stable_hash(config)
    manifest = read_json(args.dataset_root / "manifests" / "statue_dataset_manifest.json")
    assets = {str(item["unique_id"]): item for item in manifest["assets"]}
    ids = SMOKE3 if args.subset == "smoke3" else CORE10 if args.subset == "core10" else tuple(sorted(assets))
    index: dict[str, object] = {
        "schema_version": "1.0.0", "renderer_version": config["renderer_version"],
        "blender_version": bpy.app.version_string, "subset": args.subset,
        "render_config": config, "render_config_hash": config_hash,
        "source_mutation_count": 0, "cases": {}, "determinism_check": "NOT_RUN",
    }
    for case_index, case_id in enumerate(ids):
        asset = assets[case_id]
        source_path = args.dataset_root / "raw" / str(asset["stored_filename"])
        before_hash = sha256_file(source_path)
        if before_hash != asset["checksum_sha256"]:
            raise RuntimeError(f"Source hash mismatch before render: {case_id}")
        _clear_scene()
        source = _import_mesh(source_path)
        _render_copy(source, config)
        scene, camera = _configure_scene(config)
        views = {
            view: _render_view(scene, camera, args.output_root / case_id, view, config["camera_positions"][view])
            for view in config["reference_views"]
        }
        if args.determinism_check and case_index == 0:
            repeat_root = args.output_root / ".determinism-repeat" / case_id
            repeat = {
                view: _render_view(scene, camera, repeat_root, view, config["camera_positions"][view])
                for view in config["reference_views"]
            }
            index["determinism_check"] = "PASS" if all(views[view]["sha256"] == repeat[view]["sha256"] for view in views) else "FAIL"
        after_hash = sha256_file(source_path)
        if after_hash != before_hash:
            index["source_mutation_count"] = int(index["source_mutation_count"]) + 1
            raise RuntimeError(f"Source changed during reference rendering: {case_id}")
        index["cases"][case_id] = {
            "source_sha256_before": before_hash, "source_sha256_after": after_hash,
            "source_immutable": True, "views": views,
        }
        print(f"{case_index + 1}/{len(ids)} {case_id}: PASS", flush=True)
    index["case_count"] = len(ids)
    index["render_count"] = len(ids) * len(config["reference_views"])
    index["index_hash"] = stable_hash(index)
    write_json(args.output_root / "index.json", index)
    return index


def main() -> int:
    args = _arguments()
    try:
        result = render(args)
    except Exception as exc:
        print(f"CGB reference render failed: {type(exc).__name__}: {exc}")
        return 1
    print(
        f"CGB reference render {'PASS' if result['determinism_check'] != 'FAIL' else 'FAIL'}: cases={result['case_count']} renders={result['render_count']} "
        f"determinism={result['determinism_check']} source_mutations={result['source_mutation_count']} "
        f"config_hash={result['render_config_hash']}"
    )
    return 0 if result["determinism_check"] != "FAIL" and result["source_mutation_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
