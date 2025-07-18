import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import urwid
import mido
from mido import Message
from config import SLIDERS, ALL_BOTH_PRESS_TOGGLE_ENABLED, ALL_BOTH_PRESS_CC_NUMBER
import time

print(mido.get_output_names())

# Mock MPR121 class for CLI
class MockMPR121:
    def __init__(self):
        self.touched_pins = [False] * 12

# Simple debouncer stub for CLI (no real debounce)
class SimpleDebouncer:
    def __init__(self, fn):
        self.fn = fn
    def update(self):
        pass
    @property
    def value(self):
        return self.fn()

# MIDI interface using mido
class MidiInterface:
    def __init__(self, port_name=None):
        self.port = mido.open_output(port_name) if port_name else mido.open_output()
    def send(self, msg):
        self.port.send(msg)

class SliderState:
    def __init__(self, config):
        self.config = config
        self.value = float(config["initial_value"])
        self.last_sent_value = config["initial_value"]
        self.both_pressed = False
        self.hold_count_down = 0
        self.hold_count_up = 0
        self.enabled = True
        self.activity_on = False
        self.last_activity_time = time.monotonic()

class SliderWidget(urwid.WidgetWrap):
    ACTIVITY_TIMEOUT = 0.5  # seconds

    def __init__(self, slider_state, midi_interface):
        self.slider_state = slider_state
        self.midi = midi_interface
        self.focused = False
        self.text_widget = urwid.Text(self._get_text())
        super().__init__(self.text_widget)

    def _get_text(self):
        s = self.slider_state
        focus_marker = ">" if self.focused else " "
        return f"{focus_marker} CC {s.config['cc_number']:2d} | Value: {int(s.value):3d} | Both: {'Y' if s.both_pressed else 'N'} | Activity: {'ON' if s.activity_on else 'OFF'}"

    def set_focus(self, focused):
        self.focused = focused
        self.text_widget.set_text(self._get_text())

    def update_display(self):
        self.text_widget.set_text(self._get_text())

    def move_up(self):
        s = self.slider_state
        if not s.enabled or s.both_pressed:
            return
        s.hold_count_up += 1
        step = (s.config["speed_initial"] if s.hold_count_up == 1 else s.config["speed"] + (s.config["accel_rate"] * s.hold_count_up))
        s.value = min(127, s.value + step)
        self._send_value()
        self.activity_ping()
        self.update_display()

    def move_down(self):
        s = self.slider_state
        if not s.enabled or s.both_pressed:
            return
        s.hold_count_down += 1
        step = (s.config["speed_initial"] if s.hold_count_down == 1 else s.config["speed"] + (s.config["accel_rate"] * s.hold_count_down))
        s.value = max(0, s.value - step)
        self._send_value()
        self.activity_ping()
        self.update_display()

    def reset_holds(self):
        s = self.slider_state
        s.hold_count_up = 0
        s.hold_count_down = 0

    def both_press(self):
        s = self.slider_state
        if not s.both_pressed and s.config["both_press_cc"] is not None:
            self.midi.send(Message('control_change', channel=0, control=s.config["both_press_cc"], value=127))
            s.both_pressed = True
            self.activity_ping()
            self.update_display()

    def both_release(self):
        s = self.slider_state
        if s.both_pressed and s.config["both_press_cc"] is not None:
            self.midi.send(Message('control_change', channel=0, control=s.config["both_press_cc"], value=0))
            s.both_pressed = False
            self.activity_ping()
            self.update_display()

    def _send_value(self):
        s = self.slider_state
        new_value = int(s.value)
        if new_value != s.last_sent_value:
            #print(f"Sending CC {s.config['cc_number']} value {new_value}")
            self.midi.send(Message('control_change', channel=0, control=s.config["cc_number"], value=new_value))
            s.last_sent_value = new_value

    def activity_ping(self):
        s = self.slider_state
        s.last_activity_time = time.monotonic()
        activity_cc = s.config.get("activity_channel_cc")
        if activity_cc is not None and not s.activity_on:
            self.midi.send(Message('control_change', channel=0, control=activity_cc, value=127))
            s.activity_on = True
            self.update_display()

    def activity_check(self):
        s = self.slider_state
        activity_cc = s.config.get("activity_channel_cc")
        # Use longer timeout if both_pressed is active
        timeout = 10.0 if s.both_pressed else self.ACTIVITY_TIMEOUT
        if activity_cc is not None and s.activity_on:
            if (time.monotonic() - s.last_activity_time) > timeout:
                self.midi.send(Message('control_change', channel=0, control=activity_cc, value=0))
                s.activity_on = False
                self.update_display()

class AllBothPressManager:
    """Simple version of AllBothPressManager for the test tool."""
    
    def __init__(self, midi_interface):
        self.midi = midi_interface
        self.enabled = ALL_BOTH_PRESS_TOGGLE_ENABLED
        self.cc_number = ALL_BOTH_PRESS_CC_NUMBER
        
        # State tracking
        self.all_both_pressed = False
        self.toggle_active = False
        self.stable_start_time = None
        self.toggle_start_time = None
        self.last_trigger_time = 0
        
        # Timing configuration (simplified for test tool)
        self.stable_time = 3.0
        self.min_duration = 10.0
        self.max_duration = 30.0
        self.cooldown = 60.0
        
        if self.enabled:
            print(f"All Both-Press Toggle enabled (CC {self.cc_number})")
        else:
            print("All Both-Press Toggle disabled")
    
    def update(self, slider_states, current_time):
        """Update the all both-press state based on current slider states."""
        if not self.enabled or not slider_states:
            return False
        
        # Check if all sliders are in both-press state
        all_both_pressed_now = all(s.both_pressed for s in slider_states if s.enabled)
        
        # State change detection
        if all_both_pressed_now != self.all_both_pressed:
            self.all_both_pressed = all_both_pressed_now
            
            if self.all_both_pressed:
                # All sliders just entered both-press state
                self.stable_start_time = current_time
                print("All sliders entered both-press state - starting stable timer")
            else:
                # At least one slider left both-press state
                self.stable_start_time = None
                print("At least one slider left both-press state - resetting stable timer")
        
        # Check if we should trigger the toggle
        if (self.all_both_pressed and 
            not self.toggle_active and 
            self.stable_start_time is not None and
            current_time - self.stable_start_time >= self.stable_time and
            current_time - self.last_trigger_time >= self.cooldown):
            
            # Trigger the toggle
            self.toggle_active = True
            self.toggle_start_time = current_time
            self.last_trigger_time = current_time
            
            # Send MIDI CC ON
            try:
                self.midi.send(Message('control_change', channel=0, control=self.cc_number, value=127))
                print(f"All Both-Press Toggle ACTIVATED (CC {self.cc_number})")
            except Exception as e:
                print(f"Failed to send All Both-Press Toggle MIDI: {e}")
            
            return True
        
        # Check if we should deactivate the toggle
        if self.toggle_active:
            toggle_duration = current_time - self.toggle_start_time
            
            # Deactivate if minimum duration reached and not all sliders are still both-pressed
            if (toggle_duration >= self.min_duration and not self.all_both_pressed) or \
               toggle_duration >= self.max_duration:
                
                self.toggle_active = False
                self.toggle_start_time = None
                
                # Send MIDI CC OFF
                try:
                    self.midi.send(Message('control_change', channel=0, control=self.cc_number, value=0))
                    print(f"All Both-Press Toggle DEACTIVATED (CC {self.cc_number}) after {toggle_duration:.1f}s")
                except Exception as e:
                    print(f"Failed to send All Both-Press Toggle MIDI: {e}")
                
                return True
        
        return False

class SliderUI:
    def __init__(self, sliders):
        self.midi = MidiInterface('MadMapper In')
        self.slider_states = [SliderState(cfg) for cfg in sliders]
        self.widgets = [SliderWidget(state, self.midi) for state in self.slider_states]
        self.all_both_press_manager = AllBothPressManager(self.midi)
        self.listbox = urwid.ListBox(urwid.SimpleFocusListWalker(self.widgets))
        self.focus_index = 0
        self.widgets[self.focus_index].set_focus(True)
        self._main_loop = None

    def unhandled_input(self, key):
        w = self.widgets[self.focus_index]
        if key in ("up", "k"):
            self._move_focus(-1)
        elif key in ("down", "j"):
            self._move_focus(1)
        elif key in ("right", "+"):
            w.move_up()
        elif key in ("left", "-"):
            w.move_down()
        elif key == " ":
            w.both_press()
        elif key == "b":
            w.both_release()
        elif key in ("q", "Q"):
            raise urwid.ExitMainLoop()
        else:
            w.reset_holds()

    def _move_focus(self, delta):
        self.widgets[self.focus_index].set_focus(False)
        self.focus_index = (self.focus_index + delta) % len(self.widgets)
        self.widgets[self.focus_index].set_focus(True)

    def main(self):
        self._main_loop = urwid.MainLoop(self.listbox, unhandled_input=self.unhandled_input)
        self._main_loop.set_alarm_in(0.1, self._periodic_activity_check)
        self._main_loop.run()

    def _periodic_activity_check(self, loop, user_data):
        current_time = time.monotonic()
        for w in self.widgets:
            w.activity_check()
        # Update all both-press manager
        self.all_both_press_manager.update(self.slider_states, current_time)
        loop.set_alarm_in(0.1, self._periodic_activity_check)

def main():
    ui = SliderUI(SLIDERS)
    ui.main()

if __name__ == "__main__":
    main() 