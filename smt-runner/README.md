# smt-runner

smt-runner is the infrastructure we use to

* Filter benchmarks.
* Run solvers on a set of benchmarks.
* Post-process those runs.
* Compute results and generate graphs.

## Dependencies

smt-runner was developed against Python 3.6. It might work with
other versions.

To use smt-runner in the context of this artifact you will need
to install Docker. We used `24.0.2` but the experiments should
still work with older/newer versions.

smt-runner also has a bunch of external python dependencies to install
them run

```
sudo apt-get update
sudo apt-get install libnuma-dev
pip3 install --user -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
```
