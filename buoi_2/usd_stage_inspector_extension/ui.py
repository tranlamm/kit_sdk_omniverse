import omni.ui as ui
import omni.usd
from pxr import Usd, Sdf

# --- Định nghĩa Style cho UI ---
WINDOW_STYLE = {
    "background_color": 0xFF222222,
    "color": 0xFFCCCCCC
}

HEADER_LABEL_STYLE = {
    "font_size": 18,
    "font_weight": "bold",
    "color": 0xFF00B0FF
}

BUTTON_STYLE = {
    "background_color": 0xFF444444,
    "border_radius": 4,
    "margin_height": 2,
    "margin_width": 2
}

ITEM_BUTTON_STYLE = {
    "background_color": 0xFF555555,
    "border_radius": 3,
    "padding": 2
}

COLLAPSABLE_STYLE = {
    "background_color": 0xFF333333,
    "font_weight": "semi_bold",
    "border_radius": 4
}
# --- Class chính ---

class StageInspectorWindow:
    def __init__(self, title="Hierarchical USD Inspector (No Binding)"):
        
        print("lamt3")
        self._window = ui.Window(title, width=650, height=650, visible=True, style=WINDOW_STYLE)

        with self._window.frame:
            with ui.VStack(spacing=8, style={"padding": 8}):
                print("lamt3")
                
                ui.Label("USD Stage Inspector (Manual Refresh)", height=30, style=HEADER_LABEL_STYLE)
                
                # 2. Control Panel
                with ui.HStack(spacing=6, height=35):
                    # NÚT REFRESH: ĐƯỢC BIND DUY NHẤT ĐỂ GỌI _rebuild_content
                    ui.Button("Refresh", width=80, clicked_fn=self._rebuild_content, style=BUTTON_STYLE)
                    
                    # Checkbox: Lưu widget để lấy trạng thái sau này
                    self._skip_inactive_field = ui.CheckBox(width=12) 
                    ui.Label("Skip Inactive Prims")
                    ui.Spacer()

                # 3. Filter Section
                with ui.HStack(spacing=6, height=35):
                    ui.Label("Filter by Name:", width=100)
                    # Lưu widget StringField để lấy giá trị khi Refresh
                    self._filter_name_field = ui.StringField()
                    
                with ui.HStack(spacing=6, height=35):
                    ui.Label("Filter by Type:", width=100)
                    self._filter_type_field = ui.StringField()
                    
                    self._common_types = ["Mesh", "Xform", "Camera", "Light", "Scope"]
                    self._type_combo_box = ui.ComboBox(0, *self._common_types, width=120)
                    
                ui.Separator(height=4)

                # 4. Main Scrolling Area
                with ui.ScrollingFrame(style={"border_color": 0xFF444444, "border_width": 1}):
                    self._content = ui.Frame()
                    self._content.set_build_fn(self._build_tree)
        
        # Gọi rebuild ban đầu
        self._rebuild_content()

    def _on_type_dropdown_change(self, model):
        """Cập nhật StringField và sau đó BUỘC rebuild UI."""
        selected_index = model.get_value_as_int()
        selected_type = self._common_types[selected_index]
        
        # Chuẩn hóa tên type (giữ nguyên logic)
        if selected_type == "Light": type_string = "UsdLuxLight"
        elif selected_type == "Xform": type_string = "UsdGeomXform"
        elif selected_type == "Mesh": type_string = "UsdGeomMesh"
        elif selected_type == "Camera": type_string = "UsdGeomCamera"
        elif selected_type == "Scope": type_string = "UsdGeomScope"
        else: type_string = ""
             
        # Cập nhật giá trị vào StringField và trigger rebuild
        self._filter_type_field.model.set_value(type_string)
        self._rebuild_content() # <-- GỌI REBUILD NGAY LẬP TỨC

    def _rebuild_content(self, model=None):
        """Buộc Frame xây dựng lại nội dung."""
        if self._content:
            self._content.rebuild()

    def _make_select_callback(self, path_str):
        def _select():
            ctx = omni.usd.get_context()
            # Bắt buộc phải chuyển path string về list khi dùng set_selected_prim_paths
            ctx.get_selection().set_selected_prim_paths([path_str], False)
        return _select

    def _build_tree(self):
        """Hàm xây dựng nội dung động, lấy giá trị filter trực tiếp từ widget models."""
        stage = omni.usd.get_context().get_stage()
        
        # LẤY GIÁ TRỊ FILTER TRỰC TIẾP TỪ WIDGET MODELS KHI HÀM BUILD ĐƯỢC GỌI
        filter_name = self._filter_name_field.model.get_value_as_string().lower().strip()
        filter_type = self._filter_type_field.model.get_value_as_string().lower().strip()
        skip_inactive = self._skip_inactive_field.model.get_value_as_bool()

        with self._content:
            if stage is None:
                ui.Label("⚠️ No stage open.", style={"color": 0xFFFF5555})
                return

            with ui.VStack(spacing=2):
                root_prim = stage.GetPseudoRoot()
                for prim in root_prim.GetChildren():
                    self._recursive_build_prim(prim, filter_name, filter_type, skip_inactive)
                
                ui.Spacer(height=0)

    # --- HÀM ĐỆ QUY XÂY DỰNG PRIM VÀ CON CỦA NÓ ---
    def _recursive_build_prim(self, prim: Usd.Prim, filter_name: str, filter_type: str, skip_inactive: bool):
        
        # 1. Áp dụng Bộ lọc (Logic không đổi)
        if skip_inactive and not prim.IsActive():
            return
        
        prim_type_name = prim.GetTypeName() or "<NoneType>"
        prim_path_string = prim.GetPath().pathString

        if filter_type and filter_type not in prim_type_name.lower():
            return

        if filter_name and filter_name not in prim_path_string.lower():
            return

        # 2. Định nghĩa giao diện Prim hiện tại (Logic không đổi)
        ppath = prim_path_string
        is_active = prim.IsActive()
        color_code = 0xFFCCCCCC if is_active else 0xFF888888
        header_text = f"{prim.GetName()} ({prim_type_name})"
        
        with ui.CollapsableFrame(header_text, opened=False, style=COLLAPSABLE_STYLE):
            
            with ui.VStack(spacing=1, style={"padding_left": 15}): 
                
                with ui.HStack(height=24, style={"background_color": 0xFF4D4D4D, "border_radius": 2}):
                    
                    ui.Label("•", width=10, style={"color": color_code})
                        
                    ui.Label(ppath, 
                             tooltip=f"Type: {prim_type_name}",
                             max_width=450, 
                             alignment=ui.Alignment.LEFT_CENTER, 
                             style={"padding_left": 4, "color": color_code})
                    
                    ui.Spacer()
                    
                    ui.Button("Select", width=60, 
                              clicked_fn=self._make_select_callback(ppath),
                              style=ITEM_BUTTON_STYLE)

                # 3. Gọi đệ quy cho các Prim con
                for child in prim.GetChildren():
                    self._recursive_build_prim(child, filter_name, filter_type, skip_inactive)

    def destroy(self):
        """Dọn dẹp tài nguyên."""
        if self._window:
            self._window.visible = False
            
            # Ngắt kết nối build function
            if self._content:
                self._content.set_build_fn(None)
                self._content = None
            
            # (Không cần clear_value_changed_fns cho các filter chính vì chúng không được bind)
            # Chỉ ngắt kết nối dropdown
            if self._type_combo_box:
                # Cần kiểm tra xem model còn tồn tại không trước khi clear
                if hasattr(self._type_combo_box.model, 'clear_value_changed_fns'):
                    self._type_combo_box.model.clear_value_changed_fns()
                self._type_combo_box = None
            
            self._window.destroy()
            self._window = None