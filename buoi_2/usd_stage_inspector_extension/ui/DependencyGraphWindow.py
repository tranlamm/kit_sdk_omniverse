import os
import omni.ui as ui
import omni.usd
from pxr import UsdGeom, UsdLux, UsdShade, Usd, Sdf
from .BaseWindow import BaseWindow

USD_ASSET_ROOT = r"C:\omniverse\usd"

class DependencyGraphWindow(BaseWindow):
    def __init__(self):
        super().__init__(title="USD Dependency Graph", width=700, height=600, visible=True)

        with self._window.frame:
            with ui.ScrollingFrame(
                horizontal_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_AS_NEEDED,
                vertical_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_AS_NEEDED
            ):
                self._content = ui.Frame()
                self._content.set_build_fn(self._build)

    def _build(self):
        ctx = self.__get_context__()
        stage = self.__get_stage__()

        if not stage:
            with self._content:
                ui.Label("No active USD stage")
                return

        with self._content: 
            with ui.VStack(spacing=6):
                # 1. LAYER STACK
                ui.Label("Layer Stack", style={"font_size": 16})
                root_layer = self.__get_stage__().GetRootLayer()
                self._draw_layer_recursive(root_layer, indent=0)

                ui.Separator()
                
                ui.Label("Prim Composition", style={"font_size": 16})
                self._draw_prim_dependencies()
        
    # ----------------------------
    # LAYER DEPENDENCY GRAPH
    # ----------------------------
    def _draw_layer_recursive(self, layer: Sdf.Layer, indent: int):
        with ui.HStack():
            ui.Spacer(width=indent * 20)
            ui.Label(layer.identifier)

        for sub_path in layer.subLayerPaths:
            if os.path.isabs(sub_path):
                full_path = sub_path
            else:
                full_path = os.path.join(USD_ASSET_ROOT, sub_path)
            
            # In ra để kiểm tra (DEBUG)
            print(f"DEBUG: Trying to open layer at: {full_path}")

            sub_layer = Sdf.Layer.FindOrOpen(full_path)
            if sub_layer:
                self._draw_layer_recursive(sub_layer, indent + 1)

    # ----------------------------
    # PRIM DEPENDENCY GRAPH
    # ----------------------------
    def _has_composition_arc(self, prim: Usd.Prim) -> bool:
        return (
            bool(prim.GetInherits().GetAllDirectInherits())
            or bool(prim.GetMetadata("references"))
            or bool(prim.GetMetadata("payload"))
            or bool(prim.GetVariantSets().GetNames())
        )
    
    def _draw_prim_dependencies(self):
        with ui.VStack(spacing=4):
            for prim in self.__get_stage__().Traverse():
                if not prim.IsValid():
                    continue

                if not self._has_composition_arc(prim):
                    continue
                self._draw_prim_node(prim)

    def _draw_prim_node(self, prim: Usd.Prim):
        with ui.VStack(spacing=2):
            ui.Label(
                f"{prim.GetPath()} ({prim.GetTypeName()})",
                style={"font_size": 14}
            )
            self._draw_composition_arcs(prim, indent=1)

    # ----------------------------
    # COMPOSITION ARCS
    # ----------------------------
    def _draw_composition_arcs(self, prim: Usd.Prim, indent: int):
        # Inherits
        for path in prim.GetInherits().GetAllDirectInherits():
            self._draw_arc("Inherits", path, indent)

        # References (via metadata)
        refs = prim.GetMetadata("references")
        if refs:
            for ref in refs.GetAddedOrExplicitItems():
                self._draw_arc("Reference", ref.assetPath, indent)

        # Payloads (via metadata)
        payload = prim.GetMetadata("payload")
        if payload:
            for p in payload.GetAddedOrExplicitItems():
                self._draw_arc("Payload", p.assetPath, indent)

        # Variants
        vsets = prim.GetVariantSets()
        for name in vsets.GetNames():
            vs = vsets.GetVariantSet(name)
            sel = vs.GetVariantSelection()
            self._draw_arc(f"Variant {name}", sel, indent)

    def _draw_arc(self, label: str, value: str, indent: int):
        with ui.HStack():
            ui.Spacer(width=indent * 20)
            ui.Label(f"{label}: {value}")