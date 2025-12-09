import omni.ext
import omni.ui as ui
from .ui import StageInspectorWindow

class UsdStageInspectorExtension(omni.ext.IExt):
    def on_startup(self, _ext_id):
        self._window = StageInspectorWindow("USD Stage Inspector")
        print("[buoi_2.usd_stage_inspector_extension] Extension startup")

    def on_shutdown(self):
        if self._window:
            self._window.destroy()
            self._window = None
        print("[buoi_2.usd_stage_inspector_extension] Extension shutdown")
