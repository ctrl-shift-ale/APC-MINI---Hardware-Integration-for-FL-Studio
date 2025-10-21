# name=AKAI APC mini State Navigator
# url=https://www.akaipro.com/apc-mini

import device
import channels

import math

# APC mini LED colors (velocity values for Note On messages)
LED_OFF = 0
LED_GREEN = 1
LED_GREEN_BLINK = 2
LED_RED = 3
LED_RED_BLINK = 4
LED_YELLOW = 5
LED_YELLOW_BLINK = 6

# Navigation buttons
BTN_UP = 64  # Note 64 - navigate forward
BT_DWN = 65  # Note 65 - navigate backward
BT_LEFT = 66  # Note 65 - navigate left
BT_RIGHT = 67  # Note 65 - navigate right

# Pad 
PAD_START = 0
PAD_END = 63
GRID_SIZE = 8

horizontal_offset = 0
# State system
STATES = ["DEFAULT","A", "B", "C"]
STATE_COLORS = {
    "DEFAULT": LED_OFF,
    "A": LED_GREEN,
    "B": LED_RED,
    "C": LED_YELLOW
}

#Grid matrix
GRID = [[0 for _ in range(GRID_SIZE*2)] for _ in range(GRID_SIZE)]
# Global state tracker
current_state_index = 0

def OnInit():
    """Called when script is loaded"""
    global current_state_index
    current_state_index = 0
    print('AKAI APC mini State Navigator initialized')
    print(f'Starting in State: {STATES[current_state_index]}')
    UpdateAllPads()

def OnDeInit():
    """Called when script is unloaded"""
    print('AKAI APC mini State Navigator deinitialized')
    # Turn off all LEDs
    for note in range(PAD_START, PAD_END + 1):
        device.midiOutMsg(144, note, LED_OFF)

def OnMidiMsg(event):
    """
    Main MIDI message handler
    event.status: MIDI status byte (144 = Note On)
    event.data1: Note number
    event.data2: Velocity
    """
    global current_state_index
    global horizontal_offset
    
    event.handled = False
    
    # Note On messages
    if event.status == 144 and event.data2 > 0:
        print(f'note on: {event.data1}')
        # Up button (64) - move forward through states
        if event.data1 == BTN_UP:
            current_state_index = (current_state_index + 1) % len(STATES)
            print(f'State changed to: {STATES[current_state_index]}')
            UpdateAllPads()
            event.handled = True
        
        # Down button (65) - move backward through states
        elif event.data1 == BT_DWN:
            current_state_index = (current_state_index - 1) % len(STATES)
            print(f'State changed to: {STATES[current_state_index]}')
            UpdateAllPads()
            event.handled = True
        
        # left button (66) - move left through grid
        elif event.data1 == BT_LEFT:
            if horizontal_offset == GRID_SIZE:
                horizontal_offset = 0
                RefreshPads_NewBars()
        
        # right button (67) - move right through grid
        elif event.data1 == BT_RIGHT:
            if horizontal_offset == 0:
                horizontal_offset = GRID_SIZE
                RefreshPads_NewBars()

        elif event.data1 in range(PAD_END + 1):
            if current_state_index == 1:
                ManageGrid(event.data1)
                event.handled = True
    
                    
def UpdateAllPads():
    """Update all pad LEDs (notes 0-63) based on current state"""
    current_state = STATES[current_state_index]
    color = STATE_COLORS[current_state]
    
    # Set all pads to the current state's color
    for note in range(PAD_START, PAD_END + 1):
        device.midiOutMsg(144, 0, note, color) #int midiId, int channel, int data1, int data2 
    
    print(f'All pads set to {current_state} ({color})')

def RefreshPads_NewBars():
    global horizontal_offset
    global GRID
    for row in range(0, 8):
        for pad in range(horizontal_offset, 8 + horizontal_offset):
            val = GRID[row][pad]
            if val == 0:
                color = LED_GREEN
            else:
                color = LED_GREEN_BLINK
            device.midiOutMsg(144, 0, pad-horizontal_offset, color)

def UpdateGrid(row,index):
    global horizontal_offset
    global GRID
    index_with_offset = index + horizontal_offset
    stored_value = GRID[row][index_with_offset]
    new_value = 1 - stored_value
    GRID[row][index_with_offset] = new_value
    channels.setGridBit(row,index,new_value)  #setGridBit 	int index, int position, int value, (bool useGlobalIndex* = False) 	- 	Set grid bit value at "position" for channel at "index".
    print(f'row: {row}, index: {index}, value: {new_value}')
    return new_value
    
def ManageGrid(note):
    row = GRID_SIZE - 1 - math.floor(note / GRID_SIZE) #7 - (56/8) = 0
    index = note - (GRID_SIZE - 1 - row)*GRID_SIZE # 56 - (7-0)*8 = 56 - 56 = 0
    val = UpdateGrid(row,index)
    if val == 0:
        color = LED_GREEN
    else:
        color = LED_GREEN_BLINK
    device.midiOutMsg(144, 0, note, color)

