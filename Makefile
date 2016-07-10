develop:
	@pip --version > /dev/null || { \
	  echo "pip not installed. Trying to install pip..."; \
	  sudo easy_install pip; \
	}
	@virtualenv --version > /dev/null || { \
	  echo "virtualenv not installed. Trying to install virtualenv..."; \
	  sudo pip install virtualenv; \
	}
	virtualenv env --distribute
	. env/bin/activate
	./env/bin/pip install -r requirements-dev.txt

test:
	. env/bin/activate
	./env/bin/nosetests \
	  -v \
	  --rednose \
	  --with-coverage \
	  --cover-erase \
	  --cover-html \
	  --cover-html-dir=htmlcov \
	  --cover-package=webreview \
	  webreview

upload-pypi:
	$(MAKE) test
	python setup.py sdist upload
	rm -rf *.egg-info
