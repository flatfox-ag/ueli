# Ueli

Ueli the servant helps to build and deploy at flatfox

## todos

- [ ] check if all kubernetes fils metadata.name begin with ueli.projectname


## test local

0. activate another python env
0. install dependencies e.g. `pip install -r /PATH/TO/ueli/requirements.txt`
0. install ueli `pip install -e /PATH/TO/ueli`

## create new version

    git tag 0.1 -m "tagged version"
    git push --tags origin master


## helpful links

- http://peterdowns.com/posts/first-time-with-pypi.html
- https://packaging.python.org/distributing/
- https://realpython.com/blog/python/comparing-python-command-line-parsing-libraries-argparse-docopt-click/
