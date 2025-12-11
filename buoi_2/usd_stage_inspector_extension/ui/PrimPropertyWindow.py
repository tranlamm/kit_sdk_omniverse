import omni.ui as ui
import omni.usd
from pxr import UsdGeom, UsdLux, UsdShade, Usd
from .BaseWindow import BaseWindow

class PrimPropertyWindow(BaseWindow):
    def __init__(self, prim_path: str):
        super().__init__(title=f"Prim Properties - {prim_path}", width=500, height=600, visible=True)
        self._prim_path = prim_path

        with self._window.frame:
            with ui.ScrollingFrame(
                horizontal_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_AS_NEEDED,
                vertical_scrollbar_policy=ui.ScrollBarPolicy.SCROLLBAR_AS_NEEDED
            ):
                self._content = ui.Frame()
                self._content.set_build_fn(self._build)

    def _build(self):
        prim = self.__get_stage__().GetPrimAtPath(self._prim_path)
        if not prim:
            with self._content:
                ui.Label("Prim not found")
            return

        with self._content:
            with ui.VStack(spacing=2, style={"padding": 8}):

                # ----- BASIC INFO -----
                ui.Label(f"Path: {prim.GetPath()}", style={"color": 0xFFEEEEEE, "font_size": 16})
                ui.Label(f"Name: {prim.GetName()}", style={"font_weight": "bold"})
                ui.Label(f"Type: {prim.GetTypeName()}")
                ui.Label(f"Active: {prim.IsActive()}")
                ui.Separator(height=2)

                # ----- ATTRIBUTES -----
                ui.Label("Attributes", style={"color": 0xFF00AACC, "font_size": 18})
                with ui.VStack(spacing=2):
                    for attr in prim.GetAttributes():
                        val = attr.Get()
                        with ui.HStack(height=22):
                            ui.Label(attr.GetName(), width=180, style={"color": 0xFFCCCCCC})
                            ui.Label(str(val), style={"color": 0xFFAAAAFF})

                ui.Separator(height=2)

                # ----- TYPE SPECIFIC -----
                prim_type = prim.GetTypeName()
                if prim_type == "Xform":
                    self._build_xform(prim)
                elif prim_type == "Mesh":
                    self._build_mesh(prim)
                elif prim_type == "Camera":
                    self._build_camera(prim)
                elif prim_type in ["DistantLight", "RectLight", "SphereLight"]:
                    self._build_light(prim)
                elif prim_type == "Material":
                    self._build_material(prim)

    # ---------- SPECIFIC BUILDERS ----------
    def _build_xform(self, prim):
        ui.Label("Xform", style={"color": 0xFFEEDD88, "font_size": 16})
        xform = UsdGeom.Xformable(prim)
        ops = xform.GetOrderedXformOps()
        if not ops:
            ui.Label("No Xform Ops")
        for op in ops:
            val = op.Get()
            ui.Label(f"{op.GetName()}: {val}")

    def _build_mesh(self, prim):
        ui.Label("Mesh", style={"color": 0xFF88DD88, "font_size": 16})
        mesh = UsdGeom.Mesh(prim)
        pts = mesh.GetPointsAttr().Get() or []
        faces = mesh.GetFaceVertexCountsAttr().Get() or []
        normals = mesh.GetNormalsAttr().Get() or []
        ui.Label(f"Points: {len(pts)}")
        ui.Label(f"Faces: {len(faces)}")
        ui.Label(f"Normals: {len(normals)}")

    def _build_camera(self, prim):
        ui.Label("Camera", style={"color": 0xFF88AAFF, "font_size": 16})
        cam = UsdGeom.Camera(prim)
        ui.Label(f"Focal Length: {cam.GetFocalLengthAttr().Get()}")
        ui.Label(f"Horizontal Aperture: {cam.GetHorizontalApertureAttr().Get()}")
        ui.Label(f"Vertical Aperture: {cam.GetVerticalApertureAttr().Get()}")
        ui.Label(f"Clipping Range: {cam.GetClippingRangeAttr().Get()}")

    def _build_light(self, prim):
        ui.Label("Light", style={"color": 0xFFFFDD88, "font_size": 16})
        for attr in prim.GetAttributes():
            val = attr.Get()
            ui.Label(f"{attr.GetName()}: {val}")

    def _build_material(self, prim):
        ui.Label("Material", style={"color": 0xFFFF88CC, "font_size": 16})
        # Get all shader inputs
        shader = UsdShade.Material(prim)
        for s in shader.GetSurfaceOutputs():
            ui.Label(f"Surface: {s.GetName()} = {s.Get()}")  