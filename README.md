# QSF paper artifact

This is the artifact of QSF. You can download the repository to your local computer to get the experimental results in the paper.

# `data`

This directory contains the experiment data , solver configurations, and benchmark selection.


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
docker pull dockerqsf/jfs-2019:ubuntu1804
docker pull dockerqsf/xsat-2016:ubuntu1804
docker pull dockerqsf/gosat-2017:ubuntu1804
docker pull dockerqsf/optsat-2024:ubuntu1804
```