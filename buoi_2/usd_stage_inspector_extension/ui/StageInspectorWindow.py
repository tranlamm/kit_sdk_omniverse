import omni.ui as ui
import omni.usd
from pxr import Usd
from ..model.PrimRow import PrimRow
from .BaseWindow import BaseWindow

class StageInspectorWindow(BaseWindow):
    def __init__(self, title="StageInspectorWindow"):
        super().__init__(title=title, width=650, height=700, visible=True)

        # cache: path → list children PrimRow
        self._cache = {}

        # List root prim
        self._rows = []

        with self._window.frame:
            with ui.VStack(style={"padding": 6}, spacing=6):
                ui.Button("Reload All", clicked_fn=self.reload_all, width=50, height=50)

                ui.Separator()

                with ui.ScrollingFrame(
                    horizontal_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_AS_NEEDED,
                    vertical_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_AS_NEEDED
                ):
                    self._content = ui.Frame()
                    self._content.set_build_fn(self.build_content)

        self.reload_all()
    
    # ---------------------- LOAD UI ----------------------
    def reload_all(self):
        self._cache.clear()
        self.reload_root_prim()

    def reload_root_prim(self):
        self._rows.clear()

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
        with self._content:
            with ui.VStack(style={"min_width": 600}):
                rows_to_process = []
                for r in self._rows:
                    rows_to_process.append( (r, 0) )  # (PrimRow, indent_level)

                while rows_to_process:
                    row, indent = rows_to_process.pop(0)
                    indent_px = indent * 18
                    color = 0xFFCCCCCC if row.is_active else 0xFF777777

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