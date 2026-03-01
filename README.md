# Airport

This is an add-on for the Candle Controller / WebThings Gateway, designed to be installed on the Raspberry Pi. It allows the Raspberry Pi to act as a receiver for Apple Airport audio streaming.

It implements two stream receiver servers:

Shairport-Sync
https://github.com/mikebrady/shairport-sync

RPiPlay
https://github.com/FD-/RPiPlay


Shairport-sync was created with:

```
./configure --sysconfdir=/etc --with-alsa --with-pipewire --with-soxr --with-avahi --with-ssl=openssl --sysconfdir=/home/pi/.webthings/data/airport --with-metadata --with-airplay-2
```
