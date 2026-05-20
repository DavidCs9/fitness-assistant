build-SharedLayer:
	python3.12 -m pip install \
		-r requirements.txt \
		-t "$(ARTIFACTS_DIR)/python" \
		--platform manylinux2014_x86_64 \
		--only-binary=:all: \
		--python-version 3.12
	mkdir -p "$(ARTIFACTS_DIR)/python"
	cp -r python/. "$(ARTIFACTS_DIR)/python"
