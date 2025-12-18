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

def sort_by_depth(paths, reverse = False) -> List[Sdf.Path]:
    return sorted(paths, key=_depth, reverse=reverse)

def to_leaf_path(path: Sdf.Path) -> Sdf.Path:
    return Sdf.Path.absoluteRootPath.AppendChild(
        path.name
    )

def remove_all_prim_spec(
    layer: Sdf.Layer,
    prim_path: Sdf.Path
):
    prim_spec = layer.GetPrimAtPath(prim_path)

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

def get_layer(path: str) -> Sdf.Layer:
    layer = Sdf.Layer.FindOrOpen(path)
    if layer:
        raise RuntimeError(f"Existed layer path: {path}")

    return Sdf.Layer.CreateNew(path)

def remap_relative_to_ancestor(
    paths: list[Sdf.Path],
    ancestor: Sdf.Path
) -> list[Sdf.Path]:
    """
    /A/B/C/D/E   relative to /A/B/C  -> /C/D/E
    """

    if not ancestor.IsPrimPath():
        raise ValueError(f"Ancestor must be prim path: {ancestor}")

    result = []

    root_name = ancestor.name
    new_root = Sdf.Path.absoluteRootPath.AppendChild(root_name)

    for p in paths:
        if not p.IsPrimPath():
            raise ValueError(f"Not a prim path: {p}")

        if not p.HasPrefix(ancestor):
            raise ValueError(f"{p} is not under {ancestor}")

        # /A/B/C/D/E  -> D/E
        rel = p.MakeRelativePath(ancestor)

        # /C + D/E
        new_path = new_root.AppendPath(rel)
        result.append(new_path)

    return result

# ------------------------------------------------------------
# Export logic
# ------------------------------------------------------------

def export_subtree_excluding_children(
    stage: Usd.Stage,
    prim_path: Sdf.Path,
    excluded_children: List[Sdf.Path],
    out_file: Path
):
    """
    Export prim_path subtree but REMOVE any excluded child prims
    """
    prim = stage.GetPrimAtPath(prim_path)
    out_layer = get_layer(str(out_file))
    new_prim_path = to_leaf_path(prim.GetPrimStack()[0].path)

    Sdf.CopySpec(
        prim.GetPrimStack()[0].layer,
        prim.GetPrimStack()[0].path,
        out_layer,
        new_prim_path
    )

    # Remove excluded children SAFELY
    excluded_children = sort_by_depth(excluded_children, True)
    relative_path_excluded_children = remap_relative_to_ancestor(excluded_children, prim_path)
    for child_path in relative_path_excluded_children:
        remove_all_prim_spec(out_layer, child_path)

    out_layer.Save()

def replace_prim_with_payload(
    layer: Sdf.Layer,
    prim_path: Sdf.Path,
    asset_path: str,
    parent_prim_path: Sdf.Path
):
    new_prim_path = to_leaf_path(prim_path)
    relative_prim_path = remap_relative_to_ancestor([prim_path], parent_prim_path)[0] if parent_prim_path != None else prim_path

    remove_all_prim_spec(layer, relative_prim_path)
    prim_spec = layer.GetPrimAtPath(relative_prim_path)
    prim_spec.payloadList.Add(
        Sdf.Payload(asset_path, new_prim_path)
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
    created_files: Dict[Sdf.Path, Path] = {}

    # Convert to Sdf.Path
    paths: Set[Sdf.Path] = {Sdf.Path(p) for p in prim_paths}

    root_layer = stage.GetRootLayer()
    base_dir = Path(root_layer.realPath).parent
    out_dir = base_dir / output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------------
    # 1) Export files
    # --------------------------------------------------------
    ordered_paths = sort_by_depth(paths)
    for prim_path in ordered_paths:
        print("Export for: " + str(prim_path))
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
        parent_list = [p for p in ordered_paths if is_ancestor(p, prim_path)]
        parent_list = sort_by_depth(parent_list, True)
        parent = next(iter(parent_list), None)

        # payload inside parent file
        if parent:
            parent_layer = Sdf.Layer.FindOrOpen(
                str(created_files[parent])
            )
            replace_prim_with_payload(
                parent_layer,
                prim_path,
                str(created_files[prim_path]),
                parent
            )
            parent_layer.Save()

        # payload at root
        else:
            prim = stage.GetPrimAtPath(prim_path)
            replace_prim_with_payload(
                prim.GetPrimStack()[0].layer,
                prim.GetPrimStack()[0].path,
                str(created_files[prim_path]),
                None
            )
            prim.GetPrimStack()[0].layer.Save()

    root_layer.Save()