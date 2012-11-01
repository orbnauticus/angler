
all:
	@python setup.py build

.PHONY: all test

test: chroot
	@cp -R angler iws.py chroot
	@chroot chroot python iws.py

chroot: chroot.tar.gz
	@tar -xf chroot.tar.gz

chroot.tar.gz:
	@debootstrap --components=main,universe quantal chroot http://archive.ubuntu.com/ubuntu
	@chroot chroot apt-get -y install python python-apt
	@tar -cf chroot.tar.gz chroot
