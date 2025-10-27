# name=AKAI APC mini Proto New Navigation
# url=https://www.akaipro.com/apc-mini

import device
import channels
import playlist
import patterns
import mixer 
import plugins
import transport
import general

import math
import time
import inspect

# DEBUG SETTINGS - choose which functions you want to receive console feedback from
DEBUG = {
    'OnProjectLoad': False,
    'OnRefresh': True,
    'OnMidiMsg' : True,
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

# APC mini LED colors (velocity values for Note On messages)
LED_OFF = 0
LED_GREEN = 1
LED_GREEN_BLINK = 2
LED_RED = 3
LED_RED_BLINK = 4
LED_YELLOW = 5
LED_YELLOW_BLINK = 6

# Change state button
BT_STATE = 87  # Note 87 - navigate through states

# State system
STATES = ["DEFAULT","PATTERNS", "PLUGINS", "PLACEHOLDER"]

# Play / Stop buttons
BT_PLAY = 88  # Note 88 -> Above BT_STOP
BT_STOP = 89  # Note 89 -> "Stop All Clips" label
# PLAYING
playing = 0
playing_his = 0

# Arrow buttons
BT_UP = 64 # Note 64 - up
BT_DOWN = 65 # Note 65 - down
BT_LEFT = 66  # Note 66 - left
BT_RIGHT = 67  # Note 67 - right

# Fader Ctrl Buttons
BT_VOL = 68
BT_PAN = 69
BT_SEND = 70
BT_DEVICE = 71

FADER_MODES = ["VOLUME", "PAN", "SEND", "DEVICE"]

# Pads - for in range() use 
PAD_START = 0
PAD_END = 63
PAD_PATTERN_GRID_START = 16 # Pattern mode use a reduced grid (8x6) to make room for the navigator tab (last row of the pad grid)
PAD_PATTERN_GRID_END = 63
PAD_PATTERN_SEPARATOR_START = 8 # this row (note 8 to 15) separates the pattern grid to the navigation tabs row
PAD_PATTERN_SEPARATOR_END = 15
PAD_PAGE_NAVIGATION_START = 0 # navigation row
PAD_PAGE_NAVIGATION_END = 7 

# Grid Dimensions
PAD_GRID_SIZE_X = 8
PATTERN_GRID_SIZE_Y = 6 # Pattern mode use a reduced grid (8x6) to make room for the navigator tab (last row of the pad grid)

# Faders (midi CC messages)
FADER_0 = 48
FADER_1 = 49
FADER_2 = 50
FADER_3 = 51
FADER_4 = 52
FADER_5 = 53
FADER_6 = 54
FADER_7 = 55
FADER_MASTER = 56

FADER_OFFSET = 48
N_FADERS = 8

# Flags (OnRefresh function parameter)
ONREFRESH_FLAGS = [
    "HW_Dirty_Mixer_Sel",
    "HW_Dirty_Mixer_Display",
    "HW_Dirty_Mixer_Controls",
    "HW_Dirty_Mixer_Controls",
    "HW_Dirty_RemoteLinks",
    "HW_Dirty_FocusedWindow",
    "HW_Dirty_Performance",
    "HW_Dirty_LEDs",
    "HW_Dirty_RemoteLinkValues",
    "HW_Dirty_Patterns",
    "HW_Dirty_Tracks",
    "HW_Dirty_ControlValues",
    "HW_Dirty_Colors",
    "HW_Dirty_Names",
    "HW_Dirty_ChannelRackGroup",
    "HW_ChannelEvent"
]

# LIST OF FLAGS (FOR REFERENCE)
"""
HW_Dirty_Mixer_Sel 	1 	mixer selection changed
HW_Dirty_Mixer_Display 	2 	mixer display changed
HW_Dirty_Mixer_Controls 	4 	mixer controls changed
HW_Dirty_RemoteLinks 	16 	remote links (linked controls) has been added/removed
HW_Dirty_FocusedWindow 	32 	channel selection changed
HW_Dirty_Performance 	64 	performance layout changed
HW_Dirty_LEDs 	256 	various changes in FL which require update of controller leds
update status leds (play/stop/record/active window/.....) on this flag
HW_Dirty_RemoteLinkValues 	512 	remote link (linked controls) value is changed
HW_Dirty_Patterns 	1024 	pattern changes
HW_Dirty_Tracks 	2048 	track changes
HW_Dirty_ControlValues 	4096 	plugin cotrol value changes
HW_Dirty_Colors 	8192 	plugin colors changes
HW_Dirty_Names 	16384 	plugin names changes
HW_Dirty_ChannelRackGroup 	32768 	Channel rack group changes
HW_ChannelEvent 	65536 	channel changes"""

# flag values from actions related to editing plugins (from empirical tests)
FLAGS_PLUGINS = (
    17703,
    'HW_Dirty_Colors',
    'HW_Dirty_Names'
)

MAX_PLUGINS_PER_TRACK = 10
#Grid matrix
pattern_length = PAD_GRID_SIZE_X*2
grid_data = []

# Global state tracker
current_state_index = 0

n_channels = 0

plugins_pads_v_ofst = 0

current_fader_mode_index = 0 #volume

# Tempo and rhythm
BEATS_PER_PAGE = int((1/4) * PAD_GRID_SIZE_X) # is this a constant? can a beat have any sub division other than beat/4 
timebase = 0
time_signature = 0
tempo = 0
n_beats = 0
bar_cnt = 0 # counter used when playing is on (see function OnUpdateBeatIndicator())
beat_cnt = 0 # counter used when playing is on (see function OnUpdateBeatIndicator())
on_beat = False # (see function OnUpdateBeatIndicator())

# follow playindex position on pad grid while playing
# (this is the default behaviour until user pushes either a pattern pad or a navigation tab)
pattern_follow_playindex = True

# Plugins
tracks_data = {} #all the plugins data are stored here - track by track
n_tracks = 16
plugin_view = False #a plugin_view happens when the controller is displaying a SUBMENU from a certain State. So far the only plugin_view available is the plugins parameters control
selected_plugin = [] # currently selected plugin [track_idx,slot_idx]

# Navigation ( mode Patterns uses navigation tab, Tracks and Plugin_Pars use up and down buttons )
navigation = {
    "PATTERNS": { # implemented
        "current_page" : 0,
        "pages" : 0
    },
    "TRACKS": { # to be implemented
        "current_page" : 0,
        "pages" : 0
    }, 
    "PLUGIN_PARS": { # to be implemented
        "current_page" : 0,
        "pages" : 0
    }
}

#EVENTS
def OnInit():
    """Called when script is loaded"""
    init()
    print('AKAI APC mini initialized')
    print(f'Current State: {STATES[current_state_index]}')

def OnDeInit():
    """Called when script is unloaded"""
    print('AKAI APC mini State Navigator deinitialized')
    # Turn off all LEDs
    for note in range(PAD_START, PAD_END + 1):
        device.midiOutMsg(144, 0, note, LED_OFF)
    for note in range(BT_UP, BT_DEVICE + 1):
        device.midiOutMsg(144, 0, note, LED_OFF)

def OnProjectLoad(status):
    """Called when a project is loading/loaded""" 
    global current_state_index,n_channels,n_tracks, beat_cnt, bar_cnt
    if status == 100: #project succesfully loaded
        init()
        print('AKAI APC mini re-initialized')
        print(f'Current State: {STATES[current_state_index]}')

def OnRefresh(flag):
    """Called when something changed that the script might want to respond to"""
    global current_state_index, playing, playing_his, n_channels, n_tracks,beat_cnt, bar_cnt, pattern_follow_playindex
    debug_print(f' - flag: {flag}')
    
    current_state = STATES[current_state_index]
    
    # find the flags (each flag is a value which is a power of 2)
    n = flag
    found_flags = []
    for i in range(len(ONREFRESH_FLAGS)-1,-1,-1):
        exp = math.pow(2,i)
        if n - exp >= 0:
            debug_print(f"found flag: {exp} = {ONREFRESH_FLAGS[i]}")
            found_flags.append(ONREFRESH_FLAGS[i])
            n -= exp

    #check time signature
    getTimeSignature()

    #check n_channels
    n_channels = channels.channelCount()

    #check n_tracks
    n_tracks = mixer.trackCount() 

    #check if a pattern has been modified
    if "HW_Dirty_Patterns" in found_flags or "HW_Dirty_Tracks" in found_flags:
        debug_print("found flag HW_Dirty_Patterns or HW_Dirty_Tracks")
        #debug_print(f'current state index: {current_state_index}')
        patterns__get_data()
        if current_state == "PATTERNS":
            debug_print("Updating All Pads")
            patterns__update_pads("all")           

    #check if playing
    playing = transport.isPlaying()
    if playing_his != playing:
        debug_print(f'PLAYING IS NOW {playing}')
        playing_his = playing
        if playing == 0:
            beat_cnt = 0
            bar_cnt = 0
            if current_state == "PATTERNS":
                pattern_follow_playindex = True
                patterns__update_pads("all")
            
    # check plugins -> different approach here, since the very same big flag packet (17703)
    #  is being called when plugins are edited
    for cond in FLAGS_PLUGINS:
        if cond == flag or cond in found_flags:
            plugins__get_data()
            if current_state == "PLUGINS" and not plugin_view:
                 plugins__display_on_pads()

def OnMidiMsg(event):
    """
    Main MIDI message handler
    event.status: MIDI status byte (144 = Note On, 176 = CC)
    event.data1: Note number
    event.data2: Velocity
    """
    global current_state_index, current_fader_mode_index
    global plugin_view, pattern_follow_playindex
    global BT_LEFT, BT_RIGHT 

    event.handled = False #set to True to stop event propagation
    
    current_state = STATES[current_state_index]

    # Note On messages
    if event.status == 144 and event.data2 > 0:
        debug_print(f'note on: {event.data1}')
        # Change state button (87) - move forward through states
        if event.data1 == BT_STATE:
            current_state_index = (current_state_index + 1) % len(STATES)
            debug_print(f'State changed to: {STATES[current_state_index]}')
            set_state()
           
        # fader control button 
        elif event.data1 in range(BT_VOL,BT_DEVICE + 1):
            current_fader_mode_index = event.data1 - BT_VOL
            ctrl_colour__update_fader(event.data1)
            debug_print(f'Fader mode changed to: {FADER_MODES[current_fader_mode_index]}')

        # playing / stop
        elif event.data1 == BT_PLAY:
            transport.start()
        
        elif event.data1 == BT_STOP:
            transport.stop()
            
        # buttons/pads whose function changes according to mode(state):
        match current_state:
            case "PATTERNS":
                if event.data1 in range(PAD_PATTERN_SEPARATOR_START + 1, PAD_END + 1):  # pattern slots
                        debug_print("pattern grid pad pushed")
                        patterns__update_single_pad(event.data1)
                        if playing:
                            pattern_follow_playindex = False
                elif event.data1 in range(PAD_PAGE_NAVIGATION_START, PAD_PAGE_NAVIGATION_END + 1): # page navigation pads
                        debug_print("page navigation pad pushed")
                        n_pages = navigation["PATTERNS"]["pages"]
                        current_page = navigation["PATTERNS"]["current_page"]
                        pushed_pad = event.data1 - PAD_PAGE_NAVIGATION_START
                        debug_print(f"pushed_pad: {pushed_pad}; n_pages: {n_pages}")
                        if pushed_pad < n_pages and pushed_pad != current_page:
                            navigation["PATTERNS"]["current_page"] = pushed_pad
                            patterns__update_pads("all")
                        if playing:
                            pattern_follow_playindex = False
            case "PLUGINS":
                if event.data1 == BT_LEFT:  # left button (66) - go back to plugins rack view 
                    debug_print("BT_LEFT pushed")
                    if plugin_view:
                        set_state()  # go back to plugin rack view
                        plugin_view = False
                elif event.data1 in range(PAD_END + 1): #plugin ra
                    if plugin_view:
                        plugins__set_par_val(event.data1)
                    else:
                        if event.data1 % PAD_GRID_SIZE_X < 5:
                            plugins__select_on_pad(event.data1)

    # CC messages
    if event.status == 176:
        cc_ch = event.data1
        cc_val = event.data2   
        if cc_ch in range(FADER_0,FADER_7+1):
            fader_mode = FADER_MODES[current_fader_mode_index]
            debug_print(f'midi channel {cc_ch}, val: {cc_val}') 
            debug_print(f'fader mode: {fader_mode}') 
            match fader_mode:
                case "VOLUME":
                    fader__update_ch_vol(cc_ch,cc_val)
                case "PAN":
                    fader__update_ch_pan(cc_ch,cc_val)
                case "SEND":
                    fader__update_ch_send(cc_ch,cc_val)
        elif cc_ch == FADER_MASTER:
            mixer.setTrackVolume(0, cc_val/127)

    event.handled = True #set to True to stop event propagation
    
def OnUpdateBeatIndicator(val):
    """
    Called when the beat indicator has changes
    - "value" can be off = 0, bar = 1 (on), beat = 2 (on)
    """
    global bar_cnt,beat_cnt,on_beat, n_beats,playing 
    debug_print(f'update Beat Indicator: {val}')

    if val != 0: #on beat
        on_beat = True
        beat_cnt +=1
        if beat_cnt > n_beats:
            bar_cnt = 0
            beat_cnt = 1;
        if val == 1: #ON BAR
            bar_cnt += 1
    else:
        on_beat = False
    debug_print(f'bar: {bar_cnt},  beat: {beat_cnt}/{n_beats}')

    # The controller is going to show the playindex while on "PATTERNS" mode
    current_state = STATES[current_state_index]
    if current_state == "PATTERNS":
        patterns__update_pads_playidx()                   

# CONTROLLER INTERFACE: SET MODE (STATE)
def set_state():
    """Update all pad LEDs and buttons based on current state"""
    # turn whole pad grid off
    reset_pads_grid()

    plugin_view = False #reset plugin_view to off if prev state was PLUGINS-> EDIT PLUGIN

    current_state = STATES[current_state_index]
    debug_print(f"Current State: {current_state}")

    match current_state:
        case "DEFAULT":           
            for note in range(BT_UP,BT_DEVICE + 1):
                device.midiOutMsg(144, 0, note, LED_OFF)
            # Set all pads to the current state's color
            for note in range(PAD_START, PAD_END + 1):
                device.midiOutMsg(144, 0, note, LED_OFF)         
        case "PATTERNS":
            patterns__get_data()
            time.sleep(0.1) 
            patterns__update_pads("all") # without wait, some pads are left turned OFF
        case "PLUGINS":
            plugins__get_data()
            time.sleep(0.1)
            plugins__display_on_pads()
        case "PLACEHOLDER":
            for note in range(BT_UP,BT_DEVICE + 1):
                device.midiOutMsg(144, 0, note, LED_OFF)
            for note in range(PAD_START, PAD_END + 1):
                device.midiOutMsg(144, 0, note, LED_YELLOW) 

# MODE 1: PATTERNS
def patterns__get_data():
    """Query FL for pattern data"""
    global n_channels, grid_data, pattern_length, n_beats
    n_channels = channels.channelCount()
    pattern_length = patterns.getPatternLength(patterns.patternNumber())
    n_beats = math.floor(pattern_length / 4) 
    #calculate how many pages we need according to the current max length of a pattern
    n_pages = math.floor(pattern_length/PAD_GRID_SIZE_X)
    current_page = navigation["PATTERNS"]["current_page"]
    if current_page >= n_pages:
        current_page = n_pages - 1
        navigation["PATTERNS"]["current_page"] = current_page
    navigation["PATTERNS"]["pages"] = n_pages

    debug_print(f"pattern length: {pattern_length}, beats: {n_beats}, pages: {n_pages}")
    debug_print(f"current page displayed: {current_page}/{n_pages}")

    # fill grid_data with the patterns from all the current project's channels
    grid_data = [[-1 for _ in range(pattern_length)] for _ in range(n_channels)]
    for channel in range(0,n_channels):
        for idx in range(0,pattern_length):
            grid_data[channel][idx] = channels.getGridBit(channel,idx)
            debug_print(f"channel: {channel}, pos: {idx}, value; {grid_data[channel][idx]}")
            if grid_data[channel][idx] == 1:
                debug_print(f'note found @ ch {channels.getChannelName(channel)}, pos {idx}')

def patterns__update_pads(mode):
    """Control led colour of pads"""
    #if mode -> patterns, we are not going to refresh navigation pads
    global navigation, grid_data   
    reset_pads_grid(mode)
    
    # draw navigation row    
    n_pages = navigation["PATTERNS"]["pages"]
    current_page = navigation["PATTERNS"]["current_page"]
    for page in range (PAD_PAGE_NAVIGATION_START, PAD_PAGE_NAVIGATION_END + 1):
        if page == current_page:
           colour = LED_YELLOW_BLINK 
        elif page < n_pages:
            colour = LED_YELLOW
        else:
            colour = LED_OFF
        device.midiOutMsg(144, 0, page, colour)        
    
    if type == "all":
    # set the right and left navigation buttons  
        if current_page < n_pages - 1:
            device.midiOutMsg(144, 0, BT_RIGHT, LED_RED)
        else:
            device.midiOutMsg(144, 0, BT_RIGHT, LED_OFF)
            
        if current_page > 0:
            device.midiOutMsg(144, 0, BT_LEFT, LED_RED)
        else:
            device.midiOutMsg(144, 0, BT_RIGHT, LED_OFF)

    x_range_min = current_page*PAD_GRID_SIZE_X
    x_range_max = x_range_min+PAD_GRID_SIZE_X 
    for row in range(0, min(PATTERN_GRID_SIZE_Y,len(grid_data)) ):
        for x in range(x_range_min, x_range_max):
            debug_print(f"get grid_data[{row}][{x}]")      
            val = grid_data[row][x]
            if val == -1:
                colour = LED_OFF
            elif val == 0:
                colour = LED_GREEN
            elif val == 1:
                colour = LED_GREEN_BLINK
            pad = x - x_range_min #position of slot in pattern -> pad in controller
            note = padgrid__xy_to_note(pad,row)

            debug_print(f'row: {row}, pad: {pad}, note: {note}, colour: {colour}')
            device.midiOutMsg(144, 0, note, colour)

def patterns__update_single_pad(note):
    """Store new data in grid_data and update FL channel"""
    global navigation, grid_data
    current_page = navigation["PATTERNS"]["current_page"]
    # turn note to row/coloumn coordinates
    idx_pad, idx_channel = pattern__note_to_data_indeces(note,current_page)
    stored_value = grid_data[idx_channel][idx_pad]
    new_value = 1 - stored_value
    grid_data[idx_channel][idx_pad] = new_value
    channels.setGridBit(idx_channel,idx_pad,new_value)  #setGridBit 	int index, int position, int value, (bool useGlobalIndex* = False) 	- 	Set grid bit value at "position" for channel at "index".
    debug_print(f'channel: {channels.getChannelName(idx_channel)}, pos: {idx_pad}, value: {new_value}')
    if new_value == 0:
        colour = LED_GREEN
    else:
        colour = LED_GREEN_BLINK
    device.midiOutMsg(144, 0, note, colour)

def patterns__update_pads_playidx(): 
    """Control led playindex when playing"""
    global navigation,bar_cnt,beat_cnt, grid_data,on_beat      
    current_page = navigation["PATTERNS"]["current_page"]
    n_pages = navigation["PATTERNS"]["pages"]
    # check which page the playindex is located right now
    page_of_beat = math.floor((beat_cnt -1)/BEATS_PER_PAGE)   
    debug_print(f"beat: {beat_cnt}. Beat is now on page {page_of_beat}. Page visualised: {current_page}")
    if not current_page == page_of_beat:
        if pattern_follow_playindex:
            navigation["PATTERNS"]["current_page"] = page_of_beat
            update_pads_mode = "all"
            current_page = page_of_beat
        elif wrap(page_of_beat - 1, 0, n_pages - 1) == current_page: #this is to prevent the script from unnecessarily update the pads which causes led blinking discontinuity
            patterns__update_pads("patterns")
    else:
        update_pads_mode = "patterns"
    if current_page == page_of_beat:
        patterns__update_pads(update_pads_mode) # "all" if new windows has been loaded due to feature follow playindex
        pos_x = ((beat_cnt - 1) % BEATS_PER_PAGE) * 4 
        if not on_beat: #add off beat offset
            pos_x += 2
        for row in range(0, PATTERN_GRID_SIZE_Y): # pattern rows & empty line
            note = ((PAD_GRID_SIZE_X-1-row) * PAD_GRID_SIZE_X) + pos_x
            pad_status = grid_data[row][current_page*PAD_GRID_SIZE_X + pos_x]
            if pad_status == 1: #LED_GREEN_BLINK
                colour = LED_RED 
            elif pad_status == 0: #LED_GREEN
                colour = LED_YELLOW 
            device.midiOutMsg(144, 0, note, colour)

#MODE 2: PLUGINS
def plugins__get_data():   
    """Query FL for plugins data (tracks, plugin slot and name, parameters name and value)"""
    global n_channels,tracks_data
    # check number of tracks
    n_tracks = mixer.trackCount() 
    # build track_data and fill with data
    tracks_data = {}
    for track in range(0,n_tracks):
        track_name = mixer.getTrackName(track)
        debug_print(f"\n\nTRACK: {track_name}\n")
        tracks_data[str(track)] = {
            "name": track_name,
            "plugins": {}
        }
        for slot in range(MAX_PLUGINS_PER_TRACK):
            if mixer.isTrackPluginValid(track, slot):
                plugin_name = plugins.getPluginName(track, slot)
                debug_print(f"\n ---- \nTrack {track}, Slot {slot}, Plugin: {plugin_name}")

                # collect parameters
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

# 
#                             
def plugins__display_on_pads():
    """Show tracks and plugins slots on the grid pad.
    Each track has a 10 slots rack, therefore two rows (5 pads each)
    are allocated to each track. NAVIGATION THROUGH ALL THE TRACKS HAS NOT BEEN
    IMPLEMENTED YET, THEREFORE ONLY THE MASTER TRACK (= track 0) AND
    INSERT 1-3 ARE DISPLAYED"""
    global tracks_data, plugins_pads_v_ofst
    reset_pads_grid("all")
    first_track = plugins_pads_v_ofst #can be only 0 at the moment (navigation not implemented yet)
    last_track = plugins_pads_v_ofst + 4
    n_tracks = len(tracks_data)
    if last_track > n_tracks:
        last_track = n_tracks

    #update led pads 
    for track in range(first_track, last_track):
        track_key = str(track)
        if track_key not in tracks_data:
            continue  # skip if missing

        plugins_dict = tracks_data[track_key]["plugins"]      
        slot_idx = 0
        for _slot_key, slot_data in plugins_dict.items():
            y = (track-first_track) * 2
            if slot_idx >= 5:
                y += 1
            x = slot_idx % 5
            note = padgrid__xy_to_note(x, y)

            if slot_data["name"] == "empty":
                if track == 0: # master track
                    device.midiOutMsg(144, 0, note, LED_RED)
                elif track % 2 == 0:
                    device.midiOutMsg(144, 0, note, LED_YELLOW)
                else:
                    device.midiOutMsg(144, 0, note, LED_GREEN)
            else:
                if track == 0: # master track
                    device.midiOutMsg(144, 0, note, LED_RED_BLINK)
                elif track % 2 == 0:
                    device.midiOutMsg(144, 0, note, LED_YELLOW_BLINK)
                else:
                    device.midiOutMsg(144, 0, note, LED_GREEN_BLINK)
            slot_idx += 1   
    debug_print("done displaying pars")

def plugins__select_on_pad(note):
    """Transition to plugin pars control after a plugin has been selected"""
    global tracks_data, plugin_view, selected_plugin
    # turn note to row/coloumn coordinates
    x,y = padgrid__note_to_xy(note)
    track = math.floor(y / 2)
    # slot differs from x as each track uses two rows, 5 pads each
    slot = x if y % 2 == 0 else x + 5
    debug_print(f"Note: {note} -> Track: {track} , Slot: {slot}")
    
    track_key = str(track)
    slot_key = str(slot)
    
    if track_key not in tracks_data: # Safeguard against missing data
        debug_print(f"Track {track_key} not found in tracks_data")
        return
    if slot_key not in tracks_data[track_key]["plugins"]: # Safeguard against missing data
        debug_print(f"Slot {slot_key} not found in track {track_key}")
        return

    selected_plugin = [track,slot]
    plugin_view = True
    reset_pads_grid()
    plugin = tracks_data[track_key]["plugins"][slot_key]
    plugin_name = plugin["name"]

    # Count number of parameters
    n_pars = len(plugin["pars"])
    debug_print(f"track: {track}, slot: {slot}, plugin: {plugin_name}, n_pars: {n_pars}")
    
    for par_idx in range(0,n_pars):
        y_par = math.floor(par_idx / PAD_GRID_SIZE_X) * 3
        x_par = (par_idx % PAD_GRID_SIZE_X)
        if y_par < PAD_GRID_SIZE_X: # temporary, need to implement navigation
            note_par = padgrid__xy_to_note(x_par, y_par)
            colour = LED_GREEN if note_par % 2 == 0 else LED_RED
            device.midiOutMsg(144, 0, note_par, colour)
    
    # turn the LEFT BUTTON led on
    reset_arrow_buttons() 
    device.midiOutMsg(144, 0, BT_LEFT, LED_RED)
   
def plugins__set_par_val(note):
    """control a plugin parameter using the pads grid"""
    global tracks_data, selected_plugin
    x,y = padgrid__note_to_xy(note)
    x += math.floor(y/3)*PAD_GRID_SIZE_X
    if y % 3 == 0:
        #these pads represents the pars, have no command mapped on them yet
        # (opening the window of the plugin? or displaying the name of the parameter somehow?)
        pass
    else:
        op = "+" if y % 3 == 1 else "-"
        track = selected_plugin[0]
        slot = selected_plugin[1]
        stored_val = tracks_data[str(track)]["plugins"][str(slot)]["pars"][str(x)]["value"]
        par_current_val = plugins.getParamValue(x, track, slot)
        if par_current_val == stored_val:
             mod = 0.05 if op == "+" else -0.05
        else: # par could be something different than a knob, requiring a bigger step
            mod = 0.1 if op == "+" else -0.1
        par_new_val = clip(par_current_val + mod,0,1)
        plugins.setParamValue(par_new_val, x, track, slot)
        tracks_data[str(track)]["plugins"][str(slot)]["pars"][str(x)]["value"] = par_new_val
        debug_print(f"Track {tracks_data[str(track)]["name"]}, "
                    f"plugin {tracks_data[str(track)]["plugins"][str(slot)]["name"]}, "
                    f"par #{x}"
                    f"par {tracks_data[str(track)]["plugins"][str(slot)]["pars"][str(x)]["name"]}, "
                    f"value -> {par_new_val}")

# FADERS
def ctrl_colour__update_fader(button):
    if button in range(BT_VOL,BT_DEVICE+1):
        debug_print(f"update fade ctrl midi note: {button}")
        for note in range(BT_VOL,BT_DEVICE+1):
            colour = LED_OFF if note != button else LED_RED
            debug_print(f'note: {note}, colour: {colour}')
            device.midiOutMsg(144, 0, note, colour)

def fader__update_ch_vol(cc_ch,cc_val):
    channel = cc_ch - FADER_OFFSET
    channels.setChannelVolume(channel, cc_val/127)

def fader__update_ch_pan(cc_ch,cc_val):
    channel = cc_ch - FADER_OFFSET
    cc_val -= 64
    channels.setChannelPan(channel, cc_val/64)

def fader__update_ch_send(cc_ch,cc_val):
    track = cc_ch - FADER_OFFSET + 1 #0 is master track
    mixer.setTrackVolume(track, cc_val/127)

# GENERIC FUNCTIONS FOR PADS
def reset_pads_grid(mode="all"):
    match mode:
        case "all":
            for note in range(PAD_START, PAD_END + 1):
                device.midiOutMsg(144, 0, note, LED_OFF)
        case "patterns":
            for note in range(PAD_PATTERN_GRID_START, PAD_PATTERN_GRID_END + 1):
                device.midiOutMsg(144, 0, note, LED_OFF)
        case "no_navigation":
            for note in range(PAD_START, PAD_PATTERN_SEPARATOR_END + 1):
                device.midiOutMsg(144, 0, note, LED_OFF)

def reset_arrow_buttons():
    for note in range(BT_UP, BT_RIGHT+1): 
        device.midiOutMsg(144, 0, note, LED_OFF)

# TIME SIGNATURE AND TEMPO
def getTimeSignature():
    global timebase, time_signature, tempo
    timebase = general.getRecPPQ()
    time_signature = general.getRecPPB()
    tempo = mixer.getCurrentTempo()/1000
    debug_print(f'tempo: {tempo}')
    debug_print(f'time signature:{timebase},  {time_signature}')

# INITIALISE/RE-INITIALISE
def init():
    global current_state_index, current_fader_mode_index , n_channels, n_tracks, beat_cnt, bar_cnt

    #check n_channels
    #n_channels = channels.channelCount() 

    #check n_tracks
    #n_tracks = mixer.trackCount() 

    # initialise to mode Default(Off)
    current_state_index = 0
    set_state()
 
    #reset beat and bar counter
    beat_cnt = 0
    bar_cnt = 0

    #check time signature
    getTimeSignature()

    # initialise fader ctrl to volume mode
    current_fader_mode_index = 0 #volume
    time.sleep(0.1) #needs wait before turning the volume button led on
    ctrl_colour__update_fader(BT_VOL)

    return True 

#CONVERSION FORMULAS
def padgrid__xy_to_note(x,y):
    return ((PAD_GRID_SIZE_X-1-y) * PAD_GRID_SIZE_X) + (x)

def padgrid__note_to_xy(note):
    global PAD_START, PAD_END, PAD_GRID_SIZE_X
    if note in range(PAD_START, PAD_END + 1):
        y = PAD_GRID_SIZE_X - 1 - math.floor(note/PAD_GRID_SIZE_X) 
        x = note % PAD_GRID_SIZE_X
        return x,y
    print(f"function padgrid__note_to_xy(). Parameter note ({note}) not in PAD_GRID range")

def pattern__note_to_data_indeces(note,page):
    global PAD_PATTERN_GRID_START, PAD_PATTERN_GRID_END, PAD_GRID_SIZE_X 
    if note in range(PAD_PATTERN_GRID_START, PAD_PATTERN_GRID_END + 1):
        y = PAD_GRID_SIZE_X - 1 - math.floor(note/PAD_GRID_SIZE_X) 
        x = PAD_GRID_SIZE_X*page + (note % PAD_GRID_SIZE_X)
        return x,y
    print(f"function pattern__note_to_data_indeces(). Parameter note ({note}) not in pattern PAD_GRID range")

def clip(value, min_value, max_value):
    return max(min_value, min(value, max_value))

def wrap(value, min_value, max_value):
    """Wrap a value to stay within [min_value, max_value)."""
    range_size = max_value - min_value
    if range_size == 0:
        return min_value
    return ((value - min_value) % range_size) + min_value

#DEBUGGING
def debug_print(message):
    # Get the name of the caller function
    caller = inspect.currentframe().f_back.f_code.co_name
    if DEBUG.get(caller, False):
        print(f"[{caller}] {message}")
