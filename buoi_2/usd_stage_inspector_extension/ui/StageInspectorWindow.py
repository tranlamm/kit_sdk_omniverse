import omni.ui as ui
import omni.usd
from pxr import Usd
from ..model.PrimRow import PrimRow
from .BaseWindow import BaseWindow
from .PrimPropertyWindow import PrimPropertyWindow
import carb.events

class StageInspectorWindow(BaseWindow):
    def __init__(self, title="StageInspectorWindow"):
        super().__init__(title=title, width=850, height=600, visible=True)

        self.__init_variable__()
        self.__add_event__()

        with self._window.frame:
            with ui.VStack(style={"padding": 6}, spacing=6):
                ui.Button("Reload All", clicked_fn=self.reload_all, width=50, height=50)

                with ui.HStack(height=40, spacing=10):
                    ui.Label("Name:")
                    self._input_name = ui.StringField(width=150)
                    ui.Label("Type:")
                    self._input_type = ui.StringField(width=150)

                    ui.Button("Apply Filter", clicked_fn=self._on_apply_filter)
                    ui.Button("Clear Filter", clicked_fn=self.reload_all)

                with ui.ScrollingFrame(
                    horizontal_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_AS_NEEDED,
                    vertical_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_AS_NEEDED
                ):
                    self._content = ui.Frame()
                    self._content.set_build_fn(self.build_content)

        self.reload_all()
    
    def __init_variable__(self):
        # cache: path → list children PrimRow
        self._cache = {}

        # List root prim
        self._rows = []

        # For filter
        self._filter_name = ""
        self._filter_type = ""
        self._cur_selected_path = ""

    def __add_event__(self):
        self._sub = self.__get_context__().get_stage_event_stream().create_subscription_to_pop(
            self._on_stage_event, 
            name="MySelectionSubscription"
        )
        print("Selection subscription created.")
    
    # ---------------------- LOAD UI ----------------------
    def reload_all(self):
        self._cache.clear()
        self._rows.clear()
        self._filter_name = ""
        self._filter_type = ""
        self._cur_selected_path = ""
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
        
        with self._content:
            with ui.VStack(style={"min_width": 600}):
                if self._filter_name or self._filter_type:
                    for prim in stage.Traverse():
                        name = prim.GetName()
                        type_name = prim.GetTypeName()
                        path = prim.GetPath().pathString
                        color = 0xFFCCCCCC if prim.IsActive() else 0xFF777777

                        # Apply name filter
                        if self._filter_name:
                            if self._filter_name not in name:
                                continue

                        # Apply type filter
                        if self._filter_type:
                            if type_name != self._filter_type:
                                continue

                        # UI row
                        with ui.HStack():
                            ui.Label(f"{path} - ({name} - {type_name})", style={"color": color}, tooltip=path)
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
                    return

                rows_to_process = []
                for r in self._rows:
                    rows_to_process.append( (r, 0) )  # (PrimRow, indent_level)

                while rows_to_process:
                    row, indent = rows_to_process.pop(0)
                    indent_px = indent * 18
                    color = 0xFFCCCCCC if row.is_active else 0xFF777777
                    color = 0xFF0000FF if row.path == self._cur_selected_path else color

                    with ui.HStack(height=26, style={"background_color": 0xFF333333, "border_radius": 3, "min_width": 1000}, spacing=4):
                        if indent_px > 0:
                            ui.Spacer(width=indent_px)

                        ui.Label(f"{row.path} - ({row.name} - {row.type})", style={"color": color}, tooltip=row.path)
                        ui.Spacer()

                        symbol = ">" if row.expanded else "^"
                        ui.Button(symbol, width=22, clicked_fn=lambda r=row: self._toggle_expand(r))
                        ui.Spacer(width=4)

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
    def _toggle_expand(self, row: PrimRow):
        row.expanded = not row.expanded
        if row.expanded:
            self._load_children(row)
        self._content.rebuild()

    def _on_apply_filter(self):
        self._filter_name = self._input_name.model.get_value_as_string()
        self._filter_type = self._input_type.model.get_value_as_string()
        self._content.rebuild()

    # ----------------------- Window -----------------------
    def _open_prim_window(self, path):
        PrimPropertyWindow(path)

    # ----------------------- Event -----------------------
    def _on_stage_event(self, event: carb.events.IEvent):
        if event.type == int(omni.usd.StageEventType.SELECTION_CHANGED):
            self._on_selection_changed()

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
        def expand_to_path(rows):
            for row in rows:
                if row.path == prim_path:
                    self._cur_selected_path = prim_path
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