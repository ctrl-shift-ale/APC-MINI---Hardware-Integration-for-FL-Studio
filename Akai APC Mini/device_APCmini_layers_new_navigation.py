# name=AKAI APC mini Proto Main
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

#SETTINGS
DEBUG = {
    'OnProjectLoad': False,
    'OnRefresh': True,
    'OnMidiMsg' : True,
    'OnUpdateBeatIndicator': False,
    'set_state': False,
    'patterns__update_pad': False,
    'patterns__get_data': False,
    'patterns__update_all_pads': False,
    'patterns__update_single_pad': False,
    'patterns__update_pads_playidx': False,
    'plugins__get_data': False,
    'plugins__update_pads': False,
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
# STATES
STATE_DEFAULT = 0
STATE_PATTERNS = 1
STATE_PLUGINS = 2
STATE_C = 3
# State system
STATES = ["DEFAULT","PATTERNS", "PLUGINS", "C"]


# Navigation buttons
BT_UP = 64 # Note 64 - navigate up
BT_DOWN = 65 # Note 65 - navigate down
BT_LEFT = 66  # Note 66 - navigate left
BT_RIGHT = 67  # Note 67 - navigate right

# Fader Ctrl Buttons
BT_VOL = 68 
BT_PAN = 69
BT_SEND = 70
BT_DEVICE = 71

FADER_MODES = ["VOLUME", "PAN", "SEND", "DEVICE"]

# Pad 
PAD_START = 0
PAD_END = 63
GRID_SIZE_X = 8
GRID_SIZE_Y = 6
PAD_GRID_START = 16
PAD_GRID_END = 63
PAD_EMPTY_ROW_START = 8
PAD_EMPTY_ROW_END = 15
PAD_PAGE_NAVIGATION_START = 0 
PAD_PAGE_NAVIGATION_END = 7 


# Faders
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
FLAGS_PLUGINS = (
    17703,
    'HW_Dirty_Colors',
    'HW_Dirty_Names'
)

DEFAULT_N_CHANNELS = 8

MAX_PLUGINS_PER_TRACK = 10
#Grid matrix
pattern_max_length = GRID_SIZE_X*2
grid_data = [[-1 for _ in range(pattern_max_length)] for _ in range(DEFAULT_N_CHANNELS)]
# Global state tracker
current_state_index = 0

patterns_pads_h_shift = 0 #beats displayed in Patterns mode ( 0 -> beat 0 to 7 ; 1 -> beat 8 to 15)
patterns_pads_h_ofst = patterns_pads_h_shift*GRID_SIZE_X
n_channels = 0

plugins_pads_v_ofst = 0

current_fader_mode_index = 0 #volume

timebase = 0
time_signature = 0
tempo = 0

playing = 0
playing_his = 0

bar_cnt = 0
beat_cnt = 0
on_beat = False
pattern_n_bars = 0

tracks_data = {}
n_tracks = 16

substate = False #a substate happens when the controller is displaying a SUBMENU from a certain State. So far the only substate available is the plugins parameters control
selected_plugin = []

navigation = {
    "PATTERNS": {
        "current page" : 0,
        "pages" : 0
    },
    "PLUGINS": {
        "current page" : 0,
        "pages" : 0
    }, 
    "PARAMETERS": {
        "current page" : 0,
        "pages" : 0
    }
}

#EVENTS
def OnInit():
    """Called when script is loaded"""
    global current_state_index, current_fader_mode_index , n_channels, n_tracks

    #check n_channels
    n_channels = channels.channelCount() 

    #check n_tracks
    n_tracks = mixer.trackCount() 

    current_state_index = 0
    current_fader_mode_index = 0 #volume
    
    set_state()
    patterns__get_data()

    if DEBUG['plugins__get_data']:
        plugins__get_data()
    #check time signature
    getTimeSignature()

    time.sleep(0.1)

    ctrl_colour__update_fader(BT_VOL)

    print('AKAI APC mini State Navigator initialized')
    debug_print(f'Starting in State: {STATES[current_state_index]}')

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
    global current_state_index,n_channels,n_tracks
    if status == 100: #project succesfully loaded

        #check n_channels
        n_channels = channels.channelCount() 

        #check n_tracks
        n_tracks = mixer.trackCount() 

        current_state_index = 0
        patterns__get_data()

def OnRefresh(flag):
    """Called when something changed that the script might want to respond to"""
    global playing, playing_his, n_channels, n_tracks
    debug_print(f'Refresh: {flag}')
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
        if current_state_index == STATE_PATTERNS:
            debug_print("Updating All Pads")
            patterns__update_all_pads()           

    #check if playing
    playing = transport.isPlaying()
    if playing_his != playing:
        debug_print(f'PLAYING IS NOW {playing}')
        playing_his = playing
        if playing == 0:
            if current_state_index == STATE_PATTERNS:
                patterns__update_all_pads()
            

    # check plugins
    for cond in FLAGS_PLUGINS:
        if cond == flag or cond in found_flags:
            plugins__get_data()
            if current_state_index == STATE_PLUGINS and not substate:
                 plugins__display_on_pads()

def OnMidiMsg(event):
    """
    Main MIDI message handler
    event.status: MIDI status byte (144 = Note On)
    event.data1: Note number
    event.data2: Velocity
    """
    global current_state_index, current_fader_mode_index, patterns_pads_h_shift, patterns_pads_h_ofst, substate

    event.handled = False
    
    current_state = STATES[current_state_index]

    # Note On messages
    if event.status == 144 and event.data2 > 0:
        debug_print(f'note on: {event.data1}')
        # Change state button (87) - move forward through states
        if event.data1 == BT_STATE:
            current_state_index = (current_state_index + 1) % len(STATES)
            debug_print(f'State changed to: {STATES[current_state_index]}')
            set_state()
           
        
        # Down button (65) - move backward through states
        #elif event.data1 == BT_DWN:
        #    current_state_index = (current_state_index - 1) % len(STATES)
        #    debug_print(f'State changed to: {STATES[current_state_index]}')
        #    set_state()
        #    event.handled = True
        
        # left button (66) - move left through grid
        elif event.data1 == BT_LEFT:
            match current_state:
                case "PATTERNS":
                    if patterns_pads_h_shift == 1:
                        patterns_pads_h_shift = 0
                        patterns_pads_h_ofst = 0
                        patterns__update_all_pads()
                case "PLUGINS":
                    if substate:
                        substate = False
                        set_state() #go back to plugin rack view
        
        # right button (67) - move right through grid
        elif event.data1 == BT_RIGHT:
            match current_state:
                case "PATTERNS":
                    if patterns_pads_h_shift == 0:
                        patterns_pads_h_shift = 1
                        patterns_pads_h_ofst = patterns_pads_h_shift*GRID_SIZE_X
                        patterns__update_all_pads()

        # button belonging to 8x8 pad grid
        elif event.data1 in range(PAD_END + 1):
            match current_state:
                case "PATTERNS":
                    patterns__update_single_pad(event.data1)
                case "PLUGINS":
                    if not substate:
                        plugins__select_on_pad(event.data1)
                    else:
                        plugins__set_par_val(event.data1)
            
                

        # fader control button 
        elif event.data1 in range(BT_VOL,BT_DEVICE + 1):
            current_fader_mode_index = event.data1 - BT_VOL
            ctrl_colour__update_fader(event.data1)
            debug_print(f'Fader mode changed to: {FADER_MODES[current_fader_mode_index]}')
            

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

    event.handled = True
    
def OnUpdateBeatIndicator(val):
    global bar_cnt,beat_cnt,on_beat, pattern_n_bars
    debug_print(f'update Beat Indicator: {val}')
    song_pos = transport.getSongPos(4) #SONGLENGTH_STEPS
    song_bar = transport.getSongPos(3)
    debug_print(f'song bar: {song_bar},  step: {song_pos}')
    if val != 0:
        on_beat = True
        if val == 1: #ON BAR
            bar_cnt += 1
            beat_cnt = 0
            if bar_cnt == pattern_n_bars:
                bar_cnt = 0
        if val == 2: #ON BEAT
            beat_cnt += 1
    else:
        on_beat = False

    if current_state_index == 1:
        patterns__update_all_pads()                   

# CONTROLLER INTERFACE: SET LAYER (STATE)
def set_state():
    """Update all pad LEDs (notes 0-63) based on current state"""

    # turn whole pad grid off
    reset_pads_grid()

    substate = False #reset substate to off if prev state was PLUGINS-> EDIT PLUGIN

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
            
            patterns__update_all_pads()
        case "PLUGINS":
            plugins__get_data()
            plugins__display_on_pads()

            """
            for note in range(BT_UP,BT_DEVICE + 1):
                device.midiOutMsg(144, 0, note, LED_OFF)
            for note in range(PAD_START, PAD_END + 1):
                device.midiOutMsg(144, 0, note, LED_RED)
            """
        case "C":
            for note in range(BT_UP,BT_DEVICE + 1):
                device.midiOutMsg(144, 0, note, LED_OFF)
            for note in range(PAD_START, PAD_END + 1):
                device.midiOutMsg(144, 0, note, LED_YELLOW) 

# LAYER 1: PATTERNS
""" duplicate?
##input from user  
                             
def patterns__update_pad(row,index):
    #Store new data in grid_data and update FL channel
    global patterns_pads_h_ofst
    global grid_data
    index_with_offset = index + patterns_pads_h_ofst
    stored_value = grid_data[row][index_with_offset]
    new_value = 1 - stored_value
    grid_data[row][index_with_offset] = new_value
    channels.setGridBit(row,index,new_value)  #setGridBit 	int index, int position, int value, (bool useGlobalIndex* = False) 	- 	Set grid bit value at "position" for channel at "index".
    #debug_print(f'row: {row}, index: {index}, value: {new_value}')
    return new_value
"""
##query FL for pattern data
def patterns__get_data():
    global n_channels, grid_data, pattern_max_length
    n_channels = channels.channelCount()
    pattern_max_length = patterns.patternMax()
    pattern_n_bars = math.floor(pattern_max_length / 8) + 1
    #calculate how many pages we need according to the current max length of a pattern
    n_pages = math.floor(pattern_max_length/GRID_SIZE_X) + 1
    current_page = navigation["PATTERNS"]["current_page"]
    if n_pages >= current_page:
        navigation["PATTERNS"]["current_page"] = n_pages - 1
    navigation["PATTERNS"]["pages"] = n_pages

    grid_data = [[-1 for _ in range(pattern_max_length)] for _ in range(n_channels)]

    for channel in range(0,n_channels):
        for idx in range(0,pattern_max_length):
            grid_data[channel][idx] = channels.getGridBit(channel,idx)
            debug_print(f"channel: {channel}, pos: {idx}, value; {grid_data[channel][idx]}")
            if grid_data[channel][idx] == 1:
                empty_grid = False
                debug_print(f'note found @ ch {channel}, pos {idx}')

##control led colour of pads
def patterns__update_all_pads():
    global navigation, grid_data

    reset_pads_grid()
    # draw navigation row
    n_pages = navigation["PATTERNS"]["pages"]
    current_page = navigation["PATTERNS"]["current_page"]
    for page in range (PAD_PAGE_NAVIGATION_START, PAD_PAGE_NAVIGATION_END):
        if page == current_page:
           colour = LED_GREEN_BLINK 
        elif page < n_pages:
            colour = LED_GREEN
        else:
            colour = LED_OFF
    device.midiOutMsg(144, 0, page, colour)        
    
    # set the right and left navigation buttons  
    if current_page < n_pages - 1:
        device.midiOutMsg(144, 0, BT_RIGHT, LED_RED)
    else:
        device.midiOutMsg(144, 0, BT_RIGHT, LED_OFF)
        
    if current_page > 0:
        device.midiOutMsg(144, 0, BT_LEFT, LED_RED)
    else:
        device.midiOutMsg(144, 0, BT_RIGHT, LED_OFF)

    x_range_min = current_page*GRID_SIZE_X
    x_range_max = x_range_min+GRID_SIZE_X 
    for row in range(0, GRID_SIZE_Y):
        for x in range(x_range_min, x_range_max):      
            val = grid_data[row][x]
            if val == -1:
                color = LED_OFF
            elif val == 0:
                color = LED_GREEN
            elif val == 1:
                color = LED_GREEN_BLINK
            pad = pad - x_range_min #position of slot in pattern -> pad in controller
            note = padgrid__xy_to_note(x,row)

            debug_print(f'row: {row}, pad: {pad}, note: {note}, color: {color}')
            device.midiOutMsg(144, 0, note, color)

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
        color = LED_GREEN
    else:
        color = LED_GREEN_BLINK
    device.midiOutMsg(144, 0, note, color)

## control led playindex when playing
def patterns__update_pads_playidx(): #FINO A QUI
    global navigation,bar_cnt,beat_cnt, grid_data,on_beat,pattern_n_bars
    patterns__update_all_pads()   
    current_page = navigation["PATTERNS"]["current_page"]
    beats_per_page = 2
    page_of_beat = math.floor(beat_cnt/beats_per_page)   
    if (beat_cnt <= 1 and patterns_pads_h_shift == 0 or
        beat_cnt > 1 and patterns_pads_h_shift == 1):
        pos_x = (beat_cnt % 2) * 4 
        if not on_beat: #add off beat offset
            pos_x += 2
        for channel in range(0,n_channels):
            note = ((GRID_SIZE_X-1-channel) * GRID_SIZE_X) + (pos_x) # - patterns_pads_h_ofst)
            pad_status = grid_data[channel][pos_x+patterns_pads_h_ofst]
            if pad_status == 1: #LED_GREEN_BLINK
                device.midiOutMsg(144, 0, note, LED_RED) 
            elif pad_status == 0: #LED_GREEN
                device.midiOutMsg(144, 0, note, LED_YELLOW)

def reset_pads_grid():
    for note in range(PAD_START, PAD_END):
        device.midiOutMsg(144, 0, note, LED_OFF)

#LAYER 2: PLUGINS
def plugins__get_data():   
    global n_channels,tracks_data
    print('function plugins__get_data')
    tracks_data = {}

    # check number of tracks
    n_tracks = mixer.trackCount() 

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
                            
def plugins__display_on_pads():
    global tracks_data, plugins_pads_v_ofst
    
    first_track = plugins_pads_v_ofst
    last_track = plugins_pads_v_ofst + 3
    track_to_y_offset = [0, 3, 6] #we want to display three tracks per grid page.

    n_tracks = len(tracks_data)
    if last_track > n_tracks:
        last_track = n_tracks

    for track in range(first_track, last_track):
        track_key = str(track)
        if track_key not in tracks_data:
            continue  # skip if missing

        plugins_dict = tracks_data[track_key]["plugins"]
        y_offset = track_to_y_offset[track - first_track]
        slot_idx = 0

        for _slot_key, slot_data in plugins_dict.items():
            y = y_offset
            if slot_idx >= GRID_SIZE_X:
                y += 1
            x = slot_idx % GRID_SIZE_X
            note = padgrid__xy_to_note(x, y)

            if slot_data["name"] == "empty":
                device.midiOutMsg(144, 0, note, LED_OFF)
            else:
                device.midiOutMsg(144, 0, note, LED_YELLOW)

            slot_idx += 1
    
    debug_print("done displaying pars")

def plugins__select_on_pad(note):
    global tracks_data, substate, selected_plugin
    # turn note to row/coloumn coordinates
    x,y = padgrid__note_to_xy(note)
    debug_print(f"x: {x}, y: {y}")
    track = math.floor(y / 3)
    slot = x + (GRID_SIZE_X * (y -( track * 3)))
 
    track_key = str(track)
    slot_key = str(slot)

    # Safeguard against missing data
    if track_key not in tracks_data:
        debug_print(f"Track {track_key} not found in tracks_data")
        return
    if slot_key not in tracks_data[track_key]["plugins"]:
        debug_print(f"Slot {slot_key} not found in track {track_key}")
        return

    selected_plugin = [track,slot]
    substate = True
    reset_pads_grid()
    plugin = tracks_data[track_key]["plugins"][slot_key]
    plugin_name = plugin["name"]

    # Count number of parameters
    n_pars = len(plugin["pars"])
    debug_print(f"track: {track}, slot: {slot}, plugin: {plugin_name}, n_pars: {n_pars}")
    
    for par_idx in range(0,n_pars):
        y_par = math.floor(par_idx / GRID_SIZE_X) * 3
        x_par = (par_idx % GRID_SIZE_X)
        if y_par < GRID_SIZE_X: # temporary, need to implement navigation
            note_par = padgrid__xy_to_note(x_par, y_par)
            colour = LED_GREEN if note_par % 2 == 0 else LED_RED
            device.midiOutMsg(144, 0, note_par, colour)
   
def plugins__set_par_val(note):
    global tracks_data, selected_plugin
    x,y = padgrid__note_to_xy(note)
    if y % 3 == 0: #these pads represents the pars, have no command mapped on them (yet..?)
        pass
    else:
        op = "+" if y % 3 == 1 else "-"
        track = selected_plugin[0]
        slot = selected_plugin[1]
        #plugin = tracks_data[track_key]["plugins"][slot_key]
        par_current_val = plugins.getParamValue(x, track, slot)
        mod = 0.05 if op == "+" else -0.05
        par_new_val = clip(par_current_val + mod,0,1)
        plugins.setParamValue(par_new_val, x, track, slot)

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

# TIME SIGNATURE AND TEMPO
def getTimeSignature():
    global timebase, time_signature, tempo
    timebase = general.getRecPPQ()
    time_signature = general.getRecPPB()
    tempo = mixer.getCurrentTempo()/1000
    debug_print(f'tempo: {tempo}')
    debug_print(f'time signature:{timebase},  {time_signature}')

#CONVERSION FORMULAS
def padgrid__xy_to_note(x,y):
    return ((GRID_SIZE_X-1-y) * GRID_SIZE_X) + (x)

def padgrid__note_to_xy(note):
    global PAD_START, PAD_END, GRID_SIZE_X
    if note in range(PAD_START, PAD_END + 1):
        y = GRID_SIZE_X - 1 - math.floor(note/GRID_SIZE_X) 
        x = note % GRID_SIZE_X
        return x,y
    print(f"function padgrid__note_to_xy(). Parameter note ({note}) not in PAD_GRID range")

def pattern__note_to_data_indeces(note,page):
    global PAD_GRID_START, PAD_GRID_END, GRID_SIZE_X 
    if note in range(PAD_GRID_START, PAD_GRID_END + 1):
        y = GRID_SIZE_X - 1 - math.floor(note/GRID_SIZE_X) 
        x = GRID_SIZE_X*page + (note % GRID_SIZE_X)
        return x,y
    print(f"function pattern__note_to_data_indeces(). Parameter note ({note}) not in pattern PAD_GRID range")

def clip(value, min_value, max_value):
    return max(min_value, min(value, max_value))

#DEBUGGING
def debug_print(message):
    # Get the name of the caller function
    caller = inspect.currentframe().f_back.f_code.co_name
    if DEBUG.get(caller, False):
        print(f"[{caller}] {message}")
