
PROXY=http://10.42.0.1:3142
SUITE=precise

all:
	@python setup.py build

.PHONY: all test kvm-test

test: chroot
	@cp -R angler chroot/usr/lib/python2.7
	@cp -R test chroot
	@for x in test/*; do chroot chroot python $$x ; done

chroot: chroot.tar.gz
	@tar -xf chroot.tar.gz

chroot.tar.gz:
	@debootstrap --components=main,universe quantal chroot http://archive.ubuntu.com/ubuntu
	@chroot chroot apt-get -y install python python-apt
	@tar -cf chroot.tar.gz chroot

kvm:
	@env echo -e "sudo mount /dev/cdrom /mnt; cd /mnt; sudo python common.py;" > testscript
	@chmod +x testscript
	@env echo -e "Acquire::http { Proxy \"$(PROXY)\"; };" > aptproxy
	@env echo -e "aptproxy /etc/apt/apt.conf.d/02proxy" > filelist
	@vmbuilder kvm ubuntu --suite=$(SUITE) --tmpfs - --components=main,universe --copy filelist --addpkg python2.7 --addpkg python-apt -d kvm --firstlogin=$$PWD/testscript --proxy=$(PROXY)
	@rm filelist testscript aptproxy

angler.iso: angler test/common.py
	@mkdir angler_iso && cp -R angler test/* angler_iso
	@mkisofs -J -o angler.iso angler_iso
	@rm -r angler_iso
	
kvm-test: kvm angler.iso
	@cd kvm; sh run.sh -cdrom ../angler.iso
