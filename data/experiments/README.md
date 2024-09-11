./# Experiments

## Solver configuration

The `solver_configs` file contains files that describe the configuration
of the solver. See `solver_configs/generic/README.md`.

## Running experiments

To run experiments run the `0-run_experiments.sh` script.
Note before running this you need to have:

1. Generated all the Docker images for the solvers (see `../../solvers/README.md`).
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

Note each script should exit with the `0` exit code. If a script has
a non-zero exit code then something went wrong.

## Results

The data of repeat runs of the solvers after post-processing is contained in
the `merged` folder. The data exists as YAML files that are "merged runs" (
repeated runs on the same benchmarks merged into a single file).

We provide a few scripts to show data presented in the paper

### Solver comparison

`solver_cmp_describe.sh` will report on the performance of the different
solvers. It shows the similarity, complementarity, and limitations in
comparison to JFS-LF-SS. It takes a single argument which is the name of
the benchmark suite (`smtlib_qf_fp`, `smtlib_qf_fp_600`, `program_qf_fp`, or `program_qf_fp_600`). This is used for
table 2 and 3 in the paper.

`solver_cmp_plot_scatter.sh` is used to compare the execution time of two
solvers. It takes three arguments, the name of the the name of the benchmark
suite (`smtlib_qf_fp`, `smtlib_qf_fp_600`, `program_qf_fp`, or `program_qf_fp_600`), then the name of the first solver and
then the name of the second solver. See the `solvers` array in `common.sh` for
the possible solver names. This is used to generate figures 3 and 4 in the
paper.
