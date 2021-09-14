# Gadfly
An in-progress static site generator.

## Why ?
Most static site generators are built around a series of assumptions which
may or may not fit your use-case.

Having tried and run into troubles with several such systems, I decided to build
a non-opinionated system which just provides a compiler, the ability to watch for
changes and a dev-server which reloads the page if it is changed.

Pages use jinja2 templating and support a custom markdown block - this permits
you to write markdown where desired, but emit plain, un-changed HTML where desired
or to express and use reusable jinja2 blocks.

Furthermore, all pages are compiled within a context - the context is produced
by a regular python function in `blogcode/__init__.py` and thus permits you to
use Python in full when computing the page context - no half-baked DSL's, no
limited set of framework-provided functions and/or variables.

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
