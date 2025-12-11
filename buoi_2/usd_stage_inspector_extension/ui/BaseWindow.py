import omni.ui as ui
import omni.usd
import omni.appwindow
import carb.input
from carb.input import KeyboardEventType

class BaseWindow:
    def __init__(self, title, width, height, visible = True):
        self._window = ui.Window(title=title, width=width, height=height, visible=visible)
        self.keyboard = omni.appwindow.get_default_app_window().get_keyboard()
        self.input = carb.input.acquire_input_interface()
        
        # Subscribe to keyboard events
        self.keyboard_sub_id = self.input.subscribe_to_keyboard_events(
            self.keyboard, self.on_keyboard_event
        )
    
    def __get_context__(self):
        return omni.usd.get_context()

    def __get_stage__(self):
        return omni.usd.get_context().get_stage() 
    
    def __select_prim__(self, path):
        ctx = omni.usd.get_context()
        ctx.get_selection().set_selected_prim_paths([path], False)

    def _on_stage_selection_changed(self, selection_paths):
        pass

    def on_keyboard_event(self, event):
        return False
    
    def __destroy__(self):
        if self._window:
            self._window.visible = False
            self._window.destroy()
            self._window = None
        print(f"Destroyed window {self.__class__.__name__}")