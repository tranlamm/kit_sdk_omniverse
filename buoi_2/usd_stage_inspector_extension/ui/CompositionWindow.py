import os
import omni.ui as ui
import omni.usd
from pxr import UsdGeom, UsdLux, UsdShade, Usd, Sdf
from .BaseWindow import BaseWindow

class PropertyStackItem(ui.AbstractItem):
    def __init__(self, layer_id, value, is_winner=False):
        super().__init__()
        self.layer_id = layer_id
        self.value = value
        self.is_winner = is_winner

class PropertyStackModel(ui.AbstractItemModel):
    COLUMN_COUNT = 1

    def __init__(self):
        super().__init__()
        self._data = []

    def set_data(self, items):
        self._data = items
        self._item_changed(None)

    def get_item_children(self, item):
        if item is None:
            return self._data
        return []

    def get_item_value(self, item, column_id):
        return item
    
    def get_item_value_model_count(self, item):
        return self.COLUMN_COUNT

    def get_item_value_model(self, item, column_id):
        return None
    
class PropertyStackDelegate(ui.AbstractItemDelegate):
    def build_branch(self, model, item, column_id, level, expanded):
        pass

    def build_widget(self, model, item, column_id, level, expanded):
        if item is None:
            return
        
        value = model.get_item_value(item, column_id)

        style = {}
        if item.is_winner:
            style = {
                "color": 0xFFFFD700,
                "font-weight": "bold"
            }

        with ui.HStack(height=22):

            ui.Label(
                item.layer_id,
                width=ui.Percent(60),
                alignment=ui.Alignment.LEFT,
                style=style,
                elided_text=True
            )

            ui.Label(
                str(item.value),
                width=ui.Percent(30),
                alignment=ui.Alignment.LEFT,
                style=style,
                elided_text=True
            )

            ui.Label(
                "Active" if item.is_winner else "",
                width=ui.Percent(10),
                alignment=ui.Alignment.CENTER,
                style=style
            )

class CompositionWindow(BaseWindow):
    def __init__(self, prim_path, attr_name):
        self.prim_path = prim_path
        self.attr_name = attr_name
        print("Analyze: " + self.prim_path + " - " + self.attr_name)
        super().__init__(title="Composition Viewer", width=700, height=600, visible=True)
        self.arc_model = PropertyStackModel()
        self.delegate = PropertyStackDelegate()
        with self._window.frame:
            with ui.ScrollingFrame(
                horizontal_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_AS_NEEDED,
                vertical_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_AS_NEEDED
            ):
                self._content = ui.Frame()
                self._content.set_build_fn(self._build)
            
        self._content.rebuild()

    def build_property_stack_header(self):
        with ui.HStack(height=24):
            ui.Label("Layer / Source", width=ui.Percent(60), style={"font-weight": "bold"})
            ui.Label("Value", width=ui.Percent(30), style={"font-weight": "bold"})
            ui.Label("*", width=ui.Percent(10), alignment=ui.Alignment.CENTER, style={"font-weight": "bold"})

    def _build(self):
        with self._content:
            with ui.VStack():
                self.build_property_stack_header()
                ui.TreeView(
                    self.arc_model,
                    delegate=self.delegate,
                    root_visible=False,
                    header_visible=False,
                    column_count=PropertyStackModel.COLUMN_COUNT,
                    style={
                        "row_height": 22,
                        "selection_color": 0x553498DB,
                    }
                )

        self.analyze_property_stack(self.prim_path, self.attr_name, self.arc_model)

    def analyze_property_stack(self, prim_path: str, attr_name: str, model: PropertyStackModel):
        stage = self.__get_stage__()
        prim = stage.GetPrimAtPath(prim_path)

        if not prim or not prim.IsValid():
            model.set_data([])
            return

        attr = prim.GetAttribute(attr_name)
        if not attr or not attr.IsValid():
            model.set_data([])
            return

        root_layer = stage.GetRootLayer()
        sublayers = set(root_layer.subLayerPaths)

        items = []
        prop_stack = attr.GetPropertyStack()

        for i, spec in enumerate(prop_stack):
            layer = spec.layer
            layer_id = layer.identifier if layer else "N/A"
            path_str = spec.path.pathString

            prefix = ""
            display_name = ""

            # ---- VARIANT ----
            variant_set, variant_name = self._extract_variant_info(path_str)
            if variant_set:
                prefix = "[VARIANT]"
                display_name = f"{prefix} {variant_set}={variant_name} | {layer_id}"

            # ---- ROOT LAYER ----
            elif layer == root_layer:
                prefix = "[ROOT]"
                display_name = f"{prefix} {layer_id}"

            # ---- SUBLAYER ----
            elif layer_id in sublayers:
                prefix = "[SUBLAYER]"
                display_name = f"{prefix} {layer_id}"

            # ---- PAYLOAD / REFERENCE ----
            else:
                if self._layer_is_payload(prim, layer):
                    prefix = "[PAYLOAD]"
                else:
                    prefix = "[REFERENCE]"
                display_name = f"{prefix} {layer_id}"

            value = spec.default if spec.HasDefaultValue() else None

            items.append(
                PropertyStackItem(
                    layer_id=display_name,
                    value=value,
                    is_winner=(i == 0),
                )
            )

        model.set_data(items)
    
    def _extract_variant_info(self, path_str: str):
        if "{" not in path_str:
            return None, None
        inside = path_str.split("{", 1)[1].split("}", 1)[0]
        if "=" in inside:
            return inside.split("=", 1)
        return None, None
    
    def _layer_is_payload(self, prim, layer):
        for node in prim.GetPrimIndex().rootNode.children:
            if node.arcType == Usd.PrimCompositionQuery.ArcTypePayload:
                if node.layerStack and layer in node.layerStack.layers:
                    return True
        return False