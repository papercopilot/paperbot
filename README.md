# Paperbots
* https://packaging.python.org/en/latest/tutorials/packaging-projects/

https://github.com/pypa/twine/issues/424
```shell
# upload the build to test server
twine upload --repository-url https://test.pypi.org/legacy/ dist/*

# upload the build to pypi server
twine upload --repository-url https://upload.pypi.org/legacy/ dist/*
# or the following, note that following don't support re-upload for the same version
# twine upload dist/* 
```
Use API tokens ($HOME/.pypirc) instead of username/password to complete the upload
if .pypirc is not regonized, check [this](https://stackoverflow.com/questions/44892233/my-home-does-not-have-pypirc-file-which-is-giving-me-an-error-while-registering) out 
