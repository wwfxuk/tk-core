build:
	cd ${REZ_BUILD_SOURCE_PATH} && \
	python setup.py build

.PHONY: install
install: build
	cp -r ${REZ_BUILD_SOURCE_PATH}/build/* ${REZ_BUILD_INSTALL_PATH}