#!/usr/bin/env python3
"""
Python 3 interface for Conexant CX93001 chipset based voice modems.
"""

__author__ = "havocsec"
__version__ = "0.0.3"
__license__ = "GPLv3"

import os
import sys
import time
import wave
from datetime import datetime
import serial
from pydub import AudioSegment


class CouldNotInitializeException(Exception):
    pass


class CX93001:
    """Main modem class

    Main class to interface with Conexant CX93001 chipset based voicemodems.
    """

    __con = None

    def __init__(self, port='/dev/ttyACM0', baudrate=115200):
        """Constructor

        Class constructor that accepts a custom serial port and baudrate.
        By default, parameters are set to 8N1 comm @ 115200 bauds, no
        XONXOFF, no RTS/CTS, no DST/DTR and no write timeout. Then, the
        serial connection is open and the modem configuration is reset.
        Finally, the verbosity, echoing and caller ID are enabled through
        AT commands.
        """

        self.__con = serial.Serial()
        # Set the port and the baudrate
        self.__con.port = port
        self.__con.baudrate = baudrate
        # Set 8N1
        self.__con.bytesize = serial.EIGHTBITS
        self.__con.parity = serial.PARITY_NONE
        self.__con.stopbits = serial.STOPBITS_ONE
        self.__con.timeout = 3
        self.__con.xonxoff = False
        self.__con.rtscts = False
        self.__con.dsrdtr = False
        self.__con.writeTimeout = False
        # Try to open the connection
        try:
            self.__con.open()
        except serial.SerialException:
            raise CouldNotInitializeException("Could not open a serial connection")
        # Try to initialize
        if not self.__at('ATE1'):
            raise CouldNotInitializeException("Could not enable command echoing")
        if not self.__at('AT'):
            raise CouldNotInitializeException("Could not execute AT commands")
        if not self.__at('AT&F0'):
            raise CouldNotInitializeException("Could not reset to default state")
        if not self.__at('ATV1'):
            raise CouldNotInitializeException("Could not enable verbose reporting")
        if not self.__at('ATE1'):
            raise CouldNotInitializeException("Could not enable command echoing")
        if not self.__at('AT+VCID=1'):
            raise CouldNotInitializeException("Could not enable caller ID")

    def __del__(self):
        """Destructor

        Closes the serial connection.
        """

        self.__con.close()

    def self_test(self):
        """Returns True if the modem is working correctly

        Returns True if the modem is working correctly, False otherwise
        """

        return self.__at('AT') and self.__at('AT&F0') and self.__at('ATV1') and self.__at('ATE1') \
               and self.__at('AT+VCID=1') and self.__at('ATI1') \
               and self.__at('ATI2')
                # and self.__at('ATI3', 'CX93001-EIS_V0.2013-V92') and self.__at('ATI0', '56000')

    def __at(self, cmd, expected='OK'):
        """Execute AT command, returns True if the expected response is received, False otherwise.

        Executes an AT command and waits for the expected response, which is 'OK' by default. If the
        expected response is received, True is returned. In any other case, False is returned.
        """

        self.__con.write((cmd + "\r").encode())
        resp = self.__con.readline()
        while resp == b'\r\n' or resp == b'OK\r\n':
            resp = self.__con.readline()
        if resp != (cmd + '\r\r\n').encode():
            return False
        resp = self.__con.readline()
        if resp == (expected + '\r\n').encode():
            #print('OK:', cmd)
            return True
        else:
            #print('NOK:', cmd)
            return False

    def __detect_end(self, data):
        """Detects the end of an ongoing call

        Returns if <DLE>s (silence), <DLE>b (busy tone) or <DLE><ETX> (End of TX) are detected in the
        provided data.
        """

        return b'\x10s' in data or b'\x10b' in data or b'\x10\x03' in data

    def wait_call(self, max_rings_ignore_cid=4):
        """Waits until an incoming call is detected, then returns its caller ID data

        Waits until an incoming call is detected, then returns its caller ID data if possible (date, number). If after
        max_rings_ignore_cid rings no caller ID data is detected, then returns the tuple (date, '').
        """

        rings = 0
        while True:
            data = self.__con.readline().decode().replace('\r\n', '')
            if data != '':
                #print(data)
                if 'NMBR' in data:
                    return datetime.now(), data.replace('NMBR = ', '')
                if 'RING' in data:
                    # Just in case Caller ID isn't working
                    rings += 1
                    if rings >= max_rings_ignore_cid:
                        return datetime.now(), ''

    def accept_call(self):
        """Accept an incoming call

        Sets voice mode, voice sampling mode to 8-bit PCM mono @ 8000Hz, enables transmitting operating mode
        and answers the call.
        """

        self.__at('AT+FCLASS=8')
        self.__at('AT+VSM=1,8000,0,0')
        self.__at('AT+VLS=1')
        # Pick up
        self.__at('ATA')

    def play_audio_obj(self, wavobj, timeout=0):
        """Transmits a wave audio object over an ongoing call

        Transmits a wave audio object over an ongoing call. Enables voice transmit mode and the audio is
        played until it's finished if the timeout is 0 or until the timeout is reached.
        """

        if timeout == 0:
            timeout = wavobj.getnframes() / wavobj.getframerate()
        self.__at('AT+VTX')
        #print(timeout)
        chunksize = 1024
        start_time = time.time()
        data = wavobj.readframes(chunksize)
        while data != '':
            self.__con.write(data)
            data = wavobj.readframes(chunksize)
            time.sleep(.06)
            if time.time() - start_time >= timeout:
                break

    def play_audio_file(self, wavfile, timeout=0):
        """Transmits a wave 8-bit PCM mono @ 8000Hz audio file over an ongoing call

        Transmits a wave 8-bit PCM mono @ 8000Hz audio file over an ongoing call. Enables voice transmit mode
        and the audio is played until it finished if the timeout is 0 or until the timeout is reached.
        """

        wavobj = wave.open(wavfile, 'rb')
        self.play_audio_obj(wavobj, timeout=timeout)
        wavobj.close()

    def tts_say(self, phrase, lang='english'):
        """Transmits a TTS phrase over an ongoing call

        Uses espeak and ffmpeg to generate a wav file of the phrase. Then, it's transmitted over the ongoing call.
        """

        os.system('espeak -w temp.wav -v' + lang + ' \"' + phrase + '\" ; ffmpeg -i temp.wav -ar 8000 -acodec pcm_u8 '
                                                                    ' -ac 1 phrase.wav')
        os.remove('temp.wav')
        self.play_audio_file('phrase.wav')
        os.remove('../phrase.wav')

    def play_tones(self, sequence):
        """Plays a sequence of DTMF tones

        Plays a sequence of DTMF tones over an ongoing call.
        """

        self.__at('AT+VTS=' + ','.join(sequence))
        time.sleep(len(sequence))

    def reject_call(self):
        """Rejects an incoming call

        Answers the call and immediately hangs up in order to correctly terminate the incoming call.
        """

        self.__at('ATA')
        self.hang_up()

    def hang_up(self):
        """Terminates an ongoing call

        Terminates the currently ongoing call
        """

        self.__at('AT+FCLASS=8')
        self.__at('ATH')

    def dial(self, number):
        """Initiate a call with the desired number

        Sets the modem to voice mode, sets the sampling mode to 8-bit PCM mono @ 8000 Hz, enables transmitting
        operating mode, silence detection over a period of 5 seconds and dials to the desired number.
        """

        self.__at('AT+FCLASS=8')
        self.__at('AT+VSM=1,8000,0,0')
        self.__at('AT+VLS=1')
        self.__at('AT+VSD=128,50')
        self.__at('ATD' + number)

    def record_call(self, date=datetime.now(), number='unknown', timeout=7200):
        """Records an ongoing call until it's finished or the timeout is reached

        Sets the modem to voice mode, sets the sampling mode to 8-bit PCM mono @ 8000 Hz, enables transmitting
        operating mode, silence detection over a period of 5 seconds and voice reception mode. Then, a mp3 file
        is written until the end of the call or until the timeout is reached.
        """
        
        self.__at('AT+FCLASS=8')
        self.__at('AT+VSM=1,8000,0,0')
        self.__at('AT+VLS=1')
        self.__at('AT+VSD=128,50')
        self.__at('AT+VRX', 'CONNECT')

        chunksize = 1024
        frames = []
        start = time.time()
        while True:
            chunk = self.__con.read(chunksize)
            if self.__detect_end(chunk):
                break
            if time.time() - start >= timeout:
                #print('Timeout reached')
                break
            frames.append(chunk)
        self.hang_up()
        # Merge frames and save temporarily as .wav
        wav_path = date.strftime('%d-%m-%Y_%H:%M:%S_') + number + '.wav'
        wav_file = wave.open(wav_path, 'wb')
        wav_file.setnchannels(1)
        wav_file.setsampwidth(1)
        wav_file.setframerate(8000)
        wav_file.writeframes(b''.join(frames))
        wav_file.close()
        # Convert from .wav to .mp3 in order to save space
        segment = AudioSegment.from_wav(wav_path)
        segment.export(wav_path[:-3] + 'mp3', format='mp3')
        os.remove(wav_path)
