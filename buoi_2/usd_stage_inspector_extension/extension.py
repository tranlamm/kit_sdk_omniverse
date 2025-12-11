import omni.ext
from .ui.StageInspectorWindow import StageInspectorWindow

class UsdStageInspectorExtension(omni.ext.IExt):
    def on_startup(self, _ext_id):
        print("[buoi_2.usd_stage_inspector_extension] Extension startup")
        self._window = StageInspectorWindow("USD Stage Inspector")

    def on_shutdown(self):
        print("[buoi_2.usd_stage_inspector_extension] Extension shutdown")
        if self._window:
            self._window.destroy()
            self._window = None
