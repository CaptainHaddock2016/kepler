# SPDX-FileCopyrightText: 2025 Liz Clark, Tim Cocks for Adafruit Industries
#
# SPDX-License-Identifier: MIT
exit()
import audiomp3
import helpers
import os

from adafruit_fruitjam.peripherals import Peripherals

fruit_jam = Peripherals(safe_volume_limit=20)

# use headphones
fruit_jam.dac.headphone_output = True
fruit_jam.dac.dac_volume = -5  # dB

#fruit_jam.dac.configure_clocks(sample_rate=44100, bit_depth=16)

fruit_jam.volume = 20

files = os.listdir("sd/root/home/playlists/chopin")
selection = helpers.select(files)
printf(f"Playing: {selection}")

print(f"sd/root/home/playlists/chopin/{selection}")
with open(f"sd/root/home/playlists/chopin/{selection}", "rb") as file:
    wav = audiomp3.MP3Decoder(file)

    print("Playing wav file!")
    fruit_jam.audio.play(wav)
    while fruit_jam.audio.playing:
        pass

print("Done!")
