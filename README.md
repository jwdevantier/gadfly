An in-progress static site generator.

## Why ?
Gadfly tries to provide as much of a scaffold for easy static site generation
*without* inventing a lot of structure for you to observe.
Having run into trouble with several static site generators assuming a certain 
structure or failing to support my use-cases, I decided to build as minimally
opinionated a generator as I could.

With Gadfly, pages are placed in a (configurably named) page directory,
and a development server can monitor changes to pages and/or any number
of assets directories - triggering recompilation and a browser refresh.

Pages themselves are jinja2 documents whose context environment is
given by you via a configurable hook function. Furthermore, the environment
is augmented with a markdown block tag, allowing you to effortlessly switch
between jinja2-code, HTML and markdown as fits the use-case.

You can also define as many asset directories as you want and for each
of them associate a handler function detailing how to compile the asset type.
This permits you to call out to specific CSS or javascript compilers as part of
the asset generation step.

The flexibility does come with a bit more work. Gadfly won't generate any
standard index page or any pages for browsing tags, or filter out pages
which are yet to be published.
However, by giving you full access to Python and a flexible set of hooks
into the compilation process, you can do all of this yourself and _exactly_ to
your liking.

## Installing
### (Regular) use
```
$ pip install --user .
```

### Development
If you wish to modify Gadfly itself, then do the following to make changes made
to Gadfly's code be reflected to the installed package:
```
$ python3 -m venv --system-site-packages .venv
$ source .venv/bin/activate
(venv) $ pip install --user --editable .
```
## Getting started
A project directory should have the following structure:

```
example_blog/
├── blogcode
│   └── __init__.py
├── pages
│   └── page1.md
└── templates
    └── base.j2
```

The `blogcode/__init__.py` file should have a `main` function which takes a
configuration object and returns a dictionary of entries which are made available
to the templates. A minimal main function looks like this:

```python
# minimal blogcode/__init__.py
from gadfly import Config


def main(config: Config) -> dict:
    return {
        "one": "two"
    }
```

The `pages` folder contains the actual page entries. Note that `pages/foo` will
produce the output `output/foo/index.html` when compiled - this keeps URLs pretty.

The `templates` folder contains templates which pages may inherit from.
