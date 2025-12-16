import os
import omni.ui as ui
import omni.usd
from pxr import UsdGeom, UsdLux, UsdShade, Usd, Sdf, Pcp
from .BaseWindow import BaseWindow

USD_ASSET_ROOT = r"C:\omniverse\usd"

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

        self.analyze_property_stack_V2(self.prim_path, self.attr_name, self.arc_model)

    # def collect_all_sublayers(self, layer: Sdf.Layer, result=None):
    #     if result is None:
    #         result = []

    #     for sub_path in layer.subLayerPaths:
    #         if os.path.isabs(sub_path):
    #             full_path = sub_path
    #         else:
    #             full_path = os.path.join(USD_ASSET_ROOT, sub_path)
            
    #         # In ra để kiểm tra (DEBUG)
    #         print(f"DEBUG: Trying to collect layer at: {full_path}")

    #         sub_layer = Sdf.Layer.FindOrOpen(full_path)
    #         if not sub_layer:
    #             continue

    #         if full_path in result:
    #             continue 

    #         result.append(full_path)

    #         # đệ quy
    #         self.collect_all_sublayers(sub_layer, result)

    #     return result

    # # --- Helper function để duyệt cây Pcp ---
    # def _gather_nodes(self, prim_index):
    #     """
    #     Duyệt đệ quy (DFS) để lấy tất cả PcpNodes từ PrimIndex
    #     thay vì dùng GetNodeRange() (không tồn tại trong USD mới).
    #     """
    #     nodes = []
    #     # Bắt đầu từ Root Node
    #     if prim_index.IsValid():
    #         stack = [prim_index.rootNode]
    #         while stack:
    #             node = stack.pop()
    #             nodes.append(node)
    #             # Thêm các node con vào stack để duyệt tiếp
    #             # Lưu ý: node.children trả về list các PcpNode con
    #             stack.extend(node.children)
    #     return nodes
    
    def analyze_property_stack_V2(self, prim_path: str, attr_name: str, model: PropertyStackModel):
        stage = self.__get_stage__()
        prim = stage.GetPrimAtPath(prim_path)

        if not prim or not prim.IsValid():
            model.set_data([])
            return

        attr = prim.GetAttribute(attr_name)
        if not attr or not attr.IsValid():
            model.set_data([])
            return

        prim_name = prim.GetName()

        # ------------------------------------------------------------
        # 1. Query composition arcs
        # ------------------------------------------------------------
        query = Usd.PrimCompositionQuery(prim)
        arcs = query.GetCompositionArcs()

        # ------------------------------------------------------------
        # 2. Property stack (strong → weak)
        # ------------------------------------------------------------
        prop_stack = attr.GetPropertyStack()
        items = []

        for i, spec in enumerate(prop_stack):
            layer = spec.layer
            layer_id = layer.identifier if layer else "N/A"
            class_name = self.extract_class_name_from_spec(spec)

            prefix = "[UNKNOWN]"
            found_arc = False

            # --------------------------------------------------------
            # 3. Map layer -> composition arc (THÔNG QUA TARGET NODE)
            # --------------------------------------------------------
            for arc in arcs:
                node = arc.GetTargetNode()
                if not node:
                    continue

                layer_stack = node.layerStack
                if not layer_stack or layer not in layer_stack.layers:
                    continue

                arc_type = arc.GetArcType()

                if arc_type == Pcp.ArcTypeRoot and class_name != prim_name:
                    continue

                # ---------------- ARC TYPE CLASSIFICATION ----------------

                if arc_type == Pcp.ArcTypeRoot:
                    if layer == stage.GetRootLayer():
                        prefix = "[ROOT]"
                    elif layer == stage.GetSessionLayer():
                        prefix = "[SESSION]"
                    else:
                        prefix = "[SUBLAYER]"

                elif arc_type == Pcp.ArcTypeReference:
                    prefix = "[REFERENCE]"

                elif arc_type == Pcp.ArcTypePayload:
                    prefix = "[PAYLOAD]"

                elif arc_type == Pcp.ArcTypeInherit or class_name != prim_name:
                    prefix = f"[INHERIT] - {class_name}"

                elif arc_type == Pcp.ArcTypeVariant:
                    prefix = "[VARIANT]"

                elif arc_type == Pcp.ArcTypeSpecialize:
                    prefix = "[SPECIALIZE]"

                else:
                    prefix = f"[{arc_type}]"

                found_arc = True
                break

            if not found_arc:
                prefix = "[OTHER]"

            formatted_layer_id = (
                layer_id
                .replace("file:/", "")
                .replace("/", "\\")
            )

            display_name = f"{prefix} {formatted_layer_id}"
            value = spec.default if spec.HasDefaultValue() else None

            items.append(
                PropertyStackItem(
                    layer_id=display_name,
                    value=value,
                    is_winner=(i == 0),
                )
            )

        model.set_data(items)

    # def analyze_property_stack(self, prim_path: str, attr_name: str, model: PropertyStackModel):
    #     stage = self.__get_stage__()
    #     prim = stage.GetPrimAtPath(prim_path)
    #     primName = prim.GetName()
        
    #     if not prim or not prim.IsValid():
    #         model.set_data([])
    #         return

    #     attr = prim.GetAttribute(attr_name)
    #     if not attr or not attr.IsValid():
    #         model.set_data([])
    #         return

    #     # 1. Lấy Prim Index và danh sách tất cả các Node
    #     prim_index = prim.GetPrimIndex()
    #     all_nodes = self._gather_nodes(prim_index)
        
    #     items = []
    #     prop_stack = attr.GetPropertyStack()

    #     for i, spec in enumerate(prop_stack):
    #         layer = spec.layer
    #         layer_id = layer.identifier if layer else "N/A"
    #         class_name = self.extract_class_name_from_spec(spec)
            
    #         # --- LOGIC MỚI: TÌM NODE CHỨA LAYER ---
    #         prefix = "[UNKNOWN]"
    #         found_arc = False
            
    #         # Duyệt qua các node đã thu thập để tìm xem Layer này thuộc về Node nào
    #         for node in all_nodes:
    #             # node.layerStack.layers chứa danh sách các layer (Root + Sublayers của node đó)
    #             if layer in node.layerStack.layers:
    #                 arc_type = node.arcType
                    
    #                 # --- PHÂN LOẠI PREFIX ---
                    
    #                 # 1. ROOT NODE (Local)
    #                 if arc_type == Pcp.ArcTypeRoot and class_name == primName:
    #                     if layer == stage.GetRootLayer():
    #                         prefix = "[ROOT]"
    #                     elif layer == stage.GetSessionLayer():
    #                         prefix = "[SESSION]"
    #                     else:
    #                         # Nếu thuộc Root Node nhưng không phải Root Layer -> Là Sublayer của Root
    #                         prefix = "[SUBLAYER]"

    #                 # 2. REFERENCE
    #                 elif arc_type == Pcp.ArcTypeReference:
    #                     prefix = "[REFERENCE]"
    #                     # Tùy chọn: Nếu bạn muốn biết nó là sublayer bên trong reference:
    #                     # if layer != node.layerStack.layers[0]: prefix += " [SUB]"

    #                 # 3. PAYLOAD
    #                 elif arc_type == Pcp.ArcTypePayload:
    #                     prefix = "[PAYLOAD]"

    #                 # 4. INHERIT (Class)
    #                 elif arc_type == Pcp.ArcTypeInherit or class_name != primName:
    #                     prefix = f"[INHERIT] - {class_name}"

    #                 # 5. VARIANT
    #                 elif arc_type == Pcp.ArcTypeVariant:
    #                     # Lấy thông tin Variant cụ thể từ path của node
    #                     # Path thường có dạng: ...{variantSet=variantName}...
    #                     path_str = node.path.pathString
    #                     prefix = "[VARIANT]"
    #                     # Bạn có thể dùng hàm regex cũ của bạn để parse path_str nếu muốn hiện tên variant
    #                     # v_set, v_name = self._extract_variant_info(path_str)
    #                     # if v_set: prefix = f"[VARIANT] {v_set}={v_name}"

    #                 # 6. SPECIALIZE
    #                 elif arc_type == Pcp.ArcTypeSpecialize:
    #                     prefix = "[SPECIALIZE]"

    #                 found_arc = True
    #                 break
            
    #         # Fallback nếu không tìm thấy trong Graph (hiếm gặp, có thể là dynamic generated)
    #         if not found_arc:
    #             prefix = "[OTHER]"
            
    #         # -----------------------------

    #         # Làm đẹp tên layer (bỏ file:/, đổi slash)
    #         formatted_layer_id = layer_id.replace("file:/", "").replace("/", "\\")
    #         display_name = f"{prefix} {formatted_layer_id}"
            
    #         value = spec.default if spec.HasDefaultValue() else None

    #         items.append(
    #             PropertyStackItem(
    #                 layer_id=display_name,
    #                 value=value,
    #                 is_winner=(i == 0),
    #             )
    #         )

    #     model.set_data(items)
    
    # def _extract_variant_info(self, path_str: str):
    #     if "{" not in path_str:
    #         return None, None
    #     inside = path_str.split("{", 1)[1].split("}", 1)[0]
    #     if "=" in inside:
    #         return inside.split("=", 1)
    #     return None, None
    
    def extract_class_name_from_spec(self, spec):
        """
        /CubeClass.primvars:displayColor  -> CubeClass
        """
        path_str = spec.path.pathString

        # bỏ dấu / đầu
        path_str = path_str.lstrip("/")

        # cắt phần property (.primvars:xxx)
        prim_part = path_str.split(".", 1)[0]

        return prim_part