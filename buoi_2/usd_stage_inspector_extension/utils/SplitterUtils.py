import os
import omni.ui as ui
import omni.usd
from pxr import UsdGeom, UsdLux, UsdShade, Usd, Sdf, Pcp
from typing import Set, Dict, List
from pathlib import Path

# ------------------------------------------------------------
# Utils
# ------------------------------------------------------------

def _depth(path: Sdf.Path) -> int:
    return path.pathString.count("/")


def is_ancestor(parent: Sdf.Path, child: Sdf.Path) -> bool:
    return child.HasPrefix(parent) and parent != child


def sort_by_depth(paths: Set[Sdf.Path]) -> List[Sdf.Path]:
    return sorted(paths, key=_depth)

def get_or_create_prim_spec(
    layer: Sdf.Layer,
    prim_path: Sdf.Path
) -> Sdf.PrimSpec:
    if not prim_path.IsAbsolutePath():
        raise ValueError(f"Path must be absolute: {prim_path}")

    # Đã tồn tại
    prim_spec = layer.GetPrimAtPath(prim_path)
    if prim_spec:
        return prim_spec

    # Ensure ancestors trước
    parent = prim_path.GetParentPath()
    if parent != Sdf.Path.absoluteRootPath:
        get_or_create_prim_spec(layer, parent)

    # Tạo prim (CÁCH DUY NHẤT NÊN DÙNG)
    return Sdf.CreatePrimInLayer(layer, prim_path)

# ------------------------------------------------------------
# Export logic
# ------------------------------------------------------------

def ensure_ancestor_prims(
    layer: Sdf.Layer,
    prim_path: Sdf.Path
):
    """
    Ensure all ancestor PrimSpecs (NOT including prim_path itself)
    exist in the layer, from top to bottom.
    """

    parent_path = prim_path.GetParentPath()
    if parent_path == Sdf.Path.absoluteRootPath:
        return

    current_parent_spec = None

    # prefixes: /World, /World/Cube, ...
    for prefix in parent_path.GetPrefixes():
        name = prefix.name

        existing = layer.GetPrimAtPath(prefix)
        if existing:
            current_parent_spec = existing
            continue

        if current_parent_spec:
            current_parent_spec = Sdf.PrimSpec(
                current_parent_spec,
                name,
                Sdf.SpecifierDef
            )
        else:
            current_parent_spec = Sdf.PrimSpec(
                layer,
                name,
                Sdf.SpecifierDef
            )

def ensure_prim(layer: Sdf.Layer, prim_path: Sdf.Path) -> Sdf.PrimSpec:
    """
    Ensure prim + all ancestor prims exist in layer.
    """
    if layer.GetPrimAtPath(prim_path):
        return layer.GetPrimAtPath(prim_path)

    parent = prim_path.GetParentPath()
    if parent and parent != Sdf.Path.absoluteRootPath:
        ensure_prim(layer, parent)

    return Sdf.PrimSpec(
        layer,
        prim_path.name,
        Sdf.SpecifierDef
    )

def get_or_create_layer(path: str) -> Sdf.Layer:
    layer = Sdf.Layer.FindOrOpen(path)
    if layer:
        return layer

    return Sdf.Layer.CreateNew(path)

def export_subtree_excluding_children(
    stage: Usd.Stage,
    prim_path: Sdf.Path,
    excluded_children: List[Sdf.Path],
    out_file: Path
):
    """
    Export prim_path subtree but REMOVE any excluded child prims
    """
    src_layer = stage.GetRootLayer()

    out_layer = get_or_create_layer(str(out_file))

    # Copy full subtree
    ensure_ancestor_prims(out_layer, prim_path)

    Sdf.CopySpec(
        src_layer,
        prim_path,
        out_layer,
        prim_path
    )

    root_spec = out_layer.GetPrimAtPath(prim_path)
    if not root_spec:
        raise RuntimeError(f"PrimSpec not found in output: {prim_path}")

    # 2️⃣ Remove excluded children SAFELY
    print(excluded_children)
    excluded_children.sort(key=lambda p: str(p), reverse=True)
    for child_path in excluded_children:
        # Safety check: Ensure this child is actually under the root prim we are editing
        if not is_ancestor(prim_path, child_path):
            continue

        # 1. Get the path of the immediate parent
        parent_path = child_path.GetParentPath()

        # 2. Get the Spec for that parent from the layer
        parent_spec = out_layer.GetPrimAtPath(parent_path)

        # 3. Check if parent exists and has the child, then delete
        if parent_spec and child_path.name in parent_spec.nameChildren:
            del parent_spec.nameChildren[child_path.name]

    out_layer.Save()

def replace_prim_with_payload(
    layer: Sdf.Layer,
    prim_path: Sdf.Path,
    asset_path: str
):
    prim_spec = get_or_create_prim_spec(layer, prim_path)

    # --------------------------------------------------
    # 1) Remove attribute specs
    # --------------------------------------------------
    for attr_spec in list(prim_spec.attributes.values()):
        prim_spec.RemoveProperty(attr_spec)

    # --------------------------------------------------
    # 2) Remove relationship specs
    # --------------------------------------------------
    for rel_spec in list(prim_spec.relationships.values()):
        prim_spec.RemoveProperty(rel_spec)

    # --------------------------------------------------
    # 3) Remove variant sets
    # --------------------------------------------------
    for vs_name in list(prim_spec.variantSets.keys()):
        prim_spec.RemoveVariantSet(vs_name)

     # --------------------------------------------------
    # 4) Clear composition arcs (Sdf-style)
    # --------------------------------------------------
    prim_spec.referenceList.ClearEdits()
    prim_spec.payloadList.ClearEdits()
    prim_spec.inheritPathList.ClearEdits()
    prim_spec.specializesList.ClearEdits()

    # --------------------------------------------------
    # 5) Remove children prims
    # --------------------------------------------------
    for child_name in list(prim_spec.nameChildren.keys()):
        del prim_spec.nameChildren[child_name]

    # --------------------------------------------------
    # 6) Add payload
    # --------------------------------------------------
    prim_spec.payloadList.Add(
        Sdf.Payload(asset_path, prim_path)
    )

# ------------------------------------------------------------
# Main API
# ------------------------------------------------------------

def split_prims_to_files(
    stage: Usd.Stage,
    prim_paths: Set[str],
    output_dir: str
):
    """
    prim_paths: set of prim path strings
        ex:
        {
            "/World/Cube",
            "/World/Cube/Car",
            "/Car/Vehicle"
        }
    """

    # Convert to Sdf.Path
    paths: Set[Sdf.Path] = {Sdf.Path(p) for p in prim_paths}

    root_layer = stage.GetRootLayer()
    base_dir = Path(root_layer.realPath).parent
    out_dir = base_dir / output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    # Sort parent -> child
    ordered_paths = sort_by_depth(paths)

    created_files: Dict[Sdf.Path, Path] = {}

    # --------------------------------------------------------
    # 1) Export files
    # --------------------------------------------------------
    for prim_path in ordered_paths:
        prim = stage.GetPrimAtPath(prim_path)
        if not prim or not prim.IsValid():
            raise RuntimeError(f"Invalid prim: {prim_path}")

        # children that must be excluded from this file
        excluded_children = [
            p for p in ordered_paths
            if is_ancestor(prim_path, p)
        ]

        file_name = prim_path.name + ".usda"
        out_file = out_dir / file_name
        created_files[prim_path] = out_file

        export_subtree_excluding_children(
            stage,
            prim_path,
            excluded_children,
            out_file
        )

    # --------------------------------------------------------
    # 2) Setup payload chain
    # --------------------------------------------------------
    for prim_path in ordered_paths:
        # find closest parent in split list
        parent = next(
            (p for p in ordered_paths
             if is_ancestor(p, prim_path)),
            None
        )

        # payload inside parent file
        if parent:
            parent_layer = Sdf.Layer.FindOrOpen(
                str(created_files[parent])
            )
            replace_prim_with_payload(
                parent_layer,
                prim_path,
                str(created_files[prim_path])
            )
            parent_layer.Save()

        # payload at root
        else:
            replace_prim_with_payload(
                root_layer,
                prim_path,
                str(created_files[prim_path])
            )

    root_layer.Save()