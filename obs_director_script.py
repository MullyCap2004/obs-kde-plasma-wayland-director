#!/usr/bin/env python3
# -*- coding: utf-8 -*- # Optional: To support non-ASCII characters if needed

# =============================================================================
# Wayland OBS Director - OBS Python Script
# -----------------------------------------------------------------------------
# Author: [MullyCap2004]
# Version: 2.0 (GUI, Timer-based)
# License: [MIT License]
# Description: Automatically switches OBS scenes based on the active monitor
#              (where the mouse pointer is) under KDE Plasma Wayland.
#              Uses KWin D-Bus via qdbus6 to get the active monitor.
#              Requires qt6-tools (for qdbus6).
#              Attempts to use PyQt6 for monitor listing, falls back to kscreen.
# =============================================================================

import obspython as obs
import subprocess
import json
import time
import os
import re
import shutil # For shutil.which

# --- Global Script Variables ---
script_settings = None       # Stores OBS data settings object
monitor_scene_map = {}       # Dictionary: {output_name: scene_name}
detected_outputs = []        # List of detected monitor output names
obs_scenes = []              # List of OBS scene names
is_active = False            # Whether the switching logic is currently active
activate_on_startup = False  # Whether to activate automatically when OBS starts
last_active_output = None    # Last detected active output name
prop_group_mapping = None    # Reference to the UI property group for mappings
polling_timer = None         # Reference to the OBS timer object

# --- Constants ---
POLL_INTERVAL_MS = 350       # Polling interval in milliseconds
QDBUS6_PATH = "/usr/bin/qdbus6" # Default qdbus6 path
KSCREEN_DOCTOR_PATH = "/usr/bin/kscreen-doctor" # Default kscreen-doctor path
QDBUS6_OK = False            # Flag indicating if qdbus6 check was successful

# --- Dependency Check Functions ---
def check_command(command_name, default_path):
    """Checks if a command exists and is executable, returns the path."""
    path_to_check = default_path
    if not os.path.exists(path_to_check) or not os.access(path_to_check, os.X_OK):
        found_path = shutil.which(command_name)
        if found_path:
            print(f"OBSDirector: {command_name} found at: {found_path}")
            return found_path
        else:
            print(f"OBS Script Error: '{command_name}' command not found in {default_path} or PATH.")
            return None
    else:
        # Default path is valid
        return path_to_check

# --- D-Bus/KWin Interaction ---
def initialize_dependencies():
    """Checks for qdbus6 existence on first run."""
    global QDBUS6_PATH, QDBUS6_OK
    if hasattr(initialize_dependencies, "already_checked"): return
    initialize_dependencies.already_checked = True

    found_path = check_command('qdbus6', QDBUS6_PATH)
    if found_path:
        QDBUS6_PATH = found_path
        QDBUS6_OK = True
        print(f"OBSDirector: qdbus6 check OK ({QDBUS6_PATH})")
    else:
        QDBUS6_OK = False

def get_kwin_active_output_name_subprocess() -> str | None:
    """Calls KWin D-Bus method org.kde.KWin.activeOutputName via qdbus6."""
    if not QDBUS6_OK: return None
    try:
        cmd = [QDBUS6_PATH, 'org.kde.KWin', '/KWin', 'org.kde.KWin.activeOutputName']
        result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=0.4)
        if result.returncode == 0:
            value = result.stdout.strip()
            return value if value else None
        else: return None
    except subprocess.TimeoutExpired:
        # print("OBSDirector: Timeout calling qdbus6 for activeOutputName") # Reduce log noise
        return None
    except Exception as e:
        print(f"OBSDirector: Exception calling qdbus6 for activeOutputName: {e}")
        return None

# --- Monitor Detection ---
def detect_outputs():
    """Detects monitor output names. Tries PyQt6 first, then kscreen-doctor."""
    outputs = []
    print("OBSDirector: Detecting monitors...")

    # Attempt 1: PyQt6 (preferred)
    try:
        # print("OBSDirector: Attempting PyQt6 import...")
        from PyQt6.QtGui import QGuiApplication
        screens = QGuiApplication.screens()
        if screens:
            # print(f"OBSDirector: Detected {len(screens)} monitors via PyQt6 QScreen.")
            for screen in screens:
                name = screen.name()
                if name: outputs.append(name)
            if outputs:
                print(f"OBSDirector: Monitor names via PyQt6: {outputs}")
                return outputs
        # else: print("OBSDirector: QGuiApplication.screens() returned empty list.")
    except ImportError: print("OBSDirector: PyQt6 not available in OBS Python environment. Falling back...")
    except Exception as e: print(f"OBSDirector: Error using PyQt6 for monitor detection: {e}")

    # Attempt 2: kscreen-doctor (Fallback)
    print("OBSDirector: Falling back to kscreen-doctor...")
    global KSCREEN_DOCTOR_PATH
    ks_path = check_command('kscreen-doctor', KSCREEN_DOCTOR_PATH)
    if not ks_path: return ["Error_kscreen_missing"]
    KSCREEN_DOCTOR_PATH = ks_path # Update global path if found elsewhere

    try:
        cmd_ks = [KSCREEN_DOCTOR_PATH, '-o']
        result_ks = subprocess.run(cmd_ks, capture_output=True, text=True, check=False, timeout=3)
        if result_ks.returncode == 0 and result_ks.stdout:
            lines = result_ks.stdout.strip().split('\n')
            for line in lines:
                parts = line.split()
                if len(parts) >= 2 and parts[0] == "Output:":
                    output_name = parts[1].strip().replace(':','')
                    if output_name and output_name not in ["enabled", "disabled"]: outputs.append(output_name)
            print(f"OBSDirector: Monitor names via kscreen-doctor: {outputs}")
        else: outputs = ["Error_kscreen_failed"]
    except Exception as e: print(f"OBSDirector: Exception running kscreen-doctor: {e}"); outputs = ["Error_kscreen_exception"]

    # Final processing
    final_outputs = [o for o in outputs if not o.startswith("Error")]
    if not final_outputs:
        print("OBSDirector: No valid monitors detected. Using fallback.")
        return ["Unknown_Monitor"]
    return final_outputs

# --- OBS Script Callback Functions ---

def script_description():
    return ("<b>Wayland OBS Director (GUI Map vFinal)</b><br>"
            "Automatically switches OBS scene based on the active monitor<br>"
            "detected via KWin D-Bus (mouse pointer location).<br>"
            "Configure monitor-to-scene mapping below.<br>"
            "Requires Plasma 6 Wayland and qt6-tools (for qdbus6).<br>"
            "PyQt6 recommended for best monitor detection.")

def script_defaults(settings):
    """Sets default values for script settings."""
    print("OBSDirector: Setting defaults...")
    obs.obs_data_set_default_bool(settings, "script_enabled", False)
    obs.obs_data_set_default_bool(settings, "activate_on_startup", False) # Default is OFF
    default_mapping = """{\n    "DP-1": "Scene",\n    "HDMI-A-0": "Scene 2"\n}"""
    obs.obs_data_set_default_string(settings, "monitor_mapping", default_mapping) # Store mapping as JSON string

def script_properties():
    """Creates the user interface for the script in OBS settings."""
    print("OBSDirector: Creating properties UI...")
    initialize_dependencies() # Ensure qdbus6 check runs
    props = obs.obs_properties_create()
    global prop_group_mapping

    # --- Main Controls ---
    obs.obs_properties_add_bool(props, "script_enabled", "Enable Script")
    obs.obs_properties_add_bool(props, "activate_on_startup", "Activate on OBS Startup") # New checkbox
    obs.obs_properties_add_button(props, "refresh_button", "Refresh Monitors && Scenes", refresh_pressed)

    # --- Mapping Group ---
    prop_group_mapping = obs.obs_properties_create()
    try:
        update_mapping_properties_ui(prop_group_mapping) # Populate the group
    except Exception as e:
        print(f"OBSDirector: Error populating mapping UI initially: {e}")
        # Add error text directly to the main props if group population fails
        obs.obs_properties_add_text(props, "mapping_error", f"Error creating mapping UI: {e}", obs.OBS_TEXT_ERROR)

    obs.obs_properties_add_group(props, "monitor_mapping_group", "Monitor -> Scene Mapping", obs.OBS_GROUP_NORMAL, prop_group_mapping)

    # --- Dependency Warning ---
    if not QDBUS6_OK:
         obs.obs_properties_add_text(props, "qdbus_warning", "WARNING: 'qdbus6' not found or not executable. Script will not function.", obs.OBS_TEXT_WARNING)

    return props

def script_load(settings):
    """Called when the script is loaded."""
    print("OBSDirector: Script Loaded.")
    global script_settings, monitor_scene_map, is_active, activate_on_startup
    script_settings = settings
    initialize_dependencies() # Ensure check runs

    # Load saved mapping
    map_json = obs.obs_data_get_string(settings, "monitor_mapping")
    try:
        monitor_scene_map = json.loads(map_json)
        print(f"OBSDirector: Mapping loaded: {monitor_scene_map}")
    except json.JSONDecodeError:
        print("OBSDirector: Could not load saved mapping.")
        monitor_scene_map = {}

    # Load activation states
    is_active = obs.obs_data_get_bool(settings, "script_enabled")
    activate_on_startup = obs.obs_data_get_bool(settings, "activate_on_startup")
    print(f"OBSDirector: Initial state - Active: {is_active}, Activate on Startup: {activate_on_startup}")

    # Activate script automatically if the startup setting is checked
    if activate_on_startup:
        print("OBSDirector: Activating on startup as requested.")
        is_active = True
        # Save the activated state back to settings
        obs.obs_data_set_bool(settings, "script_enabled", True)
        # Start the timer
        start_polling_timer()
    elif is_active:
        # If not activating on startup but was previously active, start timer
        start_polling_timer()

def script_unload():
    """Called when the script is unloaded."""
    print("OBSDirector: Script Unloaded.")
    stop_polling_timer() # Ensure timer is stopped and removed

def script_save(settings):
    """Called before settings are saved (e.g., on OBS close)."""
    # Save the current mapping state
    try:
        map_json = json.dumps(monitor_scene_map)
        obs.obs_data_set_string(settings, "monitor_mapping", map_json)
    except Exception as e:
        print(f"OBSDirector: Error saving mapping on save: {e}")

def script_update(settings):
    """Called when script settings change in the UI."""
    print("OBSDirector: Settings updated...")
    global is_active, script_settings, activate_on_startup, last_active_output
    script_settings = settings

    new_active_state = obs.obs_data_get_bool(settings, "script_enabled")
    new_startup_state = obs.obs_data_get_bool(settings, "activate_on_startup")
    print(f"OBSDirector: New state - Active: {new_active_state}, Activate on Startup: {new_startup_state}")

    activate_on_startup = new_startup_state # Update global variable

    # Manage timer based on the 'Enable Script' checkbox state
    if new_active_state != is_active:
        is_active = new_active_state
        if is_active:
            start_polling_timer()
        else:
            stop_polling_timer()
            last_active_output = None # Reset last detected output when disabled


# --- Timer and Scene Switching Logic ---
def start_polling_timer():
    """Creates and starts the OBS timer if not already running."""
    global polling_timer
    if polling_timer is None:
        print(f"OBSDirector: Starting polling timer (Interval: {POLL_INTERVAL_MS}ms).")
        try:
            polling_timer = obs.timer_add(poll_kwin, POLL_INTERVAL_MS)
            if polling_timer is None:
                 print("OBSDirector: ERROR - obs.timer_add failed (returned None). Polling disabled.")
        except AttributeError:
             print("OBSDirector: ERROR - obs.timer_add function not found in obspython. Polling disabled.")
        except Exception as e:
             print(f"OBSDirector: ERROR creating timer: {e}. Polling disabled.")

def stop_polling_timer():
    """Stops and removes the OBS timer if running."""
    global polling_timer
    if polling_timer is not None:
        print("OBSDirector: Stopping polling timer.")
        try: obs.timer_remove(polling_timer)
        except AttributeError: print("OBSDirector: ERROR - obs.timer_remove function not found.")
        except Exception as e: print(f"OBSDirector: ERROR removing timer: {e}")
        finally: polling_timer = None

def poll_kwin():
    """Function called periodically by the timer."""
    global last_active_output

    # The timer handles the interval, this function executes the check
    current_output = get_kwin_active_output_name_subprocess()

    if current_output is not None and current_output != last_active_output:
        print(f"OBSDirector: Active monitor changed -> '{current_output}'")
        last_active_output = current_output

        scene_to_set = monitor_scene_map.get(current_output)
        if scene_to_set:
            print(f"OBSDirector: Switching to scene '{scene_to_set}' for monitor '{current_output}'")
            scene_source = obs.obs_get_source_by_name(scene_to_set)
            if scene_source:
                try: obs.obs_frontend_set_current_scene(scene_source)
                finally: obs.obs_source_release(scene_source) # IMPORTANT: Release source reference
            else: print(f"OBSDirector: Error - Source not found for scene '{scene_to_set}' (check exact name)")
        # else: print(f"OBSDirector: No scene mapped for '{current_output}'") # Reduce log noise

# --- UI Callbacks and Helper Functions ---
def get_obs_scene_names():
    """Gets a sorted list of scene names from OBS."""
    scenes = []; sources = obs.obs_frontend_get_scenes()
    if sources:
        try:
            for scene in sources: name = obs.obs_source_get_name(scene); scenes.append(name)
        finally: obs.source_list_release(sources) # Release the list
    # print(f"OBSDirector: Found OBS scenes: {scenes}") # Reduce noise
    return sorted(scenes)

def update_mapping_properties_ui(props_group):
    """Populates the Monitor -> Scene mapping UI group."""
    global detected_outputs, obs_scenes, monitor_scene_map, script_settings
    print("OBSDirector: Updating mapping UI...")
    detected_outputs = detect_outputs()
    obs_scenes = get_obs_scene_names()

    # TODO: Implement proper clearing of the props_group if possible/needed
    # Currently, refreshing might add duplicate entries if monitor list changes.

    if not detected_outputs or "Error" in detected_outputs[0] or "Unknown" in detected_outputs[0]:
         obs.obs_properties_add_text(props_group, "error_detect_text",
                                    f"Error detecting monitors ({detected_outputs[0]}). Check dependencies.",
                                    obs.OBS_TEXT_INFO)
         return

    print(f"OBSDirector: Creating mapping UI for monitors: {detected_outputs}")
    for output_name in detected_outputs:
        if not output_name or not re.match(r'^[\w-]+$', output_name): continue
        combo_id = f"map_{output_name}"
        combo = obs.obs_properties_add_list(props_group, combo_id, f"{output_name}:",
                                            obs.OBS_COMBO_TYPE_LIST, obs.OBS_COMBO_FORMAT_STRING)
        obs.obs_property_set_long_description(combo, f"Select scene for monitor {output_name}")
        obs.obs_property_list_add_string(combo, "<Do Nothing>", "") # Default/empty option
        for scene_name in obs_scenes: obs.obs_property_list_add_string(combo, scene_name, scene_name)
        obs.obs_property_set_modified_callback(combo, mapping_property_changed)

        # Set current value from loaded map
        if script_settings:
             current_scene = monitor_scene_map.get(output_name, "") # Default to "" if not mapped
             obs.obs_data_set_string(script_settings, combo_id, current_scene)

def mapping_property_changed(props, prop, settings):
    """Callback when a mapping ComboBox value changes."""
    global monitor_scene_map
    prop_id = obs.obs_property_name(prop) # Use correct API function
    if not prop_id or not prop_id.startswith("map_"): return True
    monitor_name = prop_id[len("map_"):]
    selected_scene = obs.obs_data_get_string(settings, prop_id)
    print(f"OBSDirector: UI Mapping Changed - '{monitor_name}' -> '{selected_scene}'")
    if not selected_scene: # "<Do Nothing>" selected
        if monitor_name in monitor_scene_map: del monitor_scene_map[monitor_name]
    else: monitor_scene_map[monitor_name] = selected_scene
    # Save immediately when changed? Or rely on script_save? Let's save here for persistence.
    try:
        map_json = json.dumps(monitor_scene_map)
        if script_settings: obs.obs_data_set_string(script_settings, "monitor_mapping", map_json)
    except Exception as e: print(f"OBSDirector: Error saving mapping in callback: {e}")
    return True # IMPORTANT: Return True

def refresh_pressed(props, prop):
    """Callback for the Refresh button."""
    print("OBSDirector: Refresh button pressed.")
    if prop_group_mapping:
        print("OBSDirector: Refreshing mapping UI...")
        # WARNING: Without proper clearing, this may add duplicate UI elements
        # if the monitor list changes between refreshes.
        update_mapping_properties_ui(prop_group_mapping)
        print("OBSDirector: Mapping UI refreshed (visual duplicates possible).")
    else: print("OBSDirector: Mapping property group reference not found.")
    return True # Return True is safer