# QSF paper artifact

This directory contains files that supplement the QSF
paper by describing our data in more detail.

Note that this git repository relies on git-lfs. You will
need to install this in order to retrieve the large files
in the respository. Once you have git-lfs installed run

```
git-lfs clone https://github.com/qsat-artifact/qsat-ase24
```

# `data`

This directory contains the experiment data, solver configurations, and benchmark selection.


# `smt-runner`

This is the code we used to run experiments and process them.

# `solvers`

The QSF contrast solver can be pulled from dockerhub:
```
docker pull dockerqsf/z3-4.6.0:ubuntu1804
docker pull dockerqsf/cvc5-1.2:ubuntu1804
docker pull dockerqsf/mathsat-5.5.1:ubuntu1804
docker pull dockerqsf/bitwuzla-1.0:ubuntu1804
docker pull dockerqsf/colibri-2017:ubuntu1804
docker pull dockerqsf/coral-2015:ubuntu1804
docker pull dockerqsf/my-racket-app:latest
docker pull dockerqsf/jfs-2019:ubuntu1804
docker pull dockerqsf/xsat-2016:ubuntu1804
docker pull dockerqsf/gosat-2017:ubuntu1804
docker pull dockerqsf/qsat-2024:ubuntu1804
docker pull dockerqsf/qsat-bitwuzla:ubuntu1804
```