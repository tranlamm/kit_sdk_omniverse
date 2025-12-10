import omni.ui as ui
import omni.usd

class BaseWindow:
    def __init__(self, title, width, height, visible = True):
        self._window = ui.Window(title=title, width=width, height=height, visible=visible)
    
    def __get_stage__(self):
        return omni.usd.get_context().get_stage() 
    
    def __select_prim__(self, path):
        ctx = omni.usd.get_context()
        ctx.get_selection().set_selected_prim_paths([path], False)
    
    def __destroy__(self):
        if self._window:
            self._window.visible = False
            self._window.destroy()
            self._window = None
        print(f"Destroyed window {self.__class__.__name__}")