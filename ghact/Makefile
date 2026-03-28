
test:
	bazel test ...

install:
	bazel build :ghact --build_python_zip
	cp -f bazel-bin/ghact $(HOME)/bin

clean:
	rm -rf __pycache__
