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
	pipenv lock -r > requirements.txt

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
	python setup.py sdist bdist_wheel
	pip2 install urllib3[secure] --upgrade
	pip2 install twine --upgrade
	twine upload dist/webreview-$(VERSION)*
