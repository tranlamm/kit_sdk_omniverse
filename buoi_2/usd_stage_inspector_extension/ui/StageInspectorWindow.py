import omni.ui as ui
import omni.usd
from pxr import Usd
from ..model.PrimRow import PrimRow
from .BaseWindow import BaseWindow
from .PrimPropertyWindow import PrimPropertyWindow
import carb.events
from ..utils.FilterUtils import _match_filter
import carb.input
import json
import os
from carb.input import KeyboardEventType

class StageInspectorWindow(BaseWindow):
    def __init__(self, title="StageInspectorWindow"):
        print("Init StageInspectorWindow")
        super().__init__(title=title, width=850, height=600, visible=True)

        self.__init_variable__()
        self.__add_event__()
        self.__build_custom_ui__()

        self.reload_all()
        
    def __build_custom_ui__(self):
        self._type_list = ["", "Xform", "Mesh", "Camera", "Light", "Scope", "Material"]
        self._search_mode = ui.RadioCollection()
        self._filter_type_model = ui.SimpleIntModel(0)
        with self._window.frame:
            with ui.VStack(style={"padding": 10}, spacing=10):

                # ===================== TOP FILTER BAR =====================
                with ui.HStack(spacing=12, height=28):

                    # Reload button
                    ui.Button("Reload", width=60, height=28, clicked_fn=self.reload_all)

                    # Apply / Clear
                    ui.Button("Apply", width=60, height=28, clicked_fn=self._on_apply_filter)
                    ui.Button("Clear", width=60, height=28, clicked_fn=self.reload_all)

                    ui.Spacer(width=20)

                    # Radio Buttons (3 modes)
                    with ui.HStack():
                        ui.RadioButton(text="Normal", radio_collection=self._search_mode, height=28)
                        ui.RadioButton(text="Regex", radio_collection=self._search_mode, height=28)
                        ui.RadioButton(text="Wildcard", radio_collection=self._search_mode, height=28)

                # ===================== NAME + TYPE =====================
                with ui.HStack(spacing=10):
                    # Name
                    with ui.HStack(width=180):
                        ui.Label("Name:", width=60)
                        self._input_name = ui.StringField(width=120, height=22)

                    # Type (ComboBox)
                    with ui.HStack(width=180):
                        ui.Label("Type:", width=60)
                        self.combo_box = ui.ComboBox(
                            self._filter_type_model.as_int,
                            *self._type_list,
                            width=120,
                            height=22,
                        )
                        
                    ui.Spacer()
                    
                    with ui.HStack(spacing=8):
                        ui.Button("Select All", width=60, height=28, clicked_fn=self._select_all)
                        ui.Button("Clear All", width=60, height=28, clicked_fn=self._clear_all)
                        ui.Button("Export", width=70, height=28, clicked_fn=self._export_results)

                # ===================== PATH (FULL WIDTH) =====================
                with ui.HStack(spacing=10):
                    ui.Label("Path:", width=60)
                    self._input_path = ui.StringField(width=600, height=22)

                # ===================== ATTRIBUTE NAME + VALUE =====================
                with ui.HStack(spacing=10):
                    # Attribute Name
                    with ui.HStack(width=300):
                        ui.Label("Attr Name:", width=80)
                        self._input_attributeName = ui.StringField(width=240, height=22)

                    # Attribute Value
                    with ui.HStack(width=300):
                        ui.Label("Value:", width=60)
                        self._input_attributeValue = ui.StringField(width=240, height=22)

                    ui.Spacer()

                # ===================== SCROLLING AREA (2/3 HEIGHT) =====================
                with ui.ScrollingFrame(
                    height=400,
                    horizontal_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_AS_NEEDED,
                    vertical_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_AS_NEEDED,
                ):
                    self._content = ui.Frame()
                    self._content.set_build_fn(self.build_content)
        print("End build UI")
    
    def __init_variable__(self):
        # cache: path → list children PrimRow
        self._cache = {}

        # List root prim
        self._rows = []
        
        self._selected_prim_paths = set()

        # For filter
        self._filtered_prim_paths = []
        self._filter_name = ""
        self._filter_type = ""
        self._filter_path = ""
        self._filter_attributeName = ""
        self._filter_attributeValue = ""
        self.use_regex = False
        self.use_wildcard = False
        
        # For UI
        self._is_choose_select_all = False

    def __add_event__(self):
        self._sub = self.__get_context__().get_stage_event_stream().create_subscription_to_pop(
            self._on_stage_event, 
            name="MySelectionSubscription"
        )
        
        print("Selection subscription created.")
    
    # ---------------------- LOAD UI ----------------------
    def reload_all(self):
        self._filtered_prim_paths.clear()
        self._cache.clear()
        self._rows.clear()
        self._selected_prim_paths.clear()
        self._filter_name = ""
        self._filter_type = ""
        self._filter_path = ""
        self._filter_attributeName = ""
        self._filter_attributeValue = ""
        self.use_regex = False
        self.use_wildcard = False
        self.reload_root_prim()

    def reload_root_prim(self):
        if not self.__get_stage__():
            print("No stage loaded")
            return

        root = self.__get_stage__().GetPseudoRoot()
        level1 = root.GetChildren()
        prim_names_to_skip = ["OmniverseKit_", "Render"]

        for prim in level1:
            skip = False
            for skip_name in prim_names_to_skip:
                if prim.GetName().startswith(skip_name) or prim.GetName() == skip_name:
                    skip = True
                    break
            if skip:
                continue
            row = PrimRow(
                path=prim.GetPath().pathString,
                name=prim.GetName(),
                type=prim.GetTypeName(),
                is_active=prim.IsActive(),
            )
            self._rows.append(row)

        self._content.rebuild()

    def _load_children(self, row: PrimRow):
        if row.path in self._cache:
            row.children = self._cache[row.path]
            return

        prim = self.__get_stage__().GetPrimAtPath(row.path)
        if not prim:
            return

        children_rows = []
        for c in prim.GetChildren():
            child_row = PrimRow(
                path=c.GetPath().pathString,
                name=c.GetName(),
                type=c.GetTypeName(),
                is_active=c.IsActive()
            )
            children_rows.append(child_row)
        row.children = children_rows
        self._cache[row.path] = children_rows
    
    def build_content(self):
        stage = self.__get_stage__()
        if not stage:
            print("No USD stage loaded")
            return
        
        self._filtered_prim_paths.clear()
        with self._content:
            with ui.VStack(style={"min_width": 600}):
                if self._filter_name or self._filter_type or self._filter_path or (self._filter_attributeName and self._filter_attributeValue):
                    for prim in stage.Traverse():
                        name = prim.GetName()
                        type_name = prim.GetTypeName()
                        path = prim.GetPath().pathString
                        color = 0xFFCCCCCC if prim.IsActive() else 0xFF777777
                        # Apply name filter
                        if self._filter_name:
                            if not _match_filter(name, self._filter_name,
                                use_regex=self.use_regex,
                                use_wildcard=self.use_wildcard):
                                continue

                        # Apply type filter
                        if self._filter_type:
                            if not _match_filter(type_name, self._filter_type,
                                use_regex=self.use_regex,
                                use_wildcard=self.use_wildcard):
                                continue
                            
                        # Apply path filter
                        if self._filter_path:
                            if not _match_filter(path, self._filter_path,
                                use_regex=self.use_regex,
                                use_wildcard=self.use_wildcard):
                                continue
                            
                        # Attribute name/value filter
                        if self._filter_attributeName:
                            attr = prim.GetAttribute(self._filter_attributeName)
                            if not attr.IsValid():
                                continue

                            if self._filter_attributeValue:
                                try:
                                    val = str(attr.Get())
                                    if not _match_filter(val, self._filter_attributeValue,
                                        use_regex=self.use_regex,
                                        use_wildcard=self.use_wildcard):
                                        continue
                                except Exception:
                                    continue

                        self._filtered_prim_paths.append({
                            "path": path,
                            "type": type_name
                        })
                        # UI row
                        with ui.HStack():
                            ui.Label(f"{path} - ({name} - {type_name})", style={"color": color}, tooltip=path)
                            ui.Button(
                                "Choose", width=60, height=40,
                                clicked_fn=lambda p=path: self._on_toggle_multiple(p),
                                style={"background_color": 0xFF7777AA if path in self._selected_prim_paths else 0xFF555555}
                            )
                            ui.Button(
                                "Select", width=60, height=40,
                                clicked_fn=lambda p=path: self.__select_prim__(p),
                                style={"background_color": 0xFF555555}
                            )
                            ui.Button(
                                "Inspect", width=70, height=40,
                                clicked_fn=lambda p=path: self._open_prim_window(p),
                                style={"background_color": 0xFF7777AA}
                            )
                        ui.Spacer()
                    return

                rows_to_process = []
                for r in self._rows:
                    rows_to_process.append( (r, 0) )  # (PrimRow, indent_level)

                while rows_to_process:
                    row, indent = rows_to_process.pop(0)
                    indent_px = indent * 18
                    color = 0xFF7777AA if row.path in self._selected_prim_paths else 0xFFCCCCCC

                    with ui.HStack(height=26, style={"background_color": 0xFF333333, "border_radius": 3, "min_width": 1000}, spacing=4):
                        if indent_px > 0:
                            ui.Spacer(width=indent_px)

                        ui.Label(f"{row.path} - ({row.name} - {row.type})", style={"color": color}, tooltip=row.path)
                        ui.Spacer()

                        symbol = ">" if row.expanded else "^"
                        ui.Button(symbol, width=22, clicked_fn=lambda r=row: self._toggle_expand(r))
                        ui.Spacer(width=4)
                        
                        ui.Button(
                            "Choose", width=60,
                            clicked_fn=lambda p=row.path: self._on_toggle_multiple(p),
                            style={"background_color": 0xFF7777AA if row.path in self._selected_prim_paths else 0xFF555555}
                        )

                        ui.Button(
                            "Select", width=60,
                            clicked_fn=lambda p=row.path: self.__select_prim__(p),
                            style={"background_color": 0xFF555555}
                        )

                        ui.Button(
                            "Inspect",
                            width=70,
                            clicked_fn=lambda p=row.path: self._open_prim_window(p),
                            style={"background_color": 0xFF7777AA}
                        )

                    # Add to list if expand
                    if row.expanded and row.children:
                        for child_row in row.children:
                            rows_to_process.insert(0, (child_row, indent + 1))

    # ----------------------- UI HELPERS -----------------------
    def _select_all(self):
        self._is_choose_select_all = True
        ctx = self.__get_context__()
        ctx.get_selection().set_selected_prim_paths([], False)

        if not self._selected_prim_paths:
            return

        ctx.get_selection().set_selected_prim_paths(list(self._selected_prim_paths), False)
        
    def _clear_all(self):
        self._selected_prim_paths.clear()
        self.__get_context__().get_selection().set_selected_prim_paths([], False)
        self._content.rebuild()
         
    def _on_toggle_multiple(self, path):
        if path not in self._selected_prim_paths:
            self._selected_prim_paths.add(path)
        else:
            self._selected_prim_paths.discard(path)
        self._content.rebuild()

    def _toggle_expand(self, row: PrimRow):
        row.expanded = not row.expanded
        if row.expanded:
            self._load_children(row)
        self._content.rebuild()

    def _on_apply_filter(self):
        mode = self._search_mode.model.get_value_as_int()
        self.use_regex = (mode == 1)
        self.use_wildcard = (mode == 2)
        self._filter_name = self._input_name.model.get_value_as_string()
        self._filter_type = self._type_list[self.combo_box.model.get_item_value_model().get_value_as_int()]
        self._filter_path = self._input_path.model.get_value_as_string()
        self._filter_attributeName = self._input_attributeName.model.get_value_as_string()
        self._filter_attributeValue = self._input_attributeValue.model.get_value_as_string()
        self._content.rebuild()

    # ----------------------- Window -----------------------
    def _open_prim_window(self, path):
        PrimPropertyWindow(path)
        
    def _export_results(self):
        if not self._filtered_prim_paths:
            print("No prims to export.")
            return

        file_path = "../outputs/filtered_prims.json"
        folder = os.path.dirname(file_path)
        if folder and not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)
        
        if file_path.endswith(".json"):
            with open(file_path, "w") as f:
                json.dump(self._filtered_prim_paths, f)
        else:
            with open(file_path, "w") as f:
                for p in self._filtered_prim_paths:
                    f.write(str(p) + "\n")

        print(f"Exported filter results to {os.path.abspath(file_path)}")

    # ----------------------- Event -----------------------
    def _on_stage_event(self, event: carb.events.IEvent):
        if event.type == int(omni.usd.StageEventType.SELECTION_CHANGED):
            self._on_selection_changed()
    
    def on_keyboard_event(self, event):
        if event.input == carb.input.KeyboardInput.ENTER:
            if event.type == KeyboardEventType.KEY_RELEASE:
                self._on_apply_filter()
        
        return False

    def _on_selection_changed(self):
        # 5. Retrieve the current selection
        selection = self.__get_context__().get_selection()
        paths = selection.get_selected_prim_paths()
        self._on_stage_selection_changed(paths)

    def _on_stage_selection_changed(self, selection_paths):
        if not selection_paths:
            return

        selected_path = selection_paths[0]  # chỉ lấy prim đầu tiên
        self._scroll_to_prim(selected_path)

    def _scroll_to_prim(self, prim_path: str):
        if self._is_choose_select_all:
            self._is_choose_select_all = False
            return
        def expand_to_path(rows):
            for row in rows:
                if row.path == prim_path:
                    self._selected_prim_paths.clear()
                    self._selected_prim_paths.add(row.path)
                    return True
                
                if not row.children:
                    self._load_children(row)

                if row.children:
                    found = expand_to_path(row.children)
                    if found:
                        row.expanded = True
                        return True
            return False

        expand_to_path(self._rows)
        self._content.rebuild()