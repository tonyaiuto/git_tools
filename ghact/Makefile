BZL=bazelisk

test:
	$(BZL) test ...

try:	install
	ghact --if 


install:
	$(BZL) build :ghact --build_python_zip
	cp -f bazel-bin/ghact $(HOME)/bin

clean:
	rm -rf __pycache__
