# name=AKAI APC mini LED light tester
# url=https://www.akaipro.com/apc-mini

import device
import channels
import playlist

# APC mini LED colors (velocity values for Note On messages)
LED_OFF = 0
LED_GREEN = 1
LED_GREEN_BLINK = 2
LED_RED = 3
LED_RED_BLINK = 4
LED_YELLOW = 5
LED_YELLOW_BLINK = 6

# Pad 
PAD_START = 0
PAD_END = 63

def OnInit():
    """Called when script is loaded"""

    print('AKAI APC mini LED light tester initialized')

    for note in range(PAD_START, PAD_END + 1):
        device.midiOutMsg(144, 0, note, LED_GREEN_BLINK) #int midiId, int channel, int data1, int data2 

def OnRefresh(flag):
    for note in range(PAD_START, PAD_END + 1):
        device.midiOutMsg(144, 0, note, LED_RED_BLINK)