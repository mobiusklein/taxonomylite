from setuptools import setup

setup(
    name='taxonomylite',
    version='1.0.2',
    py_modules=["taxonomylite"],
    description="Traverse NCBI Taxonomy data using SQLite",
    long_description='''
A simple one-file solution for those times when you want to check if one organism is
a descended from another, but don't need a full phylogenetic tree manipulation library.

The library is just a single file that depends only upon the standard library.
You can easily embed it in another library by copying this script.
''',
    url="https://github.com/mobiusklein/taxonomylite",
    author=', '.join(["Joshua Klein", "Sukru N. Kaymakcalan", "Christian Wake"]),
    author_email=["joshua.adam.klein@gmail.com", "skaymakca@gmail.com", "cwake@bu.edu"],
    classifiers=[
            'Development Status :: 4 - Beta',
            'Intended Audience :: Science/Research',
            'License :: OSI Approved :: BSD License',
            'Topic :: Scientific/Engineering :: Bio-Informatics']
)
