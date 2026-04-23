BZL=bazelisk

test:
	$(BZL) test ...

try:	install
	ghact --if ready add-comment 1 ready

install:
	@printf "VERSION = '%s'\n" "$$(date +%Y-%m-%d)" > version.py
	$(BZL) build :ghact --build_python_zip
	cp -f bazel-bin/ghact $(HOME)/bin

clean:
	rm -rf __pycache__

sync:
	cd .. ; $(MAKE) -$(MAKEFLAGS) sync
