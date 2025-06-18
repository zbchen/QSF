./# Experiments

## Solver configuration

The `solver_configs` file contains files that describe the configuration
of the solver. See `solver_configs/generic/README.md`.

## Running experiments

To run experiments run the `0-run_experiments.sh` script.
Note before running this you need to have:

1. Generated all the Docker images for the solvers. Just pull it down directly from Docker Hub.

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

2. Install the dependencies of smt-runner (see `../../smt-runner/README.md`).

## Post-processing results

After running experiments you can follow the steps we used to post-process the
results by running scripts in-order:

- `1-mars_extract_sat.sh`
- `2-check_event_count.sh`
- `3-extract_dsoes_wallclock_time.sh`
- `4-annotate-with-tag.sh`
- `5-annotate-with-fuzzing-throughput.sh`
- `6-merge-results.sh`
- `7-synthesize-portfolio.sh`

## Results

The data of repeat runs of the solvers after post-processing is contained in
the `merged` folder. The data exists as YAML files that are "merged runs" (
repeated runs on the same benchmarks merged into a single file).

We provide a few scripts to show data presented in the paper

### Solver comparison

`solver_cmp_describe.sh` will report on the performance of the different
solvers. It shows the similarity, complementarity, and limitations in
comparison to QSF. It takes a single argument which is the name of
the benchmark suite (`smtlib_qf_fp`, `smtlib_qf_fp_600`, `program_qf_fp`, or `program_qf_fp_600`). This is used for
tables 2, 3 and 4 in the paper.

`solver_cmp_plot_quantile.sh` will generate a quantifle plot comparing the
different solvers. It takes two arguments, the name of the the name of the benchmark
suite (`smtlib_qf_fp`, `smtlib_qf_fp_600`, `program_qf_fp`, or `program_qf_fp_600`), then the timeout (`60` or `600`).  This is used to generate
figure 3 in the paper.

`solver_cmp_plot_scatter.sh` is used to compare the execution time of two
solvers. It takes two arguments, the name of the the name of the benchmark
suite (`smtlib_qf_fp`, `smtlib_qf_fp_600`, `program_qf_fp`, or `program_qf_fp_600`), then the timeout (`60` or `600`). This is used to generate figures 2 and 4 in the
paper.
