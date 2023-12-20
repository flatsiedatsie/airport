#!/bin/bash

echo
echo "___installing packages___"
apt update
apt upgrade -y # this is optional but recommended
apt install -y --no-install-recommends build-essential git autoconf automake libtool \
 libpopt-dev libconfig-dev libasound2-dev avahi-daemon libavahi-client-dev libssl-dev libsoxr-dev \
 libplist-dev libsodium-dev libavutil-dev libavcodec-dev libavformat-dev uuid-dev libgcrypt-dev \
 libpipewire-0.3-dev xxd

mkdir -p ./final
rm -rf ./final/*

rm -rf ./shairport-sync
rm -rf ./nqptp

echo
echo "___cloning git___"
git clone https://github.com/mikebrady/shairport-sync.git

echo
echo "___building___"
cd shairport-sync
autoreconf -fi
./configure --sysconfdir=/etc --with-alsa \
 --with-pw --with-pipe --with-metadata \
 --with-soxr --with-avahi --with-ssl=openssl --with-systemd --with-airplay-2
make

#ls

echo
echo "___testing shairport___"

if [ -f shairport-sync ]; then
	./shairport-sync -v
	
	mv ./shairport-sync ../final/shairport
	cd ../final
	
	echo
	cd ..
#	echo "pwd:"
#	pwd

	echo
        echo "___building nqptp___"
	git clone https://github.com/mikebrady/nqptp.git
        cd nqptp
        autoreconf -fi
        ./configure
        make
	mv ./nqptp ../final/

        cd ../final
        
        echo
        echo "___copying libraries___"
        
        readelf -d shairport | grep 'Shared library:' | cut -d "[" -f2 | cut -d "]" -f1 | xargs -I% find / -name "%" | xargs cp -t .
        readelf -d nqptp | grep 'Shared library:' | cut -d "[" -f2 | cut -d "]" -f1 | xargs -I% find / -name "%" | xargs cp -t .

	ls -lah
	echo
	du . -h

	echo
	echo "DONE"

else
	echo
	echo "FAIL"
fi
