
PROXY=http://10.42.0.1:3142
SUITE=utopic
PYTHON_VERSION=3.4
PYTHON_MAJOR=3

PYTHON=python$(PYTHON_VERSION)

VERSION=$(shell python setup.py --version)
FULLNAME=$(shell python setup.py --fullname)
PACKAGES=python-angler_$(VERSION)_all.deb

all: build

.PHONY: all test kvm-test clean deb install-deb build

clean:
	$(PYTHON) setup.py clean

build:
	$(PYTHON) setup.py build

sdist:
	$(PYTHON) setup.py sdist

deb: sdist
	@cd dist; tar -xf $(FULLNAME).tar.gz; cd $(FULLNAME); debuild -i -uc -us; fi
	@echo "Packages can be found under dist/"

install-deb:
	@cd dist; dpkg -i $(PACKAGES)

test: chroot
	@cp -R angler chroot/usr/lib/python$(PYMIN)
	@cp -R test chroot
	@for x in test/*; do chroot chroot python $$x ; done

chroot: chroot.tar.gz
	@tar -xf chroot.tar.gz

chroot.tar.gz:
	@debootstrap --components=main,universe $(SUITE) chroot http://archive.ubuntu.com/ubuntu
	@chroot chroot apt-get -y install $(PYTHON) python$(PYTHON_MAJOR)-apt
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
