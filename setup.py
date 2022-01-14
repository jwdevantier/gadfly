from setuptools import setup


def get_requirements():
    # intentionally naive, does not support include files etc
    with open("./requirements.txt") as fp:
        return fp.read().split()


setup(
    name="gadfly",
    packages=["gadfly"],
    version="0.1.0",
    description="static site generator",
    author="Jesper Wendel Devantier",
    url="https://github.com/jwdevantier/gadfly",
    license="MIT",
    install_requires=get_requirements(),
    options={"bdist_wheel": {"universal": True}},
    entry_points = {
        "console_scripts": [
            "gadfly=gadfly.__main__:main"
        ]
    },
    classifiers=[
        "Programming Language :: Python",
    ]
)
