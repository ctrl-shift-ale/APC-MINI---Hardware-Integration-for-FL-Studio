# name=AKAI APC mini Proto Ale
# url=https://www.akaipro.com/apc-mini

import device
import channels
import playlist
import patterns
import mixer
import plugins
import transport
import general
import ui

import math
import time
import inspect

# ============================================================================
# DEBUG CONFIGURATION
# ============================================================================
DEBUG = {
    'OnProjectLoad': False,
    'OnRefresh': True,
    'OnMidiMsg': True,
    'OnUpdateBeatIndicator': True,
    'set_state': False,
    'patterns__update_pad': False,
    'patterns__get_data': False,
    'patterns__update_pads': False,
    'patterns__update_single_pad': False,
    'patterns__update_pads_playidx': True,
    'plugins__get_data': True,
    'plugins__update_pads': True,
    'plugins__select_on_pad': True,
    'plugins__set_par_val': True
}

# ============================================================================
# LED COLOR CONSTANTS (velocity values for Note On messages)
# ============================================================================
LED_OFF = 0
LED_GREEN = 1
LED_GREEN_BLINK = 2
LED_RED = 3
LED_RED_BLINK = 4
LED_YELLOW = 5
LED_YELLOW_BLINK = 6

# ============================================================================
# BUTTON MAPPINGS
# ============================================================================
# State navigation
BT_STATE = 87

# Transport controls
BT_PLAY = 88
BT_STOP = 89

# Arrow buttons
BT_UP = 64
BT_DOWN = 65
BT_LEFT = 66
BT_RIGHT = 67

# Fader control buttons
BT_VOL = 68
BT_PAN = 69
BT_SEND = 70
BT_DEVICE = 71

# ============================================================================
# PAD GRID CONSTANTS
# ============================================================================
PAD_START = 0
PAD_END = 63
PAD_GRID_SIZE_X = 8
PATTERN_GRID_SIZE_Y = 6  # Reduced grid (8x6) to make room for navigation

# Pattern mode pad ranges
PAD_PATTERN_GRID_START = 16
PAD_PATTERN_GRID_END = 63
PAD_PATTERN_SEPARATOR_START = 8
PAD_PATTERN_SEPARATOR_END = 15
PAD_PAGE_NAVIGATION_START = 0
PAD_PAGE_NAVIGATION_END = 7

# ============================================================================
# FADER CONSTANTS
# ============================================================================
FADER_0 = 48
FADER_MASTER = 56
FADER_OFFSET = 48
N_FADERS = 8

# ============================================================================
# CONTROLLER STATES
# ============================================================================
STATES = ["DEFAULT", "PATTERNS", "PLUGINS", "PLACEHOLDER"]
FADER_MODES = ["VOLUME", "PAN", "SEND", "DEVICE"]

# ============================================================================
# FL STUDIO REFRESH FLAGS (for reference)
# ============================================================================
ONREFRESH_FLAGS = [
    "HW_Dirty_Mixer_Sel",           # 1 - Mixer selection changed
    "HW_Dirty_Mixer_Display",       # 2 - Mixer display changed
    "HW_Dirty_Mixer_Controls",      # 4 - Mixer controls changed
    "HW_Dirty_Mixer_Controls",      # 8 - (duplicate)
    "HW_Dirty_RemoteLinks",         # 16 - Remote links added/removed
    "HW_Dirty_FocusedWindow",       # 32 - Channel selection changed
    "HW_Dirty_Performance",         # 64 - Performance layout changed
    "HW_Dirty_LEDs",                # 256 - LED updates required
    "HW_Dirty_RemoteLinkValues",    # 512 - Remote link value changed
    "HW_Dirty_Patterns",            # 1024 - Pattern changes
    "HW_Dirty_Tracks",              # 2048 - Track changes
    "HW_Dirty_ControlValues",       # 4096 - Plugin control value changes
    "HW_Dirty_Colors",              # 8192 - Plugin colors changes
    "HW_Dirty_Names",               # 16384 - Plugin names changes
    "HW_Dirty_ChannelRackGroup",    # 32768 - Channel rack group changes
    "HW_ChannelEvent"               # 65536 - Channel changes
]

# Plugin-related flags (from empirical testing)
FLAGS_PLUGINS = (17703, 'HW_Dirty_Colors', 'HW_Dirty_Names')

# ============================================================================
# GLOBAL STATE VARIABLES
# ============================================================================
current_state_index = 0
current_fader_mode_index = 0

# Playback state
playing = 0
playing_his = 0

# Timing
BEATS_PER_PAGE = int((1/4) * PAD_GRID_SIZE_X)
bar_cnt = 0
beat_cnt = 0
on_beat = False

# Pattern data
pattern_length = PAD_GRID_SIZE_X * 2
grid_data = []
pattern_follow_playindex = True

# Plugin data
MAX_PLUGINS_PER_TRACK = 10
tracks_data = {}
plugins_pads_v_ofst = 0
plugin_view = False
selected_plugin = []

# Navigation state
navigation = {
    "PATTERNS": {"current_page": 0, "pages": 0},
    "TRACKS": {"current_page": 0, "pages": 0},
    "PLUGIN_PARS": {"current_page": 0, "pages": 0}
}

# ============================================================================
# EVENT HANDLERS
# ============================================================================

def OnInit():
    """Called when script is loaded."""
    init()
    print('AKAI APC mini initialized')
    print(f'Current State: {STATES[current_state_index]}')


def OnDeInit():
    """Called when script is unloaded. Turns off all LEDs."""
    print('AKAI APC mini deinitialized')
    
    # Turn off all pad LEDs
    for note in range(PAD_START, PAD_END + 1):
        device.midiOutMsg(144, 0, note, LED_OFF)
    
    # Turn off all button LEDs
    for note in range(BT_UP, BT_DEVICE + 1):
        device.midiOutMsg(144, 0, note, LED_OFF)


def OnProjectLoad(status):
    """Called when a project is loading/loaded."""
    global beat_cnt, bar_cnt
    
    if status == 100:  # Project successfully loaded
        init()
        beat_cnt = 0
        bar_cnt = 0
        print('AKAI APC mini re-initialized')
        print(f'Current State: {STATES[current_state_index]}')


def OnRefresh(flag):
    """Called when something changed that the script might want to respond to."""
    global playing, playing_his, beat_cnt, bar_cnt, pattern_follow_playindex
    
    debug_print(f'flag: {flag}')
    current_state = STATES[current_state_index]
    
    # Parse flags (each flag is a power of 2)
    found_flags = _parse_flags(flag)
    
    # Update time signature
    _update_time_signature()
    
    # Check if patterns or tracks were modified
    if "HW_Dirty_Patterns" in found_flags or "HW_Dirty_Tracks" in found_flags:
        debug_print("Pattern or track modification detected")
        patterns__get_data()
        if current_state == "PATTERNS":
            patterns__update_pads("all")
    
    # Check playback state changes
    playing = transport.isPlaying()
    if playing_his != playing:
        debug_print(f'Playback state changed: {playing}')
        playing_his = playing
        
        if not playing:
            beat_cnt = 0
            bar_cnt = 0
            if current_state == "PATTERNS":
                pattern_follow_playindex = True
                patterns__update_pads("all")
    
    # Check for plugin modifications
    if flag in FLAGS_PLUGINS or any(f in found_flags for f in FLAGS_PLUGINS):
        plugins__get_data()
        if current_state == "PLUGINS" and not plugin_view:
            plugins__display_on_pads()


def OnMidiMsg(event):
    """Main MIDI message handler."""
    global current_state_index, current_fader_mode_index
    global plugin_view, pattern_follow_playindex
    
    event.handled = False
    current_state = STATES[current_state_index]
    
    # ========================================================================
    # NOTE ON MESSAGES (Buttons and Pads)
    # ========================================================================
    if event.status == 144 and event.data2 > 0:
        debug_print(f'Note On: {event.data1}')
        
        # State change button
        if event.data1 == BT_STATE:
            current_state_index = (current_state_index + 1) % len(STATES)
            debug_print(f'State changed to: {STATES[current_state_index]}')
            set_state()
        
        # Fader mode buttons
        elif event.data1 in range(BT_VOL, BT_DEVICE + 1):
            current_fader_mode_index = event.data1 - BT_VOL
            _update_fader_button_leds(event.data1)
            debug_print(f'Fader mode: {FADER_MODES[current_fader_mode_index]}')
        
        # Transport controls
        elif event.data1 == BT_PLAY:
            transport.start()
        elif event.data1 == BT_STOP:
            transport.stop()
        
        # State-specific pad handlers
        else:
            _handle_state_specific_input(event.data1, current_state)
    
    # ========================================================================
    # CC MESSAGES (Faders)
    # ========================================================================
    elif event.status == 176:
        _handle_fader_input(event.data1, event.data2)
    
    event.handled = True


def OnUpdateBeatIndicator(val):
    """Called when the beat indicator changes (0=off, 1=bar, 2=beat)."""
    global bar_cnt, beat_cnt, on_beat
    
    debug_print(f'Beat indicator: {val}')
    
    if val != 0:  # On beat
        on_beat = True
        beat_cnt += 1
        
        n_beats = math.floor(patterns.getPatternLength(patterns.patternNumber()) / 4)
        if beat_cnt > n_beats:
            bar_cnt = 0
            beat_cnt = 1
        
        if val == 1:  # On bar
            bar_cnt += 1
    else:
        on_beat = False
    
    debug_print(f'Bar: {bar_cnt}, Beat: {beat_cnt}')
    
    # Update playback indicator in pattern mode
    if STATES[current_state_index] == "PATTERNS":
        patterns__update_pads_playidx()


# ============================================================================
# STATE MANAGEMENT
# ============================================================================

def set_state():
    """Update all pad LEDs and buttons based on current state."""
    global plugin_view
    
    reset_pads_grid()
    plugin_view = False  # Reset plugin view when changing states
    
    current_state = STATES[current_state_index]
    debug_print(f"Setting state: {current_state}")
    
    if current_state == "DEFAULT":
        _set_default_state()
    elif current_state == "PATTERNS":
        patterns__get_data()
        time.sleep(0.1)
        patterns__update_pads("all")
    elif current_state == "PLUGINS":
        plugins__get_data()
        time.sleep(0.1)
        plugins__display_on_pads()
    elif current_state == "PLACEHOLDER":
        _set_placeholder_state()


def _set_default_state():
    """Set controller to default (off) state."""
    for note in range(BT_UP, BT_DEVICE + 1):
        device.midiOutMsg(144, 0, note, LED_OFF)
    for note in range(PAD_START, PAD_END + 1):
        device.midiOutMsg(144, 0, note, LED_OFF)


def _set_placeholder_state():
    """Set controller to placeholder state (all yellow)."""
    for note in range(BT_UP, BT_DEVICE + 1):
        device.midiOutMsg(144, 0, note, LED_OFF)
    for note in range(PAD_START, PAD_END + 1):
        device.midiOutMsg(144, 0, note, LED_YELLOW)


# ============================================================================
# PATTERN MODE FUNCTIONS
# ============================================================================

def patterns__get_data():
    """Query FL Studio for pattern data and populate grid_data."""
    global grid_data, pattern_length
    
    n_channels = channels.channelCount()
    pattern_length = patterns.getPatternLength(patterns.patternNumber())
    n_beats = math.floor(pattern_length / 4)
    
    # Calculate required pages
    n_pages = math.floor(pattern_length / PAD_GRID_SIZE_X)
    current_page = navigation["PATTERNS"]["current_page"]
    
    if current_page >= n_pages:
        current_page = n_pages - 1
        navigation["PATTERNS"]["current_page"] = current_page
    
    navigation["PATTERNS"]["pages"] = n_pages
    
    debug_print(f"Pattern length: {pattern_length}, beats: {n_beats}, pages: {n_pages}")
    debug_print(f"Current page: {current_page}/{n_pages}")
    
    # Build grid data matrix
    grid_data = [[-1] * pattern_length for _ in range(n_channels)]
    
    for channel in range(n_channels):
        for idx in range(pattern_length):
            grid_data[channel][idx] = channels.getGridBit(channel, idx)
            if grid_data[channel][idx] == 1:
                debug_print(f'Note @ channel {channels.getChannelName(channel)}, pos {idx}')


def patterns__update_pads(mode):
    """Update pattern pad LEDs based on current page and data."""
    reset_pads_grid(mode)
    
    current_page = navigation["PATTERNS"]["current_page"]
    n_pages = navigation["PATTERNS"]["pages"]
    
    # Draw navigation row
    for page in range(PAD_PAGE_NAVIGATION_START, PAD_PAGE_NAVIGATION_END + 1):
        if page == current_page:
            colour = LED_YELLOW_BLINK
        elif page < n_pages:
            colour = LED_YELLOW
        else:
            colour = LED_OFF
        device.midiOutMsg(144, 0, page, colour)
    
    # Update arrow buttons
    if mode == "all":
        device.midiOutMsg(144, 0, BT_RIGHT, LED_RED if current_page < n_pages - 1 else LED_OFF)
        device.midiOutMsg(144, 0, BT_LEFT, LED_RED if current_page > 0 else LED_OFF)
    
    # Draw pattern grid
    x_range_min = current_page * PAD_GRID_SIZE_X
    x_range_max = x_range_min + PAD_GRID_SIZE_X
    
    for row in range(min(PATTERN_GRID_SIZE_Y, len(grid_data))):
        for x in range(x_range_min, x_range_max):
            val = grid_data[row][x]
            
            if val == -1:
                colour = LED_OFF
            elif val == 0:
                colour = LED_GREEN
            else:  # val == 1
                colour = LED_GREEN_BLINK
            
            pad = x - x_range_min
            note = _padgrid_xy_to_note(pad, row)
            
            debug_print(f'Row: {row}, pad: {pad}, note: {note}, colour: {colour}')
            device.midiOutMsg(144, 0, note, colour)


def patterns__update_single_pad(note):
    """Toggle a single pattern pad and update FL Studio."""
    current_page = navigation["PATTERNS"]["current_page"]
    idx_pad, idx_channel = _pattern_note_to_data_indices(note, current_page)
    
    # Toggle value
    stored_value = grid_data[idx_channel][idx_pad]
    new_value = 1 - stored_value
    
    grid_data[idx_channel][idx_pad] = new_value
    channels.setGridBit(idx_channel, idx_pad, new_value)
    
    debug_print(f'Channel: {channels.getChannelName(idx_channel)}, pos: {idx_pad}, value: {new_value}')
    
    colour = LED_GREEN if new_value == 0 else LED_GREEN_BLINK
    device.midiOutMsg(144, 0, note, colour)


def patterns__update_pads_playidx():
    """Update pad LEDs to show current playback position."""
    current_page = navigation["PATTERNS"]["current_page"]
    n_pages = navigation["PATTERNS"]["pages"]
    
    # Determine which page contains the current beat
    page_of_beat = math.floor((beat_cnt - 1) / BEATS_PER_PAGE)
    debug_print(f"Beat {beat_cnt} on page {page_of_beat}, displaying page {current_page}")
    
    # Handle page switching
    update_mode = "patterns"
    if current_page != page_of_beat:
        if pattern_follow_playindex:
            navigation["PATTERNS"]["current_page"] = page_of_beat
            current_page = page_of_beat
            update_mode = "all"
        elif wrap(page_of_beat - 1, 0, n_pages - 1) == current_page:
            patterns__update_pads("patterns")
            return
    
    if current_page == page_of_beat:
        patterns__update_pads(update_mode)
        
        # Calculate playback position within current page
        pos_x = ((beat_cnt - 1) % BEATS_PER_PAGE) * 4
        if not on_beat:
            pos_x += 2
        
        # Highlight playback column
        for row in range(PATTERN_GRID_SIZE_Y):
            note = ((PAD_GRID_SIZE_X - 1 - row) * PAD_GRID_SIZE_X) + pos_x
            pad_status = grid_data[row][current_page * PAD_GRID_SIZE_X + pos_x]
            
            if pad_status == 1:
                colour = LED_RED
            elif pad_status == 0:
                colour = LED_YELLOW
            else:
                continue
            
            device.midiOutMsg(144, 0, note, colour)


# ============================================================================
# PLUGIN MODE FUNCTIONS
# ============================================================================

def plugins__get_data():
    """Query FL Studio for all plugin data across all tracks."""
    global tracks_data
    
    n_tracks = mixer.trackCount()
    tracks_data = {}
    
    for track in range(n_tracks):
        track_name = mixer.getTrackName(track)
        debug_print(f"\nTrack: {track_name}")
        
        tracks_data[str(track)] = {
            "name": track_name,
            "plugins": {}
        }
        
        for slot in range(MAX_PLUGINS_PER_TRACK):
            if mixer.isTrackPluginValid(track, slot):
                plugin_name = plugins.getPluginName(track, slot)
                debug_print(f"Track {track}, Slot {slot}, Plugin: {plugin_name}")
                
                # Collect parameters
                pars = {}
                for par in range(plugins.getParamCount(track, slot)):
                    par_name = plugins.getParamName(par, track, slot)
                    par_value = plugins.getParamValue(par, track, slot)
                    debug_print(f"Param {par}: {par_name} = {par_value}")
                    
                    pars[str(par)] = {
                        "name": par_name,
                        "value": par_value
                    }
                
                tracks_data[str(track)]["plugins"][str(slot)] = {
                    "name": plugin_name,
                    "pars": pars
                }
            else:
                # Empty slot
                tracks_data[str(track)]["plugins"][str(slot)] = {
                    "name": "empty",
                    "pars": {}
                }


def plugins__display_on_pads():
    """Display plugin rack on pad grid. Each track uses 2 rows (10 slots)."""
    reset_pads_grid("all")
    
    first_track = plugins_pads_v_ofst
    last_track = min(first_track + 4, len(tracks_data))
    
    for track in range(first_track, last_track):
        track_key = str(track)
        if track_key not in tracks_data:
            continue
        
        plugins_dict = tracks_data[track_key]["plugins"]
        slot_idx = 0
        
        for slot_data in plugins_dict.values():
            # Calculate position (2 rows per track, 5 slots per row)
            y = (track - first_track) * 2
            if slot_idx >= 5:
                y += 1
            x = slot_idx % 5
            
            note = _padgrid_xy_to_note(x, y)
            
            # Determine color based on track and slot status
            if slot_data["name"] == "empty":
                colour = LED_RED if track == 0 else (LED_YELLOW if track % 2 == 0 else LED_GREEN)
            else:
                colour = LED_RED_BLINK if track == 0 else (LED_YELLOW_BLINK if track % 2 == 0 else LED_GREEN_BLINK)
            
            device.midiOutMsg(144, 0, note, colour)
            slot_idx += 1


def plugins__select_on_pad(note):
    """Select a plugin and transition to parameter control view."""
    global plugin_view, selected_plugin
    
    x, y = _padgrid_note_to_xy(note)
    track = math.floor(y / 2)
    slot = x if y % 2 == 0 else x + 5
    
    debug_print(f"Note {note} -> Track {track}, Slot {slot}")
    
    track_key = str(track)
    slot_key = str(slot)
    
    # Validate data exists
    if track_key not in tracks_data or slot_key not in tracks_data[track_key]["plugins"]:
        debug_print(f"Invalid selection: Track {track_key}, Slot {slot_key}")
        return
    
    selected_plugin = [track, slot]
    plugin_view = True
    reset_pads_grid()
    
    plugin = tracks_data[track_key]["plugins"][slot_key]
    n_pars = len(plugin["pars"])
    
    debug_print(f"Selected: {plugin['name']}, {n_pars} parameters")
    ui.setHintMsg(f"{plugin['name']}")
    
    # Display parameter grid (3 rows per parameter: name, +, -)
    for par_idx in range(n_pars):
        y_par = math.floor(par_idx / PAD_GRID_SIZE_X) * 3
        x_par = par_idx % PAD_GRID_SIZE_X
        
        if y_par < PAD_GRID_SIZE_X:
            note_par = _padgrid_xy_to_note(x_par, y_par)
            colour = LED_GREEN if note_par % 2 == 0 else LED_RED
            device.midiOutMsg(144, 0, note_par, colour)
    
    # Enable left button to exit plugin view
    reset_arrow_buttons()
    device.midiOutMsg(144, 0, BT_LEFT, LED_RED)


def plugins__set_par_val(note):
    """Adjust plugin parameter value using pad grid."""
    x, y = _padgrid_note_to_xy(note)
    par_idx = x + math.floor(y / 3) * PAD_GRID_SIZE_X
    
    if y % 3 == 0:
        # Parameter name row (no action currently)
        return
    
    # Increment (+) or decrement (-) parameter
    op = "+" if y % 3 == 1 else "-"
    track, slot = selected_plugin
    
    stored_val = tracks_data[str(track)]["plugins"][str(slot)]["pars"][str(par_idx)]["value"]
    current_val = plugins.getParamValue(par_idx, track, slot)
    
    # Determine step size
    if current_val == stored_val:
        mod = 0.05 if op == "+" else -0.05
    else:
        mod = 0.1 if op == "+" else -0.1
    
    new_val = clip(current_val + mod, 0, 1)
    plugins.setParamValue(new_val, par_idx, track, slot)
    tracks_data[str(track)]["plugins"][str(slot)]["pars"][str(par_idx)]["value"] = new_val
    
    ui.setHintMsg(f"{tracks_data[str(track)]['plugins'][str(slot)]['pars'][str(par_idx)]['name']}")
    debug_print(f"Track {tracks_data[str(track)]['name']}, "
                f"Plugin {tracks_data[str(track)]['plugins'][str(slot)]['name']}, "
                f"Param {tracks_data[str(track)]['plugins'][str(slot)]['pars'][str(par_idx)]['name']}, "
                f"Value: {new_val}")


# ============================================================================
# FADER FUNCTIONS
# ============================================================================

def _update_fader_button_leds(active_button):
    """Update fader mode button LEDs (only active button lit)."""
    if active_button in range(BT_VOL, BT_DEVICE + 1):
        debug_print(f"Updating fader control LED: {active_button}")
        for note in range(BT_VOL, BT_DEVICE + 1):
            colour = LED_RED if note == active_button else LED_OFF
            device.midiOutMsg(144, 0, note, colour)


def _handle_fader_input(cc_ch, cc_val):
    """Route fader input to appropriate handler based on current mode."""
    fader_mode = FADER_MODES[current_fader_mode_index]
    debug_print(f'Fader {cc_ch}, value: {cc_val}, mode: {fader_mode}')
    
    if cc_ch in range(FADER_0, FADER_0 + N_FADERS):
        if fader_mode == "VOLUME":
            _fader_set_channel_volume(cc_ch, cc_val)
        elif fader_mode == "PAN":
            _fader_set_channel_pan(cc_ch, cc_val)
        elif fader_mode == "SEND":
            _fader_set_track_volume(cc_ch, cc_val)
    elif cc_ch == FADER_MASTER:
        mixer.setTrackVolume(0, cc_val / 127)


def _fader_set_channel_volume(cc_ch, cc_val):
    """Set channel volume from fader input."""
    channel = cc_ch - FADER_OFFSET
    channels.setChannelVolume(channel, cc_val / 127)


def _fader_set_channel_pan(cc_ch, cc_val):
    """Set channel pan from fader input."""
    channel = cc_ch - FADER_OFFSET
    pan_val = (cc_val - 64) / 64
    channels.setChannelPan(channel, pan_val)


def _fader_set_track_volume(cc_ch, cc_val):
    """Set track volume from fader input."""
    track = cc_ch - FADER_OFFSET + 1  # 0 is master track
    mixer.setTrackVolume(track, cc_val / 127)


# ============================================================================
# INPUT ROUTING HELPERS
# ============================================================================

def _handle_state_specific_input(note, current_state):
    """Route pad/button input based on current state."""
    global pattern_follow_playindex, plugin_view
    
    if current_state == "PATTERNS":
        if note in range(PAD_PATTERN_SEPARATOR_START + 1, PAD_END + 1):
            debug_print("Pattern grid pad pressed")
            patterns__update_single_pad(note)
            if playing:
                pattern_follow_playindex = False
        
        elif note in range(PAD_PAGE_NAVIGATION_START, PAD_PAGE_NAVIGATION_END + 1):
            debug_print("Navigation pad pressed")
            _handle_pattern_page_navigation(note)
    
    elif current_state == "PLUGINS":
        if note == BT_LEFT and plugin_view:
            debug_print("Exiting plugin view")
            set_state()
            plugin_view = False
        
        elif note in range(PAD_END + 1):
            if plugin_view:
                plugins__set_par_val(note)
            elif note % PAD_GRID_SIZE_X < 5:
                plugins__select_on_pad(note)


def _handle_pattern_page_navigation(note):
    """Handle pattern page navigation pad press."""
    global pattern_follow_playindex
    
    n_pages = navigation["PATTERNS"]["pages"]
    current_page = navigation["PATTERNS"]["current_page"]
    pushed_pad = note - PAD_PAGE_NAVIGATION_START
    
    debug_print(f"Navigation pad {pushed_pad}, total pages: {n_pages}")
    
    if pushed_pad < n_pages and pushed_pad != current_page:
        navigation["PATTERNS"]["current_page"] = pushed_pad
        patterns__update_pads("all")
    
    if playing:
        pattern_follow_playindex = False


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def reset_pads_grid(mode="all"):
    """Turn off pad LEDs based on mode."""
    if mode == "all":
        for note in range(PAD_START, PAD_END + 1):
            device.midiOutMsg(144, 0, note, LED_OFF)
    elif mode == "patterns":
        for note in range(PAD_PATTERN_GRID_START, PAD_PATTERN_GRID_END + 1):
            device.midiOutMsg(144, 0, note, LED_OFF)
    elif mode == "no_navigation":
        for note in range(PAD_START, PAD_PATTERN_SEPARATOR_END + 1):
            device.midiOutMsg(144, 0, note, LED_OFF)


def reset_arrow_buttons():
    """Turn off all arrow button LEDs."""
    for note in range(BT_UP, BT_RIGHT + 1):
        device.midiOutMsg(144, 0, note, LED_OFF)


def init():
    """Initialize or re-initialize controller to default state."""
    global current_state_index, current_fader_mode_index, beat_cnt, bar_cnt
    
    # Reset to default state
    current_state_index = 0
    set_state()
    
    # Reset counters
    beat_cnt = 0
    bar_cnt = 0
    
    # Update time signature
    _update_time_signature()
    
    # Initialize fader control to volume mode
    current_fader_mode_index = 0
    time.sleep(0.1)  # Wait before turning volume button LED on
    _update_fader_button_leds(BT_VOL)
    
    return True


# ============================================================================
# COORDINATE CONVERSION FUNCTIONS
# ============================================================================

def _padgrid_xy_to_note(x, y):
    """Convert grid coordinates (x, y) to MIDI note number."""
    return ((PAD_GRID_SIZE_X - 1 - y) * PAD_GRID_SIZE_X) + x


def _padgrid_note_to_xy(note):
    """Convert MIDI note number to grid coordinates (x, y)."""
    if note not in range(PAD_START, PAD_END + 1):
        debug_print(f"Warning: note {note} not in pad grid range")
        return None, None
    
    y = PAD_GRID_SIZE_X - 1 - math.floor(note / PAD_GRID_SIZE_X)
    x = note % PAD_GRID_SIZE_X
    return x, y


def _pattern_note_to_data_indices(note, page):
    """Convert pattern pad note to grid_data indices [position, channel]."""
    if note not in range(PAD_PATTERN_GRID_START, PAD_PATTERN_GRID_END + 1):
        debug_print(f"Warning: note {note} not in pattern grid range")
        return None, None
    
    y = PAD_GRID_SIZE_X - 1 - math.floor(note / PAD_GRID_SIZE_X)
    x = PAD_GRID_SIZE_X * page + (note % PAD_GRID_SIZE_X)
    return x, y


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _parse_flags(flag):
    """Parse refresh flag into individual flag names."""
    found_flags = []
    n = flag
    
    for i in range(len(ONREFRESH_FLAGS) - 1, -1, -1):
        exp = math.pow(2, i)
        if n - exp >= 0:
            debug_print(f"Found flag: {exp} = {ONREFRESH_FLAGS[i]}")
            found_flags.append(ONREFRESH_FLAGS[i])
            n -= exp
    
    return found_flags


def _update_time_signature():
    """Query and store current time signature and tempo."""
    timebase = general.getRecPPQ()
    time_signature = general.getRecPPB()
    tempo = mixer.getCurrentTempo() / 1000
    
    debug_print(f'Tempo: {tempo}')
    debug_print(f'Time signature: {timebase}, {time_signature}')


def clip(value, min_value, max_value):
    """Clamp a value between min and max."""
    return max(min_value, min(value, max_value))


def wrap(value, min_value, max_value):
    """Wrap a value to stay within [min_value, max_value)."""
    range_size = max_value - min_value
    if range_size == 0:
        return min_value
    return ((value - min_value) % range_size) + min_value


def debug_print(message):
    """Print debug message if debug flag is enabled for calling function."""
    caller = inspect.currentframe().f_back.f_code.co_name
    if DEBUG.get(caller, False):
        print(f"[{caller}] {message}")