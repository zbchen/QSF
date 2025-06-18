# Pre install docker environment

We have deployed the experimental environment on docker. Please pre install docker on your host

# Download

Download docker image:

```sh
$ docker pull dockerqsf/fpse:ubuntu1804
```

If the image is pulled successfully, please check there is an image named apsecpaper/apsecpaper exists.

```sh
$ docker images
REPOSITORY                TAG          IMAGE ID       CREATED         SIZE
dockerqsf/fpse            ubuntu1804   a854909a1719   5 minutes ago   13.8GB
```


Start to run the container in interactive mode.

```sh
$ docker run -it dockerqsf/fpse:ubuntu1804
```

# Obtain experimental results

Our experiments were performed on an Intel(R) Xeon(R) Gold 6458Q 128-core CPU @ 3.10GHz and the operating system is Ubuntu 18.04 LTS. 

To obtain the results, a machine with similar CPUs is required. Moreover, our experiments were run in 60 parallel.

## Analyze a program

Navigate to `/home/aaa/fp-solver/analysis`. There are five experiments in total, which are carried out in `exp0`, `exp1`, `exp2`, `exp3` and `exp4` respectively.
The process of analyzing the program is shown in `exp0`.

```sh
$ cd /home/aaa/fp-solver/analysis/exp0
```

You need to set the parameters to run the script `run_solver.sh`: `./run_solver.sh [work_path] [file_name] [solver_type] [search_type]`, where

- work_path: The path of program file location.
- file_name: The program file name.
- solver_type: The solving modes, e.g. (`z3`, `bitwuzla`, `mathsat5`,`cvc5`), (`colibri`), Search(`jfs`,`gosat`,`qsf`). The bold fields are setting parameters.
- search_type: The search modes, e.g. `bfs` and `dfs`.

If you want to obtain experimental results for a single test program, e.g., `instances/gsl_acosh.c`. For example, obtain the experimental results of `qsf+dfs`.

```sh
$ ./run_solver.sh instances gsl_acosh qsf dfs
```

After running, log and test cases are generated in the corresponding directory, you can read the log as follow:

```sh
$ vim instances/'gsl_acosh&qsf&bfs.runlog' 
```

```sh
KLEE: KLEE: WATCHDOG: watching 17656

KLEE: output directory is "/home/aaa/fp-solver/analysis/benchmark/instances/instances&gsl_acosh&qsf&bfs_output"
KLEE: Using Z3 solver backend
KLEE: Replacing function "__isnanf" with "klee_internal_isnanf"
KLEE: Replacing function "__isnan" with "klee_internal_isnan"
KLEE: Replacing function "__isnanl" with "klee_internal_isnanl"
KLEE: Replacing function "__isinff" with "klee_internal_isinff"
KLEE: Replacing function "__isinf" with "klee_internal_isinf"
KLEE: Replacing function "__isinfl" with "klee_internal_isinfl"
KLEE: WARNING ONCE: function "gsl_ieee_set_mode" has inline asm
>>>optsat exec time: 8.177269e+00 ms
KLEE: WARNING: Z3OPTSAT: OPTSAT solving SAT and evaluate SUCCESS !
>>>optsat exec time: 5.486775e+00 ms
KLEE: WARNING: Z3OPTSAT: OPTSAT solving SAT and evaluate SUCCESS !
KLEE: WARNING ONCE: calling external: sqrt((FSub w64 (FMul w64 N0:(ReadLSB w64 0 a)
                     N0)
           4607182418800017408)) at invhyp.c:34 51
>>>optsat exec time: 8.687612e+00 ms
KLEE: WARNING: Z3OPTSAT: OPTSAT solving SAT and evaluate SUCCESS !
KLEE: WARNING ONCE: calling external: log1p((FAdd w64 (FSub w64 (ReadLSB w64 0 a)
                     4607182418800017408)
           4610479282544200874)) at invhyp.c:39 7
>>>optsat exec time: 9.412387e+00 ms
KLEE: WARNING: Z3OPTSAT: OPTSAT solving SAT and evaluate SUCCESS !

KLEE: done: total instructions = 84
KLEE: done: completed paths = 5
KLEE: done: partially completed paths = 0
KLEE: done: generated tests = 5
Total exec time: 1.098616e+04 ms
```

We can get the coverage information by running the script:

```sh
$ ./repaly.sh
```

```sh
......# some info
     Running ==== > instances&gsl_acosh&qsf&bfs_output/
====  Replay Ktest ====
===>/home/aaa/fp-solver/analysis/benchmark/instances/instances&gsl_acosh&qsf&bfs_output/test000001.ktest
CHECK:  KTests have been generated !
===>python_res: invhyp.c
===>gcno: /home/aaa/fp-solver/gsl/sys/.libs/invhyp.gcno
gcno file is exit
KTest : /home/aaa/fp-solver/analysis/benchmark/instances/instances&gsl_acosh&qsf&bfs_output/test000001.ktest
KLEE-REPLAY: klee_assume(0)!
KLEE-REPLAY: NOTE: Test file: /home/aaa/fp-solver/analysis/benchmark/instances/instances&gsl_acosh&qsf&bfs_output/test000001.ktest
KLEE-REPLAY: NOTE: Arguments: "./gsl_acosh" 
KLEE-REPLAY: NOTE: Storing KLEE replay files in /tmp/klee-replay-5jwDkS
KLEE-REPLAY: NOTE: EXIT STATUS: NORMAL (0 seconds)
KLEE-REPLAY: NOTE: removing /tmp/klee-replay-5jwDkS
===>ktest_time_log: /home/aaa/fp-solver/analysis/benchmark/instances/instances&gsl_acosh&qsf&bfs_output/test000001.time
invhyp.c: No such file or directory
===>cover line res:50.0 , 7
invhyp.c: No such file or directory
===>cover branch res:3
KTest : /home/aaa/fp-solver/analysis/benchmark/instances/instances&gsl_acosh&qsf&bfs_output/test000002.ktest
KLEE-REPLAY: klee_assume(0)!
KLEE-REPLAY: NOTE: Test file: /home/aaa/fp-solver/analysis/benchmark/instances/instances&gsl_acosh&qsf&bfs_output/test000001.ktest
KLEE-REPLAY: NOTE: Arguments: "./gsl_acosh" 
KLEE-REPLAY: NOTE: Storing KLEE replay files in /tmp/klee-replay-HWKF2g
KLEE-REPLAY: NOTE: EXIT STATUS: NORMAL (0 seconds)
KLEE-REPLAY: NOTE: removing /tmp/klee-replay-HWKF2g
===>ktest_time_log: /home/aaa/fp-solver/analysis/benchmark/instances/instances&gsl_acosh&qsf&bfs_output/test000002.time
invhyp.c: No such file or directory
===>cover line res:60.0 , 8
invhyp.c: No such file or directory
===>cover branch res:5
KTest : /home/aaa/fp-solver/analysis/benchmark/instances/instances&gsl_acosh&qsf&bfs_output/test000003.ktest
KLEE-REPLAY: klee_assume(0)!
KLEE-REPLAY: NOTE: Test file: /home/aaa/fp-solver/analysis/benchmark/instances/instances&gsl_acosh&qsf&bfs_output/test000001.ktest
KLEE-REPLAY: NOTE: Arguments: "./gsl_acosh" 
KLEE-REPLAY: NOTE: Storing KLEE replay files in /tmp/klee-replay-v4lEDK
KLEE-REPLAY: NOTE: EXIT STATUS: NORMAL (0 seconds)
KLEE-REPLAY: NOTE: removing /tmp/klee-replay-v4lEDK
===>ktest_time_log: /home/aaa/fp-solver/analysis/benchmark/instances/instances&gsl_acosh&qsf&bfs_output/test000003.time
invhyp.c: No such file or directory
===>cover line res:70.0 , 9
invhyp.c: No such file or directory
===>cover branch res:5
...... # some info

```

Coverage information can be found in `res_all_0.txt`. The three columns are the name of benchmark, the code coverage, covered statements, covered branches, and the total execution time, respectively.

```sh
$ cat res_all_0.txt
```

```
instances&gsl_acosh&qsf&bfs_output/ , 100.0 , 11, 7, 12
```

Coverage trend information can be found in `cov_trend_0.txt`. `TestCase` is the benchmark and configuration information. Each row below has three columns showing the solving time, code coverage, covered statements, covered branches.

```sh
$ cat cov_trend_0.txt
```

```
=== TestCase : instances&gsl_acosh&qsf&bfs_output/
0, 50.0 , 7, 3
0, 60.0 , 8, 5
0, 70.0 , 9, 5
0, 90.0 , 10, 7
0, 100.0 , 11, 7
=== End
```

## Run in 60 parallel

The machine used in our experiments has 80 cores and 192GB memory. Before running the script, please select the appropriate machine and complete parameter configuration.

The execution time and solving time settings in the `run_solver.sh` script are 3600s and 60s respectively. This is a long execution time, and you can enter the script and modify it to your own needs.

```sh
$ vim run_solver.sh
```

```sh
......
MAX_EXE_TIME=3600
SOLVER_TIME=60
......
```

You can also modify the parallel quantity in the script:

```sh
$ vim multi_process.sh
```

```sh
......
pool = multiprocessing.Pool(processes=60) # parallel of 60
......
```

Then you can use `nohup python3 multi_process.py &` to execute all benchmarks in parallel.

```sh
$ nohup python3 multi_process.py &
```