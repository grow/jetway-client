PIP_ENV := $(shell pipenv --venv)
VERSION = $(shell cat webreview/VERSION)

# Default test target for "make test". Allows "make target=grow.pods.pods_test test"
target ?= 'webreview'

develop:
	@pip --version > /dev/null || { \
	  echo "pip not installed. Trying to install pip..."; \
	  sudo easy_install pip; \
	}
	@pipenv --version > /dev/null || { \
	  echo "pipenv not installed. Trying to install pipenv..."; \
	  sudo pip install pipenv; \
	}
	pipenv update
	pipenv install --dev

test:
	. $(PIP_ENV)/bin/activate
	$(PIP_ENV)/bin/nosetests \
	  -v \
	  --rednose \
	  --with-coverage \
	  --cover-erase \
		--cover-xml \
	  --cover-package=webreview \
	  $(target)

test-nosetests:
	. $(PIP_ENV)/bin/activate
	$(PIP_ENV)/bin/nosetests \
	  -v \
	  --rednose \
	  --with-coverage \
	  --cover-erase \
		--cover-xml \
	  --cover-package=webreview \
	  webreview

upload-pypi:
	$(MAKE) test
	. $(PIP_ENV)/bin/activate
	$(PIP_ENV)/bin/python3 setup.py sdist bdist_wheel
	$(PIP_ENV)/bin/pip3 install urllib3[secure] --upgrade
	$(PIP_ENV)/bin/pip3 install twine --upgrade
	$(PIP_ENV)/bin/twine upload dist/webreview-$(VERSION)*
