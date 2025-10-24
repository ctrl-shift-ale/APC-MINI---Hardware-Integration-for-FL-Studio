# name=AKAI APC mini Proto Main
# url=https://www.akaipro.com/apc-mini

import device
import channels
import playlist
import patterns
import mixer 
import transport
import general

import math
import time

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
GRID_SIZE = 8

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

# State system
STATES = ["DEFAULT","CHANNELS_GRID", "B", "C"]
STATE_COLORS = {
    "DEFAULT": LED_OFF,
    "CHANNELS_GRID": LED_GREEN,
    "B": LED_RED,
    "C": LED_YELLOW
}

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

DEFAULT_N_CHANNELS = 8


#Grid matrix
pattern_max_length = GRID_SIZE*2
grid_data = [[-1 for _ in range(pattern_max_length)] for _ in range(DEFAULT_N_CHANNELS)]
# Global state tracker
current_state_index = 0

horizontal_shift = 0 #which bars are being displayed ( 0 -> beat 0 to 7 ; 1 -> beat 8 to 15)
horizontal_offset = 0
n_channels = 0

current_fader_mode_index = 0 #volume

timebase = 0
time_signature = 0
tempo = 0
semiquaver_dur_ms = 0
semiquaver = True

playing = 0
playing_his = 0

beat_cnt = 0
on_beat = False

def OnInit():
    """Called when script is loaded"""
    global current_state_index
    global current_fader_mode_index
    current_state_index = 0
    current_fader_mode_index = 0 #volume
    
 
    ChangeState()
    GetGridData()
    #check time signature
    GetTimeSignature()

    time.sleep(0.1)

    UpdateFaderCtrlColour(BT_VOL)

    print('AKAI APC mini State Navigator initialized')
    print(f'Starting in State: {STATES[current_state_index]}')

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
    global current_state_index
    if status == 100: #project succesfully loaded
        current_state_index = 0
        GetGridData()

def OnRefresh(flag):
    global playing
    global playing_his
    print(f'Refresh: {flag}')
    n = flag
    found_flags = []
    for i in range(len(ONREFRESH_FLAGS)-1,-1,-1):
        exp = math.pow(2,i)
        #print(f'exp: {exp}')
        if n - exp >= 0:
            print(f"found flag: {exp} = {ONREFRESH_FLAGS[i]}")
            found_flags.append(ONREFRESH_FLAGS[i])
            n -= exp

    #check time signature
    GetTimeSignature()

    #check if a pattern has been modified
    if "HW_Dirty_Patterns" in found_flags or "HW_Dirty_Tracks" in found_flags:
        print("found flag HW_Dirty_Patterns or HW_Dirty_Tracks")
        #print(f'current state index: {current_state_index}')
        GetGridData()
        if current_state_index == 1:
            print("Updating All Pads")
            ChGrid_UpdateAllGridPads()

    #check if playing
    playing = transport.isPlaying()
    if playing_his != playing:
        print(f'PLAYING IS NOW {playing}')
        playing_his = playing
        if playing == 0:
            ChGrid_UpdateAllGridPads()

def OnUpdateBeatIndicator(val):
    global beat_cnt,on_beat
    print(f'update Beat Indicator: {val}')
    song_pos = transport.getSongPos(4) #SONGLENGTH_STEPS
    song_bar = transport.getSongPos(3)
    print(f'song bar: {song_bar},  step: {song_pos}')
    if val != 0:
        on_beat = True
        if val == 1: #ON BAR
            beat_cnt = 0
        if val == 2: #ON BEAT
            beat_cnt += 1
    else:
        on_beat = False

    if current_state_index == 1:
        UpdatePadPlayIdx()

   

def OnMidiMsg(event):
    """
    Main MIDI message handler
    event.status: MIDI status byte (144 = Note On)
    event.data1: Note number
    event.data2: Velocity
    """
    global current_state_index
    global current_fader_mode_index
    global horizontal_shift
    global horizontal_offset
    
    event.handled = False
    
    # Note On messages
    if event.status == 144 and event.data2 > 0:
        print(f'note on: {event.data1}')
        # Change state button (87) - move forward through states
        if event.data1 == BT_STATE:
            current_state_index = (current_state_index + 1) % len(STATES)
            print(f'State changed to: {STATES[current_state_index]}')
            ChangeState()
           
        
        # Down button (65) - move backward through states
        #elif event.data1 == BT_DWN:
        #    current_state_index = (current_state_index - 1) % len(STATES)
        #    print(f'State changed to: {STATES[current_state_index]}')
        #    ChangeState()
        #    event.handled = True
        
        # left button (66) - move left through grid
        elif event.data1 == BT_LEFT:
            if current_state_index == 1:
                if horizontal_shift == 1:
                    horizontal_shift = 0
                    horizontal_offset = 0
                    ChGrid_UpdateAllGridPads()
        
        # right button (67) - move right through grid
        elif event.data1 == BT_RIGHT:
            if current_state_index == 1:
                if horizontal_shift == 0:
                    horizontal_shift = 1
                    horizontal_offset = horizontal_shift*GRID_SIZE
                    ChGrid_UpdateAllGridPads()

        # button belonging to 8x8 pad grid
        elif event.data1 in range(PAD_END + 1):
            if current_state_index == 1:
                ChGrid_UpdateSingleGridPad(event.data1)
                

        # fader control button 
        elif event.data1 in range(BT_VOL,BT_DEVICE + 1):
            current_fader_mode_index = event.data1 - BT_VOL
            UpdateFaderCtrlColour(event.data1)
            print(f'Fader mode changed to: {FADER_MODES[current_fader_mode_index]}')
            

    # CC messages
    if event.status == 176:
        cc_ch = event.data1
        cc_val = event.data2   
        if cc_ch in range(FADER_0,FADER_7+1):
            fader_mode = FADER_MODES[current_fader_mode_index]
            print(f'midi channel {cc_ch}, val: {cc_val}') 
            print(f'fader mode: {fader_mode}') 
            match fader_mode:
                case "VOLUME":
                    Channel_Update_Vol(cc_ch,cc_val)
                case "PAN":
                    Channel_Update_Pan(cc_ch,cc_val)
                case "SEND":
                    Channel_Update_Send(cc_ch,cc_val)
        elif cc_ch == FADER_MASTER:
            mixer.setTrackVolume(0, cc_val/127)

    event.handled = True
    
                    
def ChangeState():
    """Update all pad LEDs (notes 0-63) based on current state"""
    current_state = STATES[current_state_index]
    color = STATE_COLORS[current_state]

    match current_state:
        case "DEFAULT":
            for note in range(BT_UP,BT_DEVICE + 1):
                device.midiOutMsg(144, 0, note, LED_OFF)
            # Set all pads to the current state's color
            for note in range(PAD_START, PAD_END + 1):
                device.midiOutMsg(144, 0, note, LED_OFF) 
            
        case "CHANNELS_GRID":
            ChGrid_UpdateAllGridPads()
        case "B":
            for note in range(BT_UP,BT_DEVICE + 1):
                device.midiOutMsg(144, 0, note, LED_OFF)
            for note in range(PAD_START, PAD_END + 1):
                device.midiOutMsg(144, 0, note, LED_RED) 
        case "C":
            for note in range(BT_UP,BT_DEVICE + 1):
                device.midiOutMsg(144, 0, note, LED_OFF)
            for note in range(PAD_START, PAD_END + 1):
                device.midiOutMsg(144, 0, note, LED_YELLOW) 
   
def UpdateFaderCtrlColour(button):
    if button in range(BT_VOL,BT_DEVICE+1):
        print(f"update fade ctrl midi note: {button}")
        for note in range(BT_VOL,BT_DEVICE+1):
            colour = LED_OFF if note != button else LED_RED
            print(f'note: {note}, colour: {colour}')
            device.midiOutMsg(144, 0, note, colour)

def UpdatePadPlayIdx():
    global beat_cnt, grid_data,horizontal_shift,horizontal_offset,on_beat
    ChGrid_UpdateAllGridPads()      
    if (beat_cnt <= 1 and horizontal_shift == 0 or
        beat_cnt > 1 and horizontal_shift == 1):
        pos_x = (beat_cnt % 2) * 4 
        if not on_beat: #add off beat offset
            pos_x += 2
        for channel in range(0,n_channels):
            note = ((GRID_SIZE-1-channel) * GRID_SIZE) + (pos_x) # - horizontal_offset)
            pad_status = grid_data[channel][pos_x+horizontal_offset]
            if pad_status == 1: #LED_GREEN_BLINK
                device.midiOutMsg(144, 0, note, LED_RED) 
            elif pad_status == 0: #LED_GREEN
                device.midiOutMsg(144, 0, note, LED_YELLOW)
                
                

def UpdateGrid(row,index):
    """Store new data in grid_data and update FL channel"""
    global horizontal_offset
    global grid_data
    index_with_offset = index + horizontal_offset
    stored_value = grid_data[row][index_with_offset]
    new_value = 1 - stored_value
    grid_data[row][index_with_offset] = new_value
    channels.setGridBit(row,index,new_value)  #setGridBit 	int index, int position, int value, (bool useGlobalIndex* = False) 	- 	Set grid bit value at "position" for channel at "index".
    #print(f'row: {row}, index: {index}, value: {new_value}')
    return new_value

def ChGrid_UpdateAllGridPads():
    global horizontal_offset
    global horizontal_shift
    global grid_data

    if horizontal_shift == 0:
        device.midiOutMsg(144, 0, BT_LEFT, LED_OFF)
        device.midiOutMsg(144, 0, BT_RIGHT, LED_RED)
    if horizontal_shift == 1:
        device.midiOutMsg(144, 0, BT_LEFT, LED_RED)
        device.midiOutMsg(144, 0, BT_RIGHT, LED_OFF)

    for row in range(0, GRID_SIZE):
        for pad in range(horizontal_offset, GRID_SIZE + horizontal_offset):      
            val = grid_data[row][pad]
            if val == -1:
                color = LED_OFF
            elif val == 0:
                color = LED_GREEN
            elif val == 1:
                color = LED_GREEN_BLINK
            note = ((GRID_SIZE-1-row) * GRID_SIZE) + (pad - horizontal_offset)
            #print(f'row: {row}, pad: {pad}, note: {note}, color: {color}')
            device.midiOutMsg(144, 0, note, color)

def ChGrid_UpdateSingleGridPad(note):
    """Store new data in grid_data and update FL channel"""
    global horizontal_offset
    global grid_data
    # turn note to row/coloumn coordinates
    channel = GRID_SIZE - 1 - math.floor(note / GRID_SIZE) 
    col = note - (GRID_SIZE - 1 - channel)*GRID_SIZE 
    pos = col + horizontal_offset #while col represents the y position of the physical pad, pos represents the y position in the channel grid
    stored_value = grid_data[channel][pos]
    new_value = 1 - stored_value
    grid_data[channel][pos] = new_value
    channels.setGridBit(channel,pos,new_value)  #setGridBit 	int index, int position, int value, (bool useGlobalIndex* = False) 	- 	Set grid bit value at "position" for channel at "index".
    #print(f'channel: {channel}, pos: {col}, value: {new_value}')
    if new_value == 0:
        color = LED_GREEN
    else:
        color = LED_GREEN_BLINK
    device.midiOutMsg(144, 0, note, color)

def GetGridData():
    global n_channels, grid_data, pattern_max_length

    pattern_max_length = patterns.patternMax() #navigation right and left for more than 16 pattern length: to be developed
    n_channels = channels.channelCount() #playlist.getTrackCount()
    n_rows = n_channels if n_channels > GRID_SIZE else GRID_SIZE #navigation up and down for more than 8 channels: to be developed
    grid_data = [[-1 for _ in range(pattern_max_length)] for _ in range(n_rows)]

    for channel in range(0,n_channels):
        for idx in range(0,pattern_max_length):
            grid_data[channel][idx] = channels.getGridBit(channel,idx)
            if grid_data[channel][idx] == 1:
                print(f'note found @ ch {channel}, pos {idx}')

def Channel_Update_Vol(cc_ch,cc_val):
    channel = cc_ch - FADER_OFFSET
    channels.setChannelVolume(channel, cc_val/127)

def Channel_Update_Pan(cc_ch,cc_val):
    channel = cc_ch - FADER_OFFSET
    cc_val -= 64
    channels.setChannelPan(channel, cc_val/64)

def Channel_Update_Send(cc_ch,cc_val):
    track = cc_ch - FADER_OFFSET + 1 #0 is master track
    mixer.setTrackVolume(track, cc_val/127)

def GetTimeSignature():
    global timebase, time_signature, tempo, semiquaver_dur_ms

    timebase = general.getRecPPQ()
    time_signature = general.getRecPPB()
    tempo = mixer.getCurrentTempo()/1000
    semiquaver_dur_ms = (60000/tempo)/4
    print(f'tempo: {tempo}')
    print(f'time signature:{timebase},  {time_signature}')
    print(f'semiquaver_dur_ms:{semiquaver_dur_ms}')
